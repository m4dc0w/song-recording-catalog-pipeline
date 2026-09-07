import os
import re
import json
import time
import subprocess
from dotenv import load_dotenv
from google import genai
from google.genai import types

from core.schemas import ServicePlan

# Load variables from .env file into the environment
load_dotenv()

# ==============================================================================
# 1. PIPELINE CONFIGURATION & TUNING
# ==============================================================================
# Fetch storage paths dynamically from environment variables
RAW_AUDIO_DIR = os.getenv("RAW_AUDIO_DIR")
PROCESSED_AUDIO_DIR = os.getenv("PROCESSED_AUDIO_DIR")

# Allow overriding the FFmpeg binary path, fallback to system PATH "ffmpeg"
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
if not FFMPEG_PATH.strip():
    FFMPEG_PATH = "ffmpeg"

# Fetch the AI model dynamically, fallback to the stable 3.8 flash model
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
if not GEMINI_MODEL.strip():
    GEMINI_MODEL = "gemini-3.8-flash"

if not RAW_AUDIO_DIR or not PROCESSED_AUDIO_DIR:
    raise ValueError(
        "ERROR: Storage paths are missing. "
        "Please define RAW_AUDIO_DIR and PROCESSED_AUDIO_DIR in your .env file."
    )

# --- Audio Extraction Tuning ---
# Buffers added to AI-detected boundaries to capture natural acoustic room decay 
# and provide sufficient overlap for downstream crossfading in the final render.
SONG_PADDING_MS: int = 3000    # 3-second buffer for musical transitions
SPEECH_PADDING_MS: int = 250   # Tight 250ms buffer for spoken word transitions

# ==============================================================================
# 2. HELPER FUNCTIONS: AUDIO & TIMESTAMPS
# ==============================================================================
def _format_setlist_for_ai(plan: ServicePlan) -> str:
    """Formats the songs in a ServicePlan into a single string for the AI prompt."""
    lines = []
    for song in plan.songs:
        if song.key:
            lines.append(f"{song.title} ({song.key})")
        else:
            lines.append(song.title)
    return "\n".join(lines)


def clean_filename(filename: str) -> str:
    """Removes illegal OS filesystem characters from song titles."""
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()


def time_to_ms(time_str: str) -> int:
    """Converts HH:MM:SS.f or MM:SS.f timestamp strings into integer milliseconds."""
    try:
        main_time, fraction = time_str.strip().split('.')
        parts = list(map(int, main_time.split(':')))
        fraction_str = fraction.ljust(3, '0')[:3]
        ms_fraction = int(fraction_str)
        
        if len(parts) == 3:
            h, m, s = parts
            return ((h * 3600) + (m * 60) + s) * 1000 + ms_fraction
        elif len(parts) == 2:
            m, s = parts
            return ((m * 60) + s) * 1000 + ms_fraction
        return 0
    except Exception as e:
        print(f"Error parsing timestamp '{time_str}': {e}")
        return 0


