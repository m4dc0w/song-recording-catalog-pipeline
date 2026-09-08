import os
import glob
import shutil
import re

def copy_verified_songs(src_dir: str, dest_dir: str) -> None:
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

    # Use glob to find all matching files recursively
    # glob with recursive=True requires **
    search_pattern = os.path.join(src_dir, "**", "Song_\d+_*.wav")
    matched_files = glob.glob(search_pattern, recursive=True)
    
    if not matched_files:
        print("No matching 'Song_XX_*.wav' files found.")
        return

    copied_count = 0
    pattern = re.compile(r"^Song_\d+_")

    for file_path in matched_files:
        base_name = os.path.basename(file_path)
        
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
