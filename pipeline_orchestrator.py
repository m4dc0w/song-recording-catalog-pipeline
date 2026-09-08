from __future__ import annotations

import os
import sys
import argparse
from datetime import datetime
from typing import Tuple, Optional, List
from dotenv import load_dotenv

from data_sources.planning_center import fetch_service_plan, fetch_recent_plans, fetch_service_types
from data_sources.local_drive import discover_raw_audio
from audio_segmentation.audio_segmentation import segment_service_audio
from post_processing.copy_songs import copy_songs
from post_processing.move_songs import move_songs
from post_processing.make_videos import make_videos

# Load environment variables
load_dotenv()

# Configure fallbacks
RAW_AUDIO_DIR: str = os.getenv("RAW_AUDIO_DIR", os.path.join(os.getcwd(), "raw_audio"))
PROCESSED_AUDIO_DIR: str = os.getenv("PROCESSED_AUDIO_DIR", os.path.join(os.getcwd(), "processed_audio"))
STAGING_AUDIO_DIR: str = os.getenv("STAGING_AUDIO_DIR", os.path.join(os.getcwd(), "staging_audio"))
VERIFIED_AUDIO_DIR: str = os.getenv("VERIFIED_AUDIO_DIR", os.path.join(os.getcwd(), "verified_audio"))
VIDEOS_DIR: str = os.getenv("VIDEOS_DIR", os.path.join(VERIFIED_AUDIO_DIR, "Videos"))
DEFAULT_SERVICE_TYPE: str = os.getenv("PCO_SERVICE_TYPE_ID", "")
FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", "ffmpeg")


def prompt_for_service_type() -> str:
    """Provides an interactive CLI menu to select a Service Type if not provided in .env."""
    service_types = fetch_service_types()
    
    if not service_types:
        print("❌ No Service Types found for this Planning Center account.")
        sys.exit(1)
        
    print("\n📋 Planning Center Service Types:")
    print("-" * 40)
    for idx, st in enumerate(service_types, start=1):
        print(f"  [{idx}] {st.name}")
    print("-" * 40)
    
    while True:
        try:
            choice = input(f"Select a service type [1-{len(service_types)}]: ")
            selected_idx = int(choice) - 1
            
            if 0 <= selected_idx < len(service_types):
                return service_types[selected_idx].id
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")