def compress_wav_to_mp3(input_wav: str, output_mp3: str) -> None:
    """Creates a 192kbps stereo MP3 preview to reduce upload bandwidth and API latency."""
    print(f"Compressing raw WAV to 64kbps mono MP3 preview...")
    command = [
        FFMPEG_PATH, "-y",
        "-i", input_wav,
        "-codec:a", "libmp3lame",
        "-b:a", "192k",    # Higher bit rate to preserve musical detail
        "-ac", "2",        # Keep stereo channels for spatial segmentation cues
        "-ar", "44100",    # Ensure full CD-quality frequency spectrum
        output_mp3
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def validate_segments(segments: list) -> list:
    """Sanitizes AI JSON output while permitting intentional musical overlaps."""
    valid_segments = []
    for i, seg in enumerate(segments):
        start_ms = time_to_ms(seg['start_time'])
        end_ms = time_to_ms(seg['end_time'])
        
        # 1. Prevent impossible negative durations
        if end_ms <= start_ms:
            print(f"Warning: Segment {i+1} ({seg.get('label')}) has invalid duration. Skipping.")
            continue
            
        # 2. Allow overlaps, but prevent a segment from jumping completely backwards in time
        if valid_segments:
            prev_start = time_to_ms(valid_segments[-1]['start_time'])
            if start_ms < prev_start:
                print(f"Warning: Segment {i+1} starts before the previous segment even began. Adjusting.")
                # Snap to the previous start rather than the previous end to preserve overlap logic
                seg['start_time'] = valid_segments[-1]['start_time'] 
                
        valid_segments.append(seg)
    return valid_segments


def slice_audio_ffmpeg_copy(input_wav: str, output_wav: str, start_s: float, end_s: float) -> None:
    """Slices audio directly on disk using bit-perfect stream copy for maximum fidelity."""
    command = [
        FFMPEG_PATH, "-y",
        "-ss", f"{start_s:.3f}",
        "-i", input_wav,
        "-to", f"{end_s:.3f}",
        "-c:a", "copy",
        output_wav
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def generate_daw_locators(segments: list, output_dir: str, service_date: str) -> None:
    """Generates a tab-separated locator text file for visual timeline auditing in Live 12."""
    locator_path = os.path.join(output_dir, f"{service_date}_DAW_Locators.txt")
    with open(locator_path, 'w', encoding='utf-8') as f:
        for seg in segments:
            start_s = time_to_ms(seg['start_time']) / 1000.0
            title = seg.get('song_title', seg.get('label', 'Marker')).strip()
            f.write(f"{start_s:.3f}\t{title}\n")
    print(f"Generated DAW Locators: {locator_path}")

# ==============================================================================
# 3. MAIN EXECUTION PIPELINE
# ==============================================================================
def segment_service_audio(plan: ServicePlan) -> None:
    """Executes the complete AI audio segmentation pipeline for a single service plan.
    
    Takes the raw audio file associated with the service plan, compresses a 
    temporary preview for the Gemini API, prompts the AI to identify precise 
    timestamps based on the setlist, and uses FFmpeg to extract bit-perfect 
    slices for each song and spoken segment.
    
    Args:
        plan (ServicePlan): The structured dataclass containing the service details, 
            setlist items, and the localized path to the raw .wav file.
            
    Raises:
        ValueError: If the raw_audio_filepath is missing from the plan.
        FileNotFoundError: If the raw_audio_filepath does not exist on disk.
    """
    if not plan.raw_audio_filepath:
        raise ValueError(f"Cannot process service for {plan.date}: 'raw_audio_filepath' is missing.")

    if not os.path.exists(plan.raw_audio_filepath):
        raise FileNotFoundError(f"Audio file not found at path: {plan.raw_audio_filepath}")

    # Setup Output Folder using the generalized PROCESSED_AUDIO_DIR
    output_dir = os.path.join(PROCESSED_AUDIO_DIR, f"Output_{plan.date}")
    
    if os.path.exists(output_dir):
        raise FileExistsError(f"Destination folder already exists: {output_dir}")
        
    os.makedirs(output_dir)
    
    # Step A: Create Lightweight MP3 Preview
    temp_mp3_path = f"temp_{plan.date}.mp3"
    compress_wav_to_mp3(plan.raw_audio_filepath, temp_mp3_path)

    # Step B: Initialize Gemini Client & Upload Preview File
    gemini_client = genai.Client()
    print("Uploading MP3 preview to Gemini File API...")
    audio_file = gemini_client.files.upload(file=temp_mp3_path)

    while audio_file.state.name == "PROCESSING":
        print("Waiting for audio processing...")
        time.sleep(4)
        audio_file = gemini_client.files.get(name=audio_file.name)

    # Step C: Define Strict JSON Output Schema with Enhanced Self-Critique
    time_regex_pattern = r"^\d{2}:\d{2}:\d{2}\.\d{1,3}$"
    
    segmentation_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "start_time": types.Schema(type=types.Type.STRING, pattern=time_regex_pattern),
            "end_time": types.Schema(type=types.Type.STRING, pattern=time_regex_pattern),
            "label": types.Schema(type=types.Type.STRING, enum=["song", "speaking", "sermon"]),
            "song_title": types.Schema(type=types.Type.STRING),
            "reason": types.Schema(type=types.Type.STRING)
        },
        required=["start_time", "end_time", "label", "song_title", "reason"]
    )

    master_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "step_1_audio_analysis": types.Schema(
                type=types.Type.STRING, 
                description="Briefly map out the chronological flow of the audio. Explicitly note the exact start of musical intros, musical interludes/segues between songs, and musical outros."
            ),
            "step_2_self_critique": types.Schema(
                type=types.Type.STRING, 
                description="Review proposed boundaries. CRITICAL CHECKS: 1) INTROS: Did I exclude preceding unaccompanied speech? 2) OUTROS: Did the song end exactly when instruments stopped? 3) INTERLUDES: Did I properly overlap timestamps for continuous segues? 4) BACKGROUND PADS: Did I mistakenly label a spoken prayer/sermon as a 'song' just because ambient instruments played underneath? 5) MICRO-SEGMENTS: Did I avoid creating tiny 'song' segments for a speaker briefly reciting/singing a lyric?"
            ),
            "final_segments": types.Schema(
                type=types.Type.ARRAY,
                items=segmentation_schema
            )
        },
        required=["step_1_audio_analysis", "step_2_self_critique", "final_segments"]
    )

    setlist_str = _format_setlist_for_ai(plan)
    
    prompt = f"""
    Analyze this Sunday service recording for {plan.date}.
    Segment the entire file into: "song", "speaking", or "sermon".
    
    Note: Sometimes the recording may be a partial recording of the service, so the
    entire setlist may not be present. If a listed song is missing from the audio, skip it.
    
    CRITICAL FORMATTING: The timestamp segments must strictly use full hour, minute, and seconds
    with decimals `%H:%M:%S.%f` timestamp format (e.g., `00:34:56.789`) with leading
    zeros even if the hour is `00`. Do not output 2-part `MM:SS.f` timestamps.
    
    CRITICAL INSTRUCTIONS FOR SONG BOUNDARIES AND OVERLAPS:
    1. CAPTURE MUSICAL INTROS (START BOUNDARY): A "song" segment MUST begin the exact moment 
       the musical arrangement (instrumentation, synth pads, acoustic strumming, 
       drum count-ins, or a cappella vocal melodies) starts.
       
       - NEGATIVE CONSTRAINT: Do NOT include unaccompanied speech as part of a 
         "song". Unaccompanied speech, prayer, or song introductions must be 
         assigned to their relevant spoken category ("speaking" or "sermon"). 
         The "song" segment strictly begins at the first instrumental note or 
         singing. If the person continues to speak or pray over the instrumental 
         intro, allow the spoken and "song" segments to overlap.

    2. CAPTURE MUSICAL OUTROS (END BOUNDARY): A "song" segment MUST END the exact moment 
       the singing and musical instruments fully stop playing. 
       - NEGATIVE CONSTRAINT: Do NOT extend a "song" segment into the sermon, announcements, 
         or post-worship prayers. Once the instruments fade out and only unaccompanied 
         speech remains, the "song" segment is completely over.
         
    3. SEGUES & CONTINUOUS TRANSITIONS: If the band performs a segue (a continuous 
       transition from one song directly into the next without stopping), the 
       musical vamp/interlude between them belongs to BOTH songs. 
       - Extend the `end_time` of the first song to include the entire transition.
       - Begin the `start_time` of the second song at the exact start of that same transition.
       
    4. OVERLAPPING IS EXPECTED: Do not force segments to be perfectly sequential. 
       It is fully expected and required that timestamps overlap (e.g., someone 
       "speaking" over a "song" intro, or a segue where two "song" segments share 
       an overlapping transition window, typically lasting anywhere from a few 
       seconds up to a minute). The overlap must cover the exact duration of the 
       musical interlude or vamp between the two tracks.

    SELF-CORRECTION & CRITIQUE LOOP:
    Before finalizing the `final_segments` array, you must complete the self-reflection fields:
    - In `step_1_audio_analysis`, map out the audio events, specifically tracking intros, segues/interludes, and outros.
    - In `step_2_self_critique`, ruthlessly audit your boundaries. Ask yourself: 
      1. INTROS: Did I mistakenly include a spoken introduction before the music started inside a 'song' segment? 
      2. OUTROS: Did I accidentally stretch a 'song' over the sermon or post-worship prayer after the instruments faded? 
      3. INTERLUDES: If two songs flow together, did I correctly overlap their timestamps to share the musical segue?
      4. BACKGROUND PADS: Is the pastor preaching over a soft background synth pad? If so, that is still a "sermon", NOT a "song".
      5. MICRO-SEGMENTS: Did a speaker recite or sing a single line of a song during a message? Keep that labeled as "sermon" or "speaking", NOT a new "song".
    If you catch an error in your logic, adjust your final timestamps accordingly.

    CRITICAL SETLIST MAPPING & UNLISTED SONGS:
    1. EXPECTED SONGS: Map matching song tracks strictly to the names provided in the list below, in chronological order.
    2. UNLISTED SONGS: If the band plays an unexpected song or spontaneous worship moment not in the setlist, you MUST still segment it as a "song". 
       - Attempt to identify the `song_title` dynamically based on the lyrics you hear. 
       - If you cannot confidently identify the song, set the `song_title` to "Unlisted Song".
       - NEGATIVE CONSTRAINT: Passionate preaching, praying, or reciting lyrics without musical accompaniment is NOT a song. Do not mislabel the sermon as an "Unlisted Song" or stretch a setlist track over it.
    
    <setlist>
    {setlist_str}
    </setlist>
    """

    print(f"Requesting high-precision segmentation with self-reflection from {GEMINI_MODEL}...")
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[audio_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=master_schema,
            temperature=0.1
        )
    )

    # Parse and Validate Segments from the Master Object
    response_data = json.loads(response.text)
    
    print("\n--- AI Self-Critique Log ---")
    print(f"Analysis: {response_data.get('step_1_audio_analysis', 'N/A')}")
    print(f"Critique: {response_data.get('step_2_self_critique', 'N/A')}")
    print("----------------------------\n")

    segments = validate_segments(response_data.get('final_segments', []))

    # Step D: Generate DAW Locators
    generate_daw_locators(segments, output_dir, plan.date)

    # Step E: Slice Master WAV File & Build Audit Report
    song_idx, speak_idx, sermon_idx = 1, 1, 1
    report_content = f"=====================================================\n"
    report_content += f"AI AUDIO SEGMENTATION REPORT - SERVICE DATE: {plan.date}\n"
    report_content += f"=====================================================\n\n"
    
    # Append the AI's internal thoughts to the text report for auditing
    report_content += f"AI AUDIO ANALYSIS:\n{response_data.get('step_1_audio_analysis', 'N/A')}\n\n"
    report_content += f"AI SELF-CRITIQUE:\n{response_data.get('step_2_self_critique', 'N/A')}\n"
    report_content += f"=====================================================\n\n"

    print("Executing precision FFmpeg slicing operations...")
    for seg in segments:
        label = seg['label'].lower()
        target_start_ms = time_to_ms(seg['start_time'])
        target_end_ms = time_to_ms(seg['end_time'])
        reason_text = seg.get('reason', 'N/A')

        if label == "song":
            start_ms = max(0, target_start_ms - SONG_PADDING_MS)
            end_ms = target_end_ms + SONG_PADDING_MS
            
            raw_title = seg.get('song_title', '').strip()
            title = raw_title if raw_title else f"Worship Song {song_idx}"
            filename = f"Song_{song_idx:02d}_{clean_filename(title)} - {plan.date}.wav"
            report_content += f"TRACK {song_idx:02d}: {title}\n"
            song_idx += 1
        else:
            start_ms = max(0, target_start_ms - SPEECH_PADDING_MS)
            end_ms = target_end_ms + SPEECH_PADDING_MS
            
            if label == "sermon":
                filename = f"Sermon_{sermon_idx:02d} - {plan.date}.wav"
                report_content += f"SERMON {sermon_idx:02d}\n"
                sermon_idx += 1
            else:
                filename = f"Speaking_{speak_idx:02d} - {plan.date}.wav"
                report_content += f"SPEAKING {speak_idx:02d}\n"
                speak_idx += 1

        report_content += f"  Timestamps: {seg['start_time']} --> {seg['end_time']}\n"
        report_content += f"  Filename:   {filename}\n"
        report_content += f"  AI Reason:  {reason_text}\n"
        report_content += f"-----------------------------------------------------\n\n"

        export_path = os.path.join(output_dir, filename)
        
        # Convert ms to seconds for the bit-perfect stream copy
        start_s = start_ms / 1000.0
        end_s = end_ms / 1000.0
        
        slice_audio_ffmpeg_copy(plan.raw_audio_filepath, export_path, start_s, end_s)
        
        # Formatted Terminal Output
        print(f"  Sliced: [{seg['start_time']} --> {seg['end_time']}] {filename}")

    # Write Audit Report File to Drive Folder
    report_path = os.path.join(output_dir, f"Segmentation_Report_{plan.date}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    # Step F: Local Temp Cleanup
    if os.path.exists(temp_mp3_path):
        os.remove(temp_mp3_path)

    print(f"\nProcessing Complete! All files saved directly to:\n{output_dir}")

# ==============================================================================
# 4. ENTRY POINT
# Example Usage: python3 audio_segmentation.py
# ==============================================================================
if __name__ == "__main__":
    from core.schemas import Song
    
    mock_plan = ServicePlan(
        date="2026-09-06",
        songs=[
            Song(title="Glorious and Mighty"),
            Song(title="Crown Him With Many Crowns"),
            Song(title="And Can It Be"),
            Song(title="All I Have Is Christ"),
            Song(title="Holy, Holy, Holy")
        ],
        raw_audio_filepath=os.path.join(RAW_AUDIO_DIR, "R_20260906-103109.wav")
    )
    
    print("========PROCESSING========")
    print(f"SERVICE_DATE: '{mock_plan.date}'")
    print(f"RAW_WAV_INPUT_PATH: '{mock_plan.raw_audio_filepath}'")
    print("==========================")
    
    if os.path.exists(mock_plan.raw_audio_filepath):
        segment_service_audio(mock_plan)
    else:
        print(f"Please specify a valid path to your input WAV file. '{mock_plan.raw_audio_filepath}' not found.")
