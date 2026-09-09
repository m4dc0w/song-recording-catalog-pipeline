from __future__ import annotations

import os
import sys
import argparse
import time
from datetime import datetime
from typing import Tuple, Optional, List

from data_sources.planning_center import (
    fetch_recent_plans, 
    fetch_service_plan, 
    parse_pco_plan_date
)
from data_sources.local_drive import discover_raw_audio
from audio_segmentation.audio_segmentation import segment_service_audio
from pipeline_orchestrator import (
    prompt_for_service_type, 
    get_plan_date,
    DEFAULT_SERVICE_TYPE, 
    RAW_AUDIO_DIR,
    PROCESSED_AUDIO_DIR,
    STAGING_AUDIO_DIR,
    VERIFIED_AUDIO_DIR,
    VIDEOS_DIR,
    MP3_DIR,
    FFMPEG_PATH
)
from post_processing.copy_songs import copy_songs
from post_processing.move_songs import move_songs
from post_processing.make_videos import make_videos
from post_processing.make_mp3 import make_mp3

def parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")

def prompt_for_dates() -> Tuple[str, str]:
    print("\n📅 Enter Timeframe for Backfill (YYYY-MM-DD):")
    print("-" * 40)
    while True:
        try:
            start_date = input("Start Date: ")
            end_date = input("End Date: ")
            parse_date(start_date)
            parse_date(end_date)
            return start_date, end_date
        except ValueError as e:
            print(f"Error: {e}. Please try again.")

def parse_pco_date(pco_date_str: str) -> Optional[datetime]:
    """Parses a PCO date string into a datetime object using parse_pco_plan_date."""
    iso_date = parse_pco_plan_date(pco_date_str)
    if iso_date:
        try:
            return datetime.strptime(iso_date, "%Y-%m-%d")
        except ValueError:
            return None
    return None

