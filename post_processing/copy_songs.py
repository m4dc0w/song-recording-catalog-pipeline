from __future__ import annotations

import os
import shutil
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

def parse_date_str(date_str: Optional[str]) -> Optional[datetime]:
    """Parses a date string in YYYY-MM-DD or YYYYMMDD format."""
    if not date_str or not str(date_str).strip():
        return None
    cleaned = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            pass
    return None

def extract_date_from_file(file_path: Path, src_dir: Path) -> Optional[datetime]:
    """
    Extracts the service date associated with a segmented song file.
    Checks the filename first (YYYY-MM-DD or YYYYMMDD), then inspects
    enclosing folder names relative to the source directory.
    """
    # 1. Hyphenated date in filename: YYYY-MM-DD (e.g., Song_01_Title - 2026-09-06.wav)
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', file_path.name)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # 2. Compact date in filename: YYYYMMDD
    m = re.search(r'(?:^|[^0-9])(\d{4})(\d{2})(\d{2})(?:[^0-9]|$)', file_path.name)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # 3. Relative enclosing folder names within src_dir (e.g., Output_R_20260906-103109 or Output_2026-09-06)
    try:
        rel_path = file_path.relative_to(src_dir)
        for part in reversed(rel_path.parts[:-1]):
            m = re.search(r'(\d{4})-(\d{2})-(\d{2})', part)
            if m:
                try:
                    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    pass
            m = re.search(r'(?:^|[^0-9])(\d{4})(\d{2})(\d{2})(?:[^0-9]|$)', part)
            if m:
                try:
                    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    pass
    except ValueError:
        pass

    return None

def format_duplicate_song_name(clean_filename: str, index: int) -> str:
    """
    Appends an index suffix (e.g. ' (2)') to the song title for duplicate songs.
    If index <= 1, returns the clean filename unchanged.
    
    If the filename contains a date at the end (e.g. 'Title - YYYY-MM-DD.wav'),
    the suffix is placed on the song title before the date:
      'Title (2) - YYYY-MM-DD.wav'
    Otherwise:
      'Title (2).wav'
    """
    if index <= 1:
        return clean_filename

    stem = Path(clean_filename).stem
    ext = Path(clean_filename).suffix

    # Match trailing dates like ' - YYYY-MM-DD' or ' - YYYYMMDD'
    date_pattern = re.compile(r'^(.*?)\s*-\s*(\d{4}-\d{2}-\d{2}(?:-\d+)?|\d{8})$')
    m = date_pattern.match(stem)
    if m:
        title = m.group(1).strip()
        date_part = m.group(2).strip()
        return f"{title} ({index}) - {date_part}{ext}"
    else:
        return f"{stem} ({index}){ext}"

def copy_songs(
    src_dir: str, 
    dest_dir: str, 
    target_date: Optional[str] = None, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> None:
    """
    Finds all 'Song_XX_*.wav' files in the source directory (recursively),
    strips the 'Song_XX_' prefix, and copies them to the destination directory.
    Prevents overwriting existing files in the destination.

    If target_date is provided, only copies files matching that date.
    If start_date and/or end_date are provided, only copies files within that date range (inclusive).
    """
    if not os.path.exists(src_dir):
        print(f"❌ Error: Source directory does not exist: {src_dir}")
        return

    os.makedirs(dest_dir, exist_ok=True)

    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None

    if target_date:
        parsed_target = parse_date_str(target_date)
        if parsed_target:
            start_dt = parsed_target
            end_dt = parsed_target

    if start_date:
        parsed_start = parse_date_str(start_date)
        if parsed_start:
            start_dt = parsed_start

    if end_date:
        parsed_end = parse_date_str(end_date)
        if parsed_end:
            end_dt = parsed_end
    
    print(f"Searching for files in: {src_dir}")
    print(f"Copying to: {dest_dir}")
    if start_dt and end_dt and start_dt == end_dt:
        print(f"Filtering for date: {start_dt.strftime('%Y-%m-%d')}")
    elif start_dt or end_dt:
        start_str = start_dt.strftime('%Y-%m-%d') if start_dt else "Beginning"
        end_str = end_dt.strftime('%Y-%m-%d') if end_dt else "End"
        print(f"Filtering for timeframe: {start_str} to {end_str} (inclusive)")
    print("-" * 48)

    # Use pathlib to find files recursively, then strictly filter with regex
    src_path = Path(src_dir)
    potential_files = src_path.rglob("Song_*.wav")
    
    pattern = re.compile(r"^Song_\d+_")
    matched_files = [f for f in potential_files if pattern.match(f.name)]

    has_date_filter = (start_dt is not None) or (end_dt is not None)
    if has_date_filter:
        filtered_files = []
        for f in matched_files:
            file_dt = extract_date_from_file(f, src_path)
            if file_dt is None:
                continue
            if start_dt and file_dt < start_dt:
                continue
            if end_dt and file_dt > end_dt:
                continue
            filtered_files.append(f)
        matched_files = filtered_files
    
    if not matched_files:
        if has_date_filter:
            print("No matching 'Song_XX_*.wav' files found for the specified date(s).")
        else:
            print("No matching 'Song_XX_*.wav' files found.")
        return

    # Sort files chronologically: by parent directory, then track number, then filename
    def get_sort_key(p: Path):
        m = re.match(r"^Song_(\d+)_", p.name)
        track_num = int(m.group(1)) if m else 0
        return (str(p.parent), track_num, p.name)

    matched_files.sort(key=get_sort_key)

    copied_count = 0
    clean_name_counts: Dict[str, int] = {}

    for file_path in matched_files:
        base_name = file_path.name
        
        # Strip the 'Song_XX_' prefix
        raw_clean_name = pattern.sub("", base_name)
        
        # Track occurrence index for duplicate titles in this service/batch
        clean_name_counts[raw_clean_name] = clean_name_counts.get(raw_clean_name, 0) + 1
        occurrence_idx = clean_name_counts[raw_clean_name]

        new_name = format_duplicate_song_name(raw_clean_name, occurrence_idx)
        dest_path = os.path.join(dest_dir, new_name)
        
        # Copy without overwriting
        if not os.path.exists(dest_path):
            shutil.copy2(file_path, dest_path)
            print(f"Copied: {base_name} -> {new_name}")
            copied_count += 1
        else:
            print(f"Skipped (already exists): {new_name}")

    print("-" * 48)
    print(f"Done! Copied {copied_count} new files.")
