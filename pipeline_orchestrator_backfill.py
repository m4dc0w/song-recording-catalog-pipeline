import os
import sys
import argparse
import time
from datetime import datetime
from typing import Tuple

from data_sources.planning_center import fetch_recent_plans, fetch_service_plan
from data_sources.local_drive import discover_raw_audio
from audio_segmentation.audio_segmentation import segment_service_audio
from pipeline_orchestrator import prompt_for_service_type, DEFAULT_SERVICE_TYPE, RAW_AUDIO_DIR

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

def parse_pco_date(pco_date_str: str) -> datetime | None:
    try:
        return datetime.strptime(pco_date_str, "%B %d, %Y")
    except ValueError:
        return None

def main() -> None:
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
        default=50,
        help="Maximum number of historical plans to fetch from PCO before filtering (Default: 50)."
    )
    
    args = parser.parse_args()

    service_type = args.service_type
    if not service_type:
        print("\n🔍 No Service Type ID provided in .env or arguments. Let's find it...")
        service_type = prompt_for_service_type()
        
    if args.start_date and args.end_date:
        start_date_str = args.start_date
        end_date_str = args.end_date
        try:
            parse_date(start_date_str)
            parse_date(end_date_str)
        except ValueError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    elif args.start_date or args.end_date:
        print("❌ Error: Both --start-date and --end-date must be provided if using CLI flags.")
        sys.exit(1)
    else:
        start_date_str, end_date_str = prompt_for_dates()
        
    start_dt = parse_date(start_date_str)
    end_dt = parse_date(end_date_str)

    print(f"\n🚀 Starting Backfill Orchestrator ({start_date_str} to {end_date_str})...")
    print("=" * 60)
    
    plans = fetch_recent_plans(service_type, limit=args.limit)
    if not plans:
        print("❌ No recent plans found for this Service Type.")
        sys.exit(1)
        
    # Filter plans
    target_plans = []
    for plan in plans:
        pco_dt = parse_pco_date(plan.dates)
        if pco_dt:
            if start_dt <= pco_dt <= end_dt:
                target_plans.append((plan, pco_dt.strftime("%Y-%m-%d")))
        else:
            print(f"⚠️ Warning: Could not parse date '{plan.dates}' for plan {plan.id}. Skipping.")
            
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

    if success_count > 0:
        print("\n💡 Next Steps (Post-Processing):")
        print("To stage, verify, and generate videos for your segmented songs, run:")
        print("  python3 pipeline_orchestrator.py --publish-verified --make-videos")
            
if __name__ == "__main__":
    main()