def main(cli_args: Optional[List[str]] = None) -> None:
    """Executes the backfill pipeline orchestration loop."""
    parser = argparse.ArgumentParser(description="Song Recording Catalog Pipeline - Backfill Orchestrator.")
    
    parser.add_argument(
        "--service-type", 
        default=DEFAULT_SERVICE_TYPE, 
        help="PCO Service Type ID. Defaults to PCO_SERVICE_TYPE_ID in .env."
    )
    parser.add_argument(
        "--start-date", 
        help="Start date for backfill (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--end-date", 
        help="End date for backfill (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of historical plans to fetch from PCO before filtering (Default: 100)."
    )
    parser.add_argument(
        "--publish-staging",
        action="store_true",
        help="Run post-processing to copy and stage songs from the processed directory to the staging directory for the backfill timeframe."
    )
    parser.add_argument(
        "--publish-verified",
        action="store_true",
        help="Run post-processing to move verified songs from the staging directory to the verified directory."
    )
    parser.add_argument(
        "--make-videos",
        action="store_true",
        help="Run post-processing to generate MP4 videos from the verified audio recordings."
    )
    parser.add_argument(
        "--make-mp3",
        action="store_true",
        help="Run post-processing to generate high-quality MP3 audio files from the verified recordings."
    )
    parser.add_argument(
        "--skip-post-processing",
        action="store_true",
        help="Skip post-processing after backfill."
    )
    parser.add_argument(
        "--post-processing-only",
        action="store_true",
        help="Skip fetching plans and audio segmentation, running only post-processing for the specified backfill timeframe."
    )
    
    if cli_args is not None:
        args = parser.parse_args(cli_args)
    else:
        args = parser.parse_args()

    publish_staging = bool(isinstance(getattr(args, 'publish_staging', False), bool) and args.publish_staging)
    publish_verified = bool(isinstance(getattr(args, 'publish_verified', False), bool) and args.publish_verified)
    make_videos_flag = bool(isinstance(getattr(args, 'make_videos', False), bool) and args.make_videos)
    make_mp3_flag = bool(isinstance(getattr(args, 'make_mp3', False), bool) and args.make_mp3)
    skip_post_processing = bool(isinstance(getattr(args, 'skip_post_processing', False), bool) and args.skip_post_processing)
    post_processing_only = bool(isinstance(getattr(args, 'post_processing_only', False), bool) and args.post_processing_only)

    if skip_post_processing:
        publish_staging = False
        publish_verified = False
        make_videos_flag = False
        make_mp3_flag = False

    service_type = getattr(args, 'service_type', None)
    if not service_type and not post_processing_only:
        print("\n🔍 No Service Type ID provided in .env or arguments. Let's find it...")
        service_type = prompt_for_service_type()
        
    if getattr(args, 'start_date', None) and getattr(args, 'end_date', None):
        start_date_str = args.start_date
        end_date_str = args.end_date
        try:
            parse_date(start_date_str)
            parse_date(end_date_str)
        except ValueError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    elif getattr(args, 'start_date', None) or getattr(args, 'end_date', None):
        print("❌ Error: Both --start-date and --end-date must be provided if using CLI flags.")
        sys.exit(1)
    else:
        start_date_str, end_date_str = prompt_for_dates()
        
    start_dt = parse_date(start_date_str)
    end_dt = parse_date(end_date_str)

    # Standalone post-processing mode for a backfill timeframe
    if post_processing_only:
        print(f"\n🚀 Running Post-Processing Only for Backfill Timeframe ({start_date_str} to {end_date_str})...")
        print("=" * 60)
        if publish_staging:
            print("\n" + "=" * 60)
            print("📦 Post-Processing: Staging Songs (Backfill Scope)")
            print("=" * 60)
            copy_songs(
                PROCESSED_AUDIO_DIR, 
                STAGING_AUDIO_DIR, 
                start_date=start_date_str, 
                end_date=end_date_str
            )
            print(f"\n🎧 Songs have been successfully staged in: {STAGING_AUDIO_DIR}")

        if publish_verified:
            print("\n" + "=" * 60)
            print("🚚 Post-Processing: Publishing Verified Songs")
            print("=" * 60)
            choice = input("Have you verified the recordings are good enough to move to the VERIFIED_AUDIO_DIR? (y/n): ")
            if choice.strip().lower() == 'y':
                print("\n🚚 Moving songs to verified directory...")
                move_songs(
                    STAGING_AUDIO_DIR, 
                    VERIFIED_AUDIO_DIR,
                    start_date=start_date_str,
                    end_date=end_date_str
                )
            else:
                print("\n⏸️ Skipping move to verified directory. They remain in staging.")
                print("Exiting pipeline to allow audio verification before generating videos.")
                return

        if make_videos_flag:
            print("\n" + "=" * 60)
            print("🎬 Post-Processing: Generating Videos")
            print("=" * 60)
            make_videos(
                VERIFIED_AUDIO_DIR, 
                VIDEOS_DIR, 
                ffmpeg_path=FFMPEG_PATH,
                start_date=start_date_str,
                end_date=end_date_str
            )

        if make_mp3_flag:
            print("\n" + "=" * 60)
            print("🎵 Post-Processing: Generating MP3 Audio")
            print("=" * 60)
            make_mp3(
                VERIFIED_AUDIO_DIR, 
                MP3_DIR, 
                ffmpeg_path=FFMPEG_PATH,
                start_date=start_date_str,
                end_date=end_date_str
            )

        print("\n🎉 Post-processing completed successfully!")
        return

    print(f"\n🚀 Starting Backfill Orchestrator ({start_date_str} to {end_date_str})...")
    print("=" * 60)
    
    plans = fetch_recent_plans(
        service_type, 
        limit=args.limit,
        start_date=start_date_str,
        end_date=end_date_str
    )
    if not plans:
        print("❌ No recent plans found for this Service Type.")
        sys.exit(1)
        
    # Filter plans
    target_plans = []
    for plan in plans:
        plan_date = get_plan_date(plan)
        if plan_date:
            if start_date_str <= plan_date <= end_date_str:
                target_plans.append((plan, plan_date))
        else:
            display_date = getattr(plan, "dates_raw", None) or getattr(plan, "dates", "Unknown Date")
            print(f"⚠️ Warning: Could not parse date '{display_date}' for plan {plan.id}. Skipping.")
            
    print(f"✅ Found {len(target_plans)} plans matching the timeframe.")
    print("=" * 60)

    success_count = 0
    fail_count = 0
    failures = []

    for plan_summary, formatted_date in target_plans:
        print(f"\n📆 Processing Plan: {plan_summary.title or 'Untitled'} on {formatted_date}")
        try:
            # 1. Discover raw audio files
            try:
                discovered_paths = discover_raw_audio(formatted_date, RAW_AUDIO_DIR)
            except FileNotFoundError as e:
                print(f"  ❌ Error: RAW_AUDIO_DIR directory does not exist: {RAW_AUDIO_DIR}")
                print("  Please check your .env file and verify the path (e.g. check for typos in your username or Google Drive mount).")
                fail_count += 1
                failures.append(f"{formatted_date} - {e}")
                break

            if not discovered_paths:
                raise FileNotFoundError(f"No raw audio files found for {formatted_date} in {RAW_AUDIO_DIR}")
                
            # 2. Fetch specific setlist
            plan_details = fetch_service_plan(service_type, plan_summary.id, formatted_date)
            
            # 3. Process each found file
            for audio_path in discovered_paths:
                plan_details.raw_audio_filepath = audio_path
                print(f"  🎧 Segmenting: {os.path.basename(audio_path)}")
                try:
                    segment_service_audio(plan_details)
                except FileExistsError as fe:
                    print(f"  ⚠️ Skipping {os.path.basename(audio_path)}: Destination exists.")
                    
            success_count += 1
        except Exception as e:
            print(f"  ❌ Error processing {formatted_date}: {e}")
            fail_count += 1
            failures.append(f"{formatted_date} - {e}")
            
        print("  ⏳ Sleeping for 5 seconds to respect API rate limits...")
        time.sleep(5)
        
    print("\n" + "=" * 60)
    print("📊 BACKFILL SUMMARY REPORT")
    print("=" * 60)
    print(f"✅ Successfully processed: {success_count}")
    print(f"❌ Failed: {fail_count}")
    if fail_count > 0:
        print("\n📝 Failure Details:")
        for fail in failures:
            print(f"  - {fail}")

    if success_count > 0 and not (publish_staging or publish_verified or make_videos_flag):
        print("\n💡 Next Steps (Post-Processing):")
        print("To stage, verify, and generate videos for your segmented songs, run:")
        print(f"  python3 pipeline_orchestrator.py --publish-staging --start-date {start_date_str} --end-date {end_date_str} --publish-verified --make-videos")

    # Post-processing execution for the backfill timeframe (inclusive)
    if publish_staging:
        print("\n" + "=" * 60)
        print("📦 Post-Processing: Staging Songs (Backfill Scope)")
        print("=" * 60)
        copy_songs(
            PROCESSED_AUDIO_DIR, 
            STAGING_AUDIO_DIR, 
            start_date=start_date_str, 
            end_date=end_date_str
        )
        print(f"\n🎧 Songs have been successfully staged in: {STAGING_AUDIO_DIR}")

    if publish_verified:
        print("\n" + "=" * 60)
        print("🚚 Post-Processing: Publishing Verified Songs")
        print("=" * 60)
        choice = input("Have you verified the recordings are good enough to move to the VERIFIED_AUDIO_DIR? (y/n): ")
        if choice.strip().lower() == 'y':
            print("\n🚚 Moving songs to verified directory...")
            move_songs(
                STAGING_AUDIO_DIR, 
                VERIFIED_AUDIO_DIR,
                start_date=start_date_str,
                end_date=end_date_str
            )
        else:
            print("\n⏸️ Skipping move to verified directory. They remain in staging.")
            print("Exiting pipeline to allow audio verification before generating videos.")
            return

    if make_videos_flag:
        print("\n" + "=" * 60)
        print("🎬 Post-Processing: Generating Videos")
        print("=" * 60)
        make_videos(
            VERIFIED_AUDIO_DIR, 
            VIDEOS_DIR, 
            ffmpeg_path=FFMPEG_PATH,
            start_date=start_date_str,
            end_date=end_date_str
        )

    if make_mp3_flag:
        print("\n" + "=" * 60)
        print("🎵 Post-Processing: Generating MP3 Audio")
        print("=" * 60)
        make_mp3(
            VERIFIED_AUDIO_DIR, 
            MP3_DIR, 
            ffmpeg_path=FFMPEG_PATH,
            start_date=start_date_str,
            end_date=end_date_str
        )
            
if __name__ == "__main__":
    main()
