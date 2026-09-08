from __future__ import annotations

import os
import subprocess
import json
import shutil
import tempfile
import textwrap
import wave
from pathlib import Path
from typing import Optional
from post_processing.copy_songs import extract_date_from_file, parse_date_str

def make_videos(
    src_dir: str, 
    dest_dir: str, 
    bg_image_path: str = "assets/images/background.png", 
    ffmpeg_path: str = "ffmpeg",
    target_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> None:
    """
    Generates video files for each matching .wav file in the source directory using a two-pass
    loudnorm audio normalization and an image background overlay.
    Optionally filters by target_date (YYYY-MM-DD) or date range (start_date to end_date).
    """
    if not os.path.exists(src_dir):
        print(f"❌ Error: Source directory does not exist: {src_dir}")
        return

    if not os.path.exists(bg_image_path):
        print(f"❌ Error: Background image not found at: {bg_image_path}")
        return

    os.makedirs(dest_dir, exist_ok=True)
    
    if target_date:
        print(f"Filtering for date: {target_date}")
    elif start_date and end_date:
        print(f"Filtering for timeframe: {start_date} to {end_date} (inclusive)")

    # Get all .wav files in the verified directory
    wav_files = [f for f in os.listdir(src_dir) if f.lower().endswith(".wav")]
    
    if not wav_files:
        print(f"No .wav files found in {src_dir}.")
        return

    target_dt = parse_date_str(target_date)
    start_dt = parse_date_str(start_date)
    end_dt = parse_date_str(end_date)

    src_path = Path(src_dir)
    filtered_wav_files = []
    for audio_file in sorted(wav_files):
        file_path = src_path / audio_file
        file_dt = extract_date_from_file(file_path, src_path)

        if target_dt is not None:
            if file_dt is None or file_dt.date() != target_dt.date():
                continue
        elif start_dt is not None and end_dt is not None:
            if file_dt is None or not (start_dt.date() <= file_dt.date() <= end_dt.date()):
                continue

        filtered_wav_files.append(audio_file)

    if not filtered_wav_files:
        if target_dt or (start_dt and end_dt):
            print(f"No .wav files matching the specified date(s) found in {src_dir}.")
        else:
            print(f"No .wav files found in {src_dir}.")
        return

    print(f"Found {len(filtered_wav_files)} audio files. Generating videos...")

    for audio_file in filtered_wav_files:
        song_title = os.path.splitext(audio_file)[0]
        full_audio_path = os.path.join(src_dir, audio_file)
        output_file = os.path.join(dest_dir, f"{song_title}.mp4")

        # Skip if video already exists
        if os.path.exists(output_file):
            print(f"Skipping (video already exists): {song_title}.mp4")
            continue

        print("=" * 53)
        print(f"Processing: {song_title}")
        print("=" * 53)

        # We need a temp text file for FFmpeg to draw the text, avoiding escaping nightmares
        # Replace " - " with newlines and auto-wrap long text lines to avoid clipping
        title_parts = song_title.split(" - ")
        wrapped_parts = [textwrap.fill(part.strip(), width=32) for part in title_parts if part.strip()]
        multiline_title = "\n".join(wrapped_parts)
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as temp_txt:
            temp_txt.write(multiline_title)
            temp_txt_path = temp_txt.name

        try:
            print("  -> Pass 1: Analyzing audio dynamics...")
            # Pass 1: loudnorm analysis
            pass1_cmd = [
                ffmpeg_path, "-hide_banner", "-nostats", "-i", full_audio_path,
                "-af", "loudnorm=I=-14:TP=-1:print_format=json",
                "-f", "null", "-"
            ]
            
            # FFmpeg writes loudnorm JSON to stderr
            result = subprocess.run(pass1_cmd, stderr=subprocess.PIPE, text=True, check=False)
            
            # Parse the JSON from the output block
            stderr_output = result.stderr
            try:
                # loudnorm JSON is printed at the end of the stderr log
                json_start = stderr_output.find("{")
                json_end = stderr_output.rfind("}") + 1
                if json_start == -1 or json_end == 0:
                    raise ValueError("No JSON found in FFmpeg output")
                    
                stats_json = json.loads(stderr_output[json_start:json_end])
                
                measured_i = stats_json["input_i"]
                measured_tp = stats_json["input_tp"]
                measured_lra = stats_json["input_lra"]
                measured_thresh = stats_json["input_thresh"]
                target_offset = stats_json["target_offset"]
                
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                print(f"  -> Error: Could not analyze audio dynamics for {song_title}. Skipping.")
                continue

            print("  -> Pass 2: Rendering final video with OLED-safe text, crossfades, and 320k audio...")
            
            # Calculate duration to set the fade-out start time
            with wave.open(full_audio_path, 'r') as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                duration = frames / float(rate)
            
            fade_s = 3.0
            fade_out_start = max(0, duration - fade_s)
            
            loudnorm_filter = f"loudnorm=I=-14:TP=-1:measured_I={measured_i}:measured_TP={measured_tp}:measured_LRA={measured_lra}:measured_thresh={measured_thresh}:offset={target_offset}:linear=true"
            fade_filter = f"afade=t=in:st=0:d={fade_s},afade=t=out:st={fade_out_start:.3f}:d={fade_s}"
            
            pass2_cmd = [
                ffmpeg_path, "-y", "-hide_banner", "-loop", "1", "-framerate", "30",
                "-i", bg_image_path,
                "-i", full_audio_path,
                "-vf", f"drawtext=textfile={temp_txt_path}:line_spacing=16:fontcolor=white@0.8:fontsize=48:shadowcolor=black@0.7:shadowx=3:shadowy=3:x=(w-text_w)/2:y=(h-text_h)/2",
                "-af", f"{loudnorm_filter},{fade_filter}",
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "320k",
                "-pix_fmt", "yuv420p", "-shortest",
                output_file
            ]
            
            subprocess.run(pass2_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print(f"  -> ✅ Success: {os.path.basename(output_file)}")
            
        except subprocess.CalledProcessError as e:
            print(f"  -> ❌ Error rendering video: {e}")
        finally:
            # Clean up the temporary title text file
            if os.path.exists(temp_txt_path):
                os.remove(temp_txt_path)

    print("=" * 53)
    print("All videos generated and audio precision-normalized successfully!")
