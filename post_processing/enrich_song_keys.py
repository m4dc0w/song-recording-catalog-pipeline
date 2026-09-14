from __future__ import annotations

import os
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Union, Any

from dotenv import load_dotenv

from core.schemas import Song, ServiceType
from core.helpers import (
    filename_to_song,
    song_to_filename,
    find_matching_song,
    extract_key_from_song,
)
from post_processing.copy_songs import parse_date_str
from data_sources.planning_center import (
    PlanningCenterProvider,
    PlanningCenterKeyProvider,
    fetch_songs_for_date,
)

# Load environment variables
load_dotenv()


def enrich_song_keys(
    directories: Union[str, Path, List[Union[str, Path]]],
    target_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    service_type_id: Optional[str] = None,
    dry_run: bool = False,
    key_provider: Optional[Any] = None,
    extensions: Optional[List[str]] = None,
) -> List[Tuple[str, str]]:
    """Inspects media files in the given directory/directories, deserializes filenames
    into Song dataclasses, looks up the song key in Planning Center via exact or heuristic
    matching, and serializes the new filename enriched with the song's musical key:
    
        '<Title> - <Date>.<ext>' -> '<Title> - <Key> - <Date>.<ext>'
        
    Args:
        directories: A directory path or list of directory paths containing media files.
        target_date: Optional specific service date (YYYY-MM-DD) to process.
        start_date: Optional start date (YYYY-MM-DD) for a date range.
        end_date: Optional end date (YYYY-MM-DD) for a date range.
        service_type_id: Optional Planning Center Service Type ID override.
        dry_run: If True, previews renaming actions without touching files on disk.
        key_provider: Optional custom or mock key provider instance.
        extensions: Allowed file extensions (default: ['.mp3', '.mp4', '.wav']).
        
    Returns:
        List[Tuple[str, str]]: List of (old_filepath, new_filepath) pairs for all enriched files.
    """
    if isinstance(directories, (str, Path)):
        dirs = [Path(directories)]
    else:
        dirs = [Path(d) for d in directories]

    if extensions is None:
        extensions = [".mp3", ".mp4", ".wav"]
    allowed_exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}

    target_dt = parse_date_str(target_date)
    start_dt = parse_date_str(start_date)
    end_dt = parse_date_str(end_date)

    provider = key_provider or PlanningCenterKeyProvider(service_type_id=service_type_id)
    renamed_pairs: List[Tuple[str, str]] = []

    print(f"\n🎵 Starting Song Key Enrichment...")
    if dry_run:
        print("🔍 DRY-RUN MODE: No files will be modified on disk.")
    if target_date:
        print(f"📅 Filtering for date: {target_date}")
    elif start_date and end_date:
        print(f"📅 Filtering for timeframe: {start_date} to {end_date} (inclusive)")
    print("=" * 60)

    for dir_path in dirs:
        if not dir_path.exists():
            print(f"⚠️ Directory does not exist, skipping: {dir_path}")
            continue

        print(f"\n📂 Scanning directory: {dir_path}")
        files = sorted(os.listdir(dir_path))
        media_files = [f for f in files if Path(f).suffix.lower() in allowed_exts]

        if not media_files:
            print(f"  No supported media files found in {dir_path}.")
            continue

        for filename in media_files:
            old_path = dir_path / filename
            song = filename_to_song(filename)

            if song is None or not song.date:
                # File does not adhere to '<Title> - <Date>' convention
                continue

            # Check date filtering
            song_dt = parse_date_str(song.date)
            if target_dt is not None:
                if song_dt is None or song_dt.date() != target_dt.date():
                    continue
            elif start_dt is not None and end_dt is not None:
                if song_dt is None or not (start_dt.date() <= song_dt.date() <= end_dt.date()):
                    continue

            # Check if key is already present in filename
            if song.key:
                print(f"  ⏭️ Skipping (already has key '{song.key}'): {filename}")
                continue

            # Query Planning Center for songs on this date
            pco_songs = provider.get_songs_for_date(song.date)
            if not pco_songs:
                print(f"  ⚠️ No Planning Center songs found for date {song.date}: {filename}")
                continue

            # Perform exact or heuristic fuzzy match
            matched_song = find_matching_song(song.title, pco_songs)
            if not matched_song:
                print(f"  ❌ No matching song found in Planning Center setlist for '{song.title}' ({song.date})")
                continue

            # Extract key from matching song
            key = extract_key_from_song(matched_song)
            if not key:
                print(f"  ⚠️ Match found ('{matched_song.title}'), but no key information recorded in Planning Center.")
                continue

            # Create enriched filename
            song.key = key
            new_filename = song_to_filename(song, ext=old_path.suffix)
            new_path = dir_path / new_filename

            if new_path == old_path:
                continue

            if new_path.exists():
                print(f"  ⚠️ Target file already exists, skipping: {new_filename}")
                continue

            if not dry_run:
                try:
                    os.rename(old_path, new_path)
                    print(f"  ✅ Renamed: {filename} ➔ {new_filename}")
                except OSError as e:
                    print(f"  ❌ Error renaming {filename} to {new_filename}: {e}")
                    continue
            else:
                print(f"  [DRY RUN] Would rename: {filename} ➔ {new_filename}")

            renamed_pairs.append((str(old_path), str(new_path)))

    print("\n" + "=" * 60)
    action_verb = "Identified for renaming" if dry_run else "Successfully enriched and renamed"
    print(f"🎉 Enrichment Complete: {action_verb} {len(renamed_pairs)} file(s).")
    print("=" * 60)

    return renamed_pairs


def main(args: Optional[List[str]] = None) -> None:
    """CLI entry point for enriching audio and video files with musical keys."""
    parser = argparse.ArgumentParser(
        description="Enrich audio/video filenames with musical key information from Planning Center."
    )
    parser.add_argument(
        "--dir", "--directory",
        dest="directories",
        action="append",
        help="Target directory containing media files. Can be specified multiple times."
    )
    parser.add_argument(
        "--date",
        dest="target_date",
        default=None,
        help="Filter files for a specific service date (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--start-date",
        dest="start_date",
        default=None,
        help="Start date (YYYY-MM-DD) for a date range filter."
    )
    parser.add_argument(
        "--end-date",
        dest="end_date",
        default=None,
        help="End date (YYYY-MM-DD) for a date range filter."
    )
    parser.add_argument(
        "--service-type",
        dest="service_type_id",
        default=None,
        help="Planning Center Service Type ID (defaults to PCO_SERVICE_TYPE_ID in .env)."
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Preview filenames that would be renamed without modifying files on disk."
    )

    parsed_args = parser.parse_args(args)

    # Resolve default directories if none passed
    target_dirs = parsed_args.directories
    if not target_dirs:
        verified_dir = os.getenv("VERIFIED_AUDIO_DIR", os.path.join(os.getcwd(), "verified_audio"))
        mp3_dir = os.getenv("MP3_DIR", os.path.join(verified_dir, "MP3"))
        videos_dir = os.getenv("VIDEOS_DIR", os.path.join(verified_dir, "Videos"))
        
        candidates = [verified_dir, mp3_dir, videos_dir]
        target_dirs = [d for d in candidates if os.path.exists(d)]

        if not target_dirs:
            print("❌ Error: No target directories specified and default directories do not exist.")
            return

    enrich_song_keys(
        directories=target_dirs,
        target_date=parsed_args.target_date,
        start_date=parsed_args.start_date,
        end_date=parsed_args.end_date,
        service_type_id=parsed_args.service_type_id,
        dry_run=parsed_args.dry_run,
    )


if __name__ == "__main__":
    main()
