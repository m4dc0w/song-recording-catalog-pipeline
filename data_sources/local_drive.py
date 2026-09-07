import os
import glob
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
    if not os.path.exists(raw_audio_dir):
        return []

    # Strip hyphens to match the YYYYMMDD format in the filename
    date_str = target_date.replace("-", "")
    
    # Look for any .wav file containing this date string
    pattern = os.path.join(raw_audio_dir, f"*{date_str}*.wav")
    matching_files = glob.glob(pattern)
    
    if not matching_files:
        return []
        
    # Sort files to ensure deterministic behavior if multiple files exist for the same day
    matching_files.sort()
    
    return matching_files
