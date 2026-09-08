import os
import shutil
from pathlib import Path

def move_songs(src_dir: str, dest_dir: str) -> None:
    """
    Moves all .wav files from the staging source directory to the verified destination directory.
    Prevents overwriting existing files in the destination.
    """
    if not os.path.exists(src_dir):
        print(f"❌ Error: Source directory does not exist: {src_dir}")
        return

    os.makedirs(dest_dir, exist_ok=True)
    
    print(f"Searching for files in: {src_dir}")
    print(f"Moving to: {dest_dir}")
    print("-" * 48)

    src_path = Path(src_dir)
    matched_files = list(src_path.glob("*.wav"))
    
    if not matched_files:
        print("No matching '.wav' files found in staging directory.")
        return

    moved_count = 0

    for file_path in matched_files:
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