def prompt_for_date_filter(
    title: str = "Date Filter for Post-Processing",
    all_label: str = "all songs"
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Prompts the user for date filtering options during post-processing.
    
    Returns:
        tuple[Optional[str], Optional[str], Optional[str]]:
            (target_date, start_date, end_date)
    """
    print(f"\n📅 {title}:")
    print("-" * 40)
    print("  [1] Single service date (YYYY-MM-DD)")
    print("  [2] Date range (Start Date & End Date)")
    print(f"  [3] All dates ({all_label})")
    print("-" * 40)
    while True:
        try:
            choice = input("Select an option [1-3] (Default: 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            sys.exit(0)
            
        if choice in ("", "1"):
            while True:
                try:
                    date_str = input("Enter service date (YYYY-MM-DD): ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nOperation cancelled.")
                    sys.exit(0)
                try:
                    datetime.strptime(date_str, "%Y-%m-%d")
                    return date_str, None, None
                except ValueError:
                    print(f"❌ Error: Invalid date format: '{date_str}'. Expected YYYY-MM-DD. Please try again.")
        elif choice == "2":
            while True:
                try:
                    start_str = input("Start Date (YYYY-MM-DD): ").strip()
                    end_str = input("End Date (YYYY-MM-DD): ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nOperation cancelled.")
                    sys.exit(0)
                try:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_str, "%Y-%m-%d")
                    if start_dt > end_dt:
                        print("❌ Error: Start date must be before or equal to end date. Please try again.")
                        continue
                    return None, start_str, end_str
                except ValueError:
                    print("❌ Error: Invalid date format. Expected YYYY-MM-DD. Please try again.")
        elif choice in ("3", "all", "a"):
            return None, None, None
        else:
            try:
                datetime.strptime(choice, "%Y-%m-%d")
                return choice, None, None
            except ValueError:
                print("Invalid selection. Please enter 1, 2, 3, or a valid YYYY-MM-DD date.")


def prompt_for_plan(service_type_id: str) -> tuple[str, str]:
    """Provides an interactive CLI menu to select a recent Planning Center plan.
    
    Returns:
        tuple[str, str]: The selected (plan_id, service_date)
    """
    plans = fetch_recent_plans(service_type_id, limit=5)
    
    if not plans:
        print("❌ No recent plans found for this Service Type.")
        sys.exit(1)
        
    print("\n📋 Recent Planning Center Services:")
    print("-" * 40)
    for idx, plan in enumerate(plans, start=1):
        title_str = f" - {plan.title}" if plan.title else ""
        print(f"  [{idx}] {plan.dates}{title_str}")
    print("-" * 40)
    
    while True:
        try:
            choice = input(f"Select a service [1-{len(plans)}]: ")
            selected_idx = int(choice) - 1
            
            if 0 <= selected_idx < len(plans):
                selected = plans[selected_idx]
                
                try:
                    parsed_date = datetime.strptime(selected.dates, "%B %d, %Y")
                    formatted_date = parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    print("⚠️ Note: Could not parse exact YYYY-MM-DD from PCO date string. Using today's date for output folder.")
                    formatted_date = datetime.now().strftime("%Y-%m-%d")
                    
                return selected.id, formatted_date
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")


def main(cli_args: Optional[List[str]] = None) -> None:
    """Executes the master pipeline orchestration loop."""
    parser = argparse.ArgumentParser(description="Song Recording Catalog Pipeline Orchestrator.")
    
    parser.add_argument(
        "--service-type", 
        default=DEFAULT_SERVICE_TYPE, 
        help="PCO Service Type ID. Defaults to PCO_SERVICE_TYPE_ID in .env."
    )
    parser.add_argument(
        "--plan-id", 
        help="Bypass interactive menu by providing a specific Plan ID."
    )
    parser.add_argument(
        "--date", 
        help="Service date (YYYY-MM-DD). Required if --plan-id is provided manually."
    )
    parser.add_argument(
        "--audio-file", 
        help="Optional specific filename of the raw .wav recording inside RAW_AUDIO_DIR. If omitted, automatic date matching and file stitching is used."
    )
    
    # Post-Processing Arguments
    parser.add_argument(
        "--start-date",
        help="Optional start date (YYYY-MM-DD) to filter songs during post-processing."
    )
    parser.add_argument(
        "--end-date",
        help="Optional end date (YYYY-MM-DD) to filter songs during post-processing."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all songs across all dates without prompting for date filtering during post-processing."
    )
    parser.add_argument(
        "--publish-staging",
        action="store_true",
        help="Run post-processing to copy and stage songs from the processed directory to the staging directory (prompts for dates if omitted)."
    )
    parser.add_argument(
        "--publish-verified",
        action="store_true",
        help="Run post-processing to move verified songs from the staging directory to the verified directory (prompts for dates if omitted)."
    )
    parser.add_argument(
        "--make-videos",
        action="store_true",
        help="Run post-processing to generate MP4 videos from the verified audio recordings (prompts for dates if omitted)."
    )
    parser.add_argument(
        "--skip-post-processing",
        action="store_true",
        help="Skip post-processing (publishing and video generation) when running the interactive pipeline."
    )
    
    if cli_args is not None:
        args = parser.parse_args(cli_args)
        args_len = len(cli_args)
    else:
        args = parser.parse_args()
        args_len = len(sys.argv) - 1

    # If no CLI arguments were passed (args length is zero), default to running the full
    # end-to-end pipeline including post-processing (staging, moving to verified, and video generation).
    has_post_processing_flags = args.publish_staging or args.publish_verified or args.make_videos
    if args_len == 0:
        args.publish_staging = True
        args.publish_verified = True
        args.make_videos = True
        run_main_pipeline = True
    else:
        # We only prompt for service type / run the main pipeline if not in standalone post-processing mode
        run_main_pipeline = not has_post_processing_flags or bool(args.plan_id or args.audio_file)

    if (args.start_date and not args.end_date) or (args.end_date and not args.start_date):
        print("❌ Error: Both --start-date and --end-date must be provided together.")
        return

    if args.start_date and args.end_date:
        try:
            s_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(args.end_date, "%Y-%m-%d")
            if s_dt > e_dt:
                print("❌ Error: --start-date must be before or equal to --end-date.")
                return
        except ValueError as e:
            print(f"❌ Error: Invalid date format: {e}. Expected YYYY-MM-DD.")
            return

    if args.date:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError as e:
            print(f"❌ Error: Invalid date format for --date: {e}. Expected YYYY-MM-DD.")
            return

    # Determine Service Type (CLI -> .env -> Interactive Menu)
    service_type = args.service_type
    
    if run_main_pipeline and not service_type:
        print("\n🔍 No Service Type ID provided in .env or arguments. Let's find it...")
        service_type = prompt_for_service_type()

    print("\n🚀 Starting Pipeline Orchestrator...")
    print("=" * 50)
    
    target_date = args.date
    target_plan_id = args.plan_id

    try:
        if run_main_pipeline:
            # 1. Resolve Plan ID and Date (Interactive Menu or CLI Flags)
            if args.plan_id and args.date:
                target_plan_id = args.plan_id
                target_date = args.date
            elif args.plan_id or (args.date and not has_post_processing_flags):
                print("❌ Error: Both --plan-id and --date must be provided together if bypassing the menu.")
                return
            else:
                target_plan_id, target_date = prompt_for_plan(service_type)
                
            print(f"\n✅ Target Date locked: {target_date}")
            print("=" * 50)
    
            # 2. Fetch the specific setlist from Planning Center
            plan = fetch_service_plan(service_type, target_plan_id, target_date)
            
            # 3. Handle raw audio filepath binding (Optional CLI override vs Automated Discovery)
            raw_audio_files = []
            if args.audio_file:
                raw_audio_path = os.path.join(RAW_AUDIO_DIR, args.audio_file)
                if not os.path.exists(raw_audio_path):
                    if not os.path.exists(RAW_AUDIO_DIR):
                        print(f"❌ Error: RAW_AUDIO_DIR directory does not exist: {RAW_AUDIO_DIR}")
                        print("Please check your .env file and verify the path (e.g. check for typos in your username or Google Drive mount).")
                    else:
                        print(f"❌ Error: Raw audio file '{args.audio_file}' not found in {RAW_AUDIO_DIR}")
                    return
                raw_audio_files = [raw_audio_path]
            else:
                print("🔍 Automatically discovering raw audio files for the service date...")
                try:
                    discovered_paths = discover_raw_audio(target_date, RAW_AUDIO_DIR)
                except FileNotFoundError:
                    print(f"❌ Error: RAW_AUDIO_DIR directory does not exist: {RAW_AUDIO_DIR}")
                    print("Please check your .env file and verify the path (e.g. check for typos in your username or Google Drive mount).")
                    return

                if discovered_paths:
                    print(f"✅ Found {len(discovered_paths)} matching raw audio file(s).")
                    raw_audio_files = discovered_paths
                else:
                    print(f"❌ Error: Could not find any raw audio files matching '{target_date}' in {RAW_AUDIO_DIR}.")
                    print("The directory exists, but contains no .wav files for this date.")
                    print("Please verify the service date or provide an audio file manually using the --audio-file argument.")
                    return
            
            # 4. Hand off execution to the audio segmentation worker (which auto-discovers/stitches if filepath is empty)
            for audio_path in raw_audio_files:
                plan.raw_audio_filepath = audio_path
                print(f"\n🎧 Processing: {os.path.basename(audio_path)}")
                try:
                    segment_service_audio(plan)
                except FileExistsError as fe:
                    print(f"\n⚠️ Skipping Audio Segmentation for {os.path.basename(audio_path)}: {fe}")
                    print("To re-run, delete or move the existing destination folder.")
                    print("Exiting pipeline to avoid accidentally publishing verified songs.")
                    return
        
        # Initialize post-processing date filters from CLI args or locked target_date
        post_proc_target_date = target_date
        post_proc_start_date = args.start_date
        post_proc_end_date = args.end_date
        post_proc_all = getattr(args, 'all', False)

        def resolve_post_proc_dates(title: str, all_label: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
            nonlocal post_proc_target_date, post_proc_start_date, post_proc_end_date, post_proc_all
            if (
                not post_proc_target_date 
                and not post_proc_start_date 
                and not post_proc_end_date 
                and not post_proc_all
            ):
                post_proc_target_date, post_proc_start_date, post_proc_end_date = prompt_for_date_filter(
                    title=title,
                    all_label=all_label
                )
                if not post_proc_target_date and not post_proc_start_date and not post_proc_end_date:
                    post_proc_all = True
            return post_proc_target_date, post_proc_start_date, post_proc_end_date

        # 5. Post-Processing: Stage Songs
        if args.publish_staging:
            print("\n" + "=" * 50)
            print("📦 Post-Processing: Staging Songs")
            print("=" * 50)
            
            p_target, p_start, p_end = resolve_post_proc_dates(
                title="Date Filter for Staging Songs",
                all_label="stage all songs"
            )

            # Copy to staging directory (scoped to target date or timeframe if provided)
            copy_songs(
                PROCESSED_AUDIO_DIR, 
                STAGING_AUDIO_DIR, 
                target_date=p_target, 
                start_date=p_start, 
                end_date=p_end
            )
            print(f"\n🎧 Songs have been successfully staged in: {STAGING_AUDIO_DIR}")

        # 6. Post-Processing: Publish Verified Songs
        if args.publish_verified:
            print("\n" + "=" * 50)
            print("🚚 Post-Processing: Publishing Verified Songs")
            print("=" * 50)
            
            p_target, p_start, p_end = resolve_post_proc_dates(
                title="Date Filter for Publishing Verified Songs",
                all_label="move all verified songs"
            )

            choice = input("Have you verified the recordings are good enough to move to the VERIFIED_AUDIO_DIR? (y/n): ")
            
            if choice.strip().lower() == 'y':
                print("\n🚚 Moving songs to verified directory...")
                move_songs(
                    STAGING_AUDIO_DIR, 
                    VERIFIED_AUDIO_DIR,
                    target_date=p_target,
                    start_date=p_start,
                    end_date=p_end
                )
            else:
                print("\n⏸️ Skipping move to verified directory. They remain in staging.")
                print("Exiting pipeline to allow audio verification before generating videos.")
                return
            
        # 7. Post-Processing: Generate Videos
        if args.make_videos:
            print("\n" + "=" * 50)
            print("🎬 Post-Processing: Generating Videos")
            print("=" * 50)
            
            p_target, p_start, p_end = resolve_post_proc_dates(
                title="Date Filter for Video Generation",
                all_label="generate videos for all songs"
            )

            make_videos(
                VERIFIED_AUDIO_DIR, 
                VIDEOS_DIR, 
                ffmpeg_path=FFMPEG_PATH,
                target_date=p_target,
                start_date=p_start,
                end_date=p_end
            )
            
        print("\n🎉 Pipeline completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")


if __name__ == "__main__":
    main()
