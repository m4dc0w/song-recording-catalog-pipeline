from __future__ import annotations

import os
import subprocess
import argparse
from pathlib import Path
from typing import Optional, List
from post_processing.copy_songs import extract_date_from_file, parse_date_str

def make_mp3(
    src_dir: str, 
    dest_dir: str, 
    ffmpeg_path: str = "ffmpeg",
    target_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> None:
    """
    Generates high-quality MP3 audio files using FFmpeg (-codec:a libmp3lame -q:a 0)
    for each matching .wav file in the source directory for broad compatibility across devices.
    Optionally filters by target_date (YYYY-MM-DD) or date range (start_date to end_date).
    """
    if not os.path.exists(src_dir):
        print(f"❌ Error: Source directory does not exist: {src_dir}")
        return

    os.makedirs(dest_dir, exist_ok=True)
    
    if target_date:
        print(f"Filtering for date: {target_date}")
    elif start_date and end_date:
        print(f"Filtering for timeframe: {start_date} to {end_date} (inclusive)")

    # Get all .wav files in the source directory
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

    print(f"Found {len(filtered_wav_files)} audio files. Generating MP3s...")

    for audio_file in filtered_wav_files:
        song_title = os.path.splitext(audio_file)[0]
        full_audio_path = os.path.join(src_dir, audio_file)
        output_file = os.path.join(dest_dir, f"{song_title}.mp3")

        # Skip if MP3 already exists
        if os.path.exists(output_file):
            print(f"Skipping (MP3 already exists): {song_title}.mp3")
            continue

        print("=" * 53)
        print(f"Processing: {song_title}")
        print("=" * 53)

        cmd = [
            ffmpeg_path, "-y", "-hide_banner", "-nostats",
            "-i", full_audio_path,
            "-codec:a", "libmp3lame",
            "-q:a", "0",
            output_file
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  -> ✅ Success: {os.path.basename(output_file)}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  -> ❌ Error converting to MP3: {e}")

    print("=" * 53)
    print("All MP3s generated successfully!")


def main(cli_args: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Convert WAV audio recordings to highest-quality MP3s.")
    parser.add_argument("--src-dir", default=os.getenv("VERIFIED_AUDIO_DIR", os.path.join(os.getcwd(), "verified_audio")), help="Source directory containing .wav files.")
    parser.add_argument("--dest-dir", default=os.getenv("MP3_DIR", os.path.join(os.getenv("VERIFIED_AUDIO_DIR", os.path.join(os.getcwd(), "verified_audio")), "MP3")), help="Destination directory for .mp3 files.")
    parser.add_argument("--date", help="Optional target date (YYYY-MM-DD) filter.")
    parser.add_argument("--start-date", help="Optional start date (YYYY-MM-DD) filter.")
    parser.add_argument("--end-date", help="Optional end date (YYYY-MM-DD) filter.")
    parser.add_argument("--ffmpeg-path", default=os.getenv("FFMPEG_PATH", "ffmpeg"), help="Path to ffmpeg binary.")

    args = parser.parse_args(cli_args) if cli_args is not None else parser.parse_args()

    make_mp3(
        src_dir=args.src_dir,
        dest_dir=args.dest_dir,
        ffmpeg_path=args.ffmpeg_path,
        target_date=args.date,
        start_date=args.start_date,
        end_date=args.end_date,
    )


if __name__ == "__main__":
    main()
