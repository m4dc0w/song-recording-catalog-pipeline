import os
import shutil
import re
from pathlib import Path

def copy_songs(src_dir: str, dest_dir: str) -> None:
    """
    Finds all 'Song_XX_*.wav' files in the source directory (recursively),
    strips the 'Song_XX_' prefix, and copies them to the destination directory.
    Prevents overwriting existing files in the destination.
    """
    if not os.path.exists(src_dir):
        print(f"❌ Error: Source directory does not exist: {src_dir}")
        return

    os.makedirs(dest_dir, exist_ok=True)
    
    print(f"Searching for files in: {src_dir}")
    print(f"Copying to: {dest_dir}")
    print("-" * 48)

    # Use pathlib to find files recursively, then strictly filter with regex
    src_path = Path(src_dir)
    potential_files = src_path.rglob("Song_*.wav")
    
    pattern = re.compile(r"^Song_\d+_")
    matched_files = [f for f in potential_files if pattern.match(f.name)]
    
    if not matched_files:
        print("No matching 'Song_XX_*.wav' files found.")
        return

    copied_count = 0

    for file_path in matched_files:
        base_name = file_path.name
        
        # Strip the prefix
        new_name = pattern.sub("", base_name)
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
