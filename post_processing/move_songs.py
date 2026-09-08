from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional
from post_processing.copy_songs import extract_date_from_file, parse_date_str

def move_songs(
    src_dir: str, 
    dest_dir: str, 
    target_date: Optional[str] = None, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> None:
    """
    Moves matching .wav files from the staging source directory to the verified destination directory.
    Optionally filters by target_date (YYYY-MM-DD) or date range (start_date to end_date).
    Prevents overwriting existing files in the destination.
    """
    if not os.path.exists(src_dir):
        print(f"❌ Error: Source directory does not exist: {src_dir}")
        return

    os.makedirs(dest_dir, exist_ok=True)
    
    print(f"Searching for files in: {src_dir}")
    print(f"Moving to: {dest_dir}")
    if target_date:
        print(f"Filtering for date: {target_date}")
    elif start_date and end_date:
        print(f"Filtering for timeframe: {start_date} to {end_date} (inclusive)")
    print("-" * 48)

    src_path = Path(src_dir)
    matched_files = list(src_path.glob("*.wav"))
    
    if not matched_files:
        print("No matching '.wav' files found in staging directory.")
        return

    target_dt = parse_date_str(target_date)
    start_dt = parse_date_str(start_date)
    end_dt = parse_date_str(end_date)

    filtered_files = []
    for file_path in matched_files:
        file_dt = extract_date_from_file(file_path, src_path)

        if target_dt is not None:
            if file_dt is None or file_dt.date() != target_dt.date():
                continue
        elif start_dt is not None and end_dt is not None:
            if file_dt is None or not (start_dt.date() <= file_dt.date() <= end_dt.date()):
                continue

        filtered_files.append(file_path)

    if not filtered_files:
        if target_dt or (start_dt and end_dt):
            print("No matching '.wav' files found in staging directory for the specified date(s).")
        else:
            print("No matching '.wav' files found in staging directory.")
        return

    moved_count = 0

    for file_path in filtered_files:
        base_name = file_path.name
        dest_path = os.path.join(dest_dir, base_name)
        
        # Move without overwriting
        if not os.path.exists(dest_path):
            shutil.move(str(file_path), dest_path)
            print(f"Moved: {base_name}")
            moved_count += 1
        else:
            print(f"Skipped (already exists in destination): {base_name}")

    print("-" * 48)
    print(f"Done! Moved {moved_count} files.")
