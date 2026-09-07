import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

from data_sources.planning_center import fetch_service_plan, fetch_recent_plans
from data_sources.local_drive import discover_raw_audio
from audio_segmentation.audio_segmentation import segment_service_audio
from post_processing.copy_songs import copy_verified_songs
from post_processing.make_videos import make_videos

# Load environment variables
load_dotenv()

# Configure fallbacks
RAW_AUDIO_DIR: str = os.getenv("RAW_AUDIO_DIR", os.path.join(os.getcwd(), "raw_audio"))
PROCESSED_AUDIO_DIR: str = os.getenv("PROCESSED_AUDIO_DIR", os.path.join(os.getcwd(), "processed_audio"))
VERIFIED_AUDIO_DIR: str = os.getenv("VERIFIED_AUDIO_DIR", os.path.join(os.getcwd(), "verified_audio"))
VIDEOS_DIR: str = os.getenv("VIDEOS_DIR", os.path.join(VERIFIED_AUDIO_DIR, "Videos"))
DEFAULT_SERVICE_TYPE: str = os.getenv("PCO_SERVICE_TYPE_ID", "")
FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", "ffmpeg")


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


def main() -> None:
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
        "--publish-verified",
        action="store_true",
        help="Run post-processing to copy verified songs from the processed directory to the verified directory."
    )
    parser.add_argument(
        "--make-videos",
        action="store_true",
        help="Run post-processing to generate MP4 videos from the verified audio recordings."
    )
    
    args = parser.parse_args()

    if not args.service_type:
        print("❌ Error: --service-type not provided and PCO_SERVICE_TYPE_ID is missing from .env.")
        return

    print("\n🚀 Starting Pipeline Orchestrator...")
    print("=" * 50)
    
    try:
        # Check if we should run the main segmentation pipeline
        # (Run it if no post-processing flags are set, or if they explicitly provided plan arguments)
        run_main_pipeline = not (args.publish_verified or args.make_videos) or args.plan_id or args.date or args.audio_file
        
        if run_main_pipeline:
            # 1. Resolve Plan ID and Date (Interactive Menu or CLI Flags)
            if args.plan_id and args.date:
                target_plan_id = args.plan_id
                target_date = args.date
            elif args.plan_id or args.date:
                print("❌ Error: Both --plan-id and --date must be provided together if bypassing the menu.")
                return
            else:
                target_plan_id, target_date = prompt_for_plan(args.service_type)
                
            print(f"\n✅ Target Date locked: {target_date}")
            print("=" * 50)
    
            # 2. Fetch the specific setlist from Planning Center
            plan = fetch_service_plan(args.service_type, target_plan_id, target_date)
            
            # 3. Handle raw audio filepath binding (Optional CLI override vs Automated Discovery)
            raw_audio_files = []
            if args.audio_file:
                raw_audio_path = os.path.join(RAW_AUDIO_DIR, args.audio_file)
                if not os.path.exists(raw_audio_path):
                    print(f"❌ Error: Raw audio file not found at {raw_audio_path}")
                    return
                raw_audio_files = [raw_audio_path]
            else:
                print("🔍 Automatically discovering raw audio files for the service date...")
                discovered_paths = discover_raw_audio(target_date, RAW_AUDIO_DIR)
                if discovered_paths:
                    print(f"✅ Found {len(discovered_paths)} matching raw audio file(s).")
                    raw_audio_files = discovered_paths
                else:
                    print(f"❌ Error: Could not automatically find any raw audio files for {target_date} in {RAW_AUDIO_DIR}.")
                    print("Please provide one manually using the --audio-file argument.")
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
        
        # 5. Post-Processing: Publish Verified Songs
        if args.publish_verified:
            print("\n" + "=" * 50)
            print("📦 Post-Processing: Publishing Verified Songs")
            print("=" * 50)
            copy_verified_songs(PROCESSED_AUDIO_DIR, VERIFIED_AUDIO_DIR)
            
        # 6. Post-Processing: Generate Videos
        if args.make_videos:
            print("\n" + "=" * 50)
            print("🎬 Post-Processing: Generating Videos")
            print("=" * 50)
            make_videos(VERIFIED_AUDIO_DIR, VIDEOS_DIR, ffmpeg_path=FFMPEG_PATH)
            
        print("\n🎉 Pipeline completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")


if __name__ == "__main__":
    main()
