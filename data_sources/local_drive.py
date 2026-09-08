from pathlib import Path
from typing import List

def discover_raw_audio(target_date: str, raw_audio_dir: str) -> List[str]:
    """
    Discovers all raw audio files in the specified directory matching the target date.
    Assumes filenames contain the date in YYYYMMDD format (e.g., R_20260906-103109.wav).
    
    Args:
        target_date (str): The date to search for in 'YYYY-MM-DD' format.
        raw_audio_dir (str): The path to the directory containing raw audio files.
        
    Returns:
        List[str]: A list of absolute paths to the matching raw audio files, or empty list if not found.
    """
    raw_path = Path(raw_audio_dir)
    if not raw_path.exists() or not raw_path.is_dir():
        return []

    # Strip hyphens to match the YYYYMMDD format in the filename
    date_str = target_date.replace("-", "")
    
    # Iterate directory entries directly without globbing on the parent path,
    # ensuring directory names with square brackets like '[Raw]' are treated literally.
    matching_files = [
        str(p) for p in raw_path.iterdir()
        if p.is_file() and date_str in p.name and p.suffix.lower() == ".wav"
    ]
    
    matching_files.sort()
    return matching_files

