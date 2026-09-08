import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from dotenv import load_dotenv

from core.schemas import ServicePlan, Song, PlanSummary, ServiceType

# Load variables from .env file into the environment
load_dotenv()

# ==============================================================================
# CONFIGURATION
# ==============================================================================
PCO_APP_ID: str = os.getenv("PCO_APP_ID", "")
PCO_SECRET: str = os.getenv("PCO_SECRET", "")
PCO_BASE_URL: str = "https://api.planningcenteronline.com/services/v2"


def parse_pco_plan_date(dates_str: Optional[str]) -> Optional[str]:
    """Attempts to parse a standardized YYYY-MM-DD date string from a Planning Center dates field.
    
    Planning Center typically provides human-readable dates in formats such as:
    - 'September 6, 2026'
    - 'September 6, 2026 at 10:30am'
    - 'Sep 6, 2026'
    - '2026-09-06'
    
    Args:
        dates_str (Optional[str]): The raw date string from Planning Center.
        
    Returns:
        Optional[str]: Standardized YYYY-MM-DD date string, or None if parsing fails.
    """
    if not dates_str:
        return None
    cleaned = dates_str.split(" at ")[0].strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


# Alias for backwards compatibility
parse_pco_date = parse_pco_plan_date


def _make_pco_request(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Helper function to make a GET request to the Planning Center API.
    Automatically handles rate limits (HTTP 429) by respecting the Retry-After header.
    """
    if not PCO_APP_ID or not PCO_SECRET:
        raise ValueError("ERROR: Planning Center credentials missing in .env.")

    max_retries = 3
    for attempt in range(max_retries):
        response = requests.get(url, auth=(PCO_APP_ID, PCO_SECRET), params=params, timeout=15)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 20))
            print(f"⚠️ PCO Rate Limit hit. Sleeping for {retry_after} seconds before retrying...")
            time.sleep(retry_after)
            continue
            
        response.raise_for_status()
        return response.json()
        
    raise requests.exceptions.HTTPError("Exceeded maximum retries for rate limits.")


def fetch_service_types() -> List[ServiceType]:
    """Fetches a list of all available service types for the organization.
    
    Returns:
        List[ServiceType]: A list of ServiceType dataclasses containing id and name.
        
    Raises:
        ValueError: If PCO credentials are not found.
        requests.exceptions.HTTPError: If the API request fails.
    """
    url: str = f"{PCO_BASE_URL}/service_types"
    
    print("📡 Fetching service types from Planning Center...")
    data = _make_pco_request(url)
    
    service_types: List[ServiceType] = []
    
    for item in data.get("data", []):
        st_id = item.get("id", "")
        attributes = item.get("attributes", {})
        
        service_types.append(
            ServiceType(
                id=st_id,
                name=attributes.get("name") or "Unknown Service Type"
            )
        )
        
    return service_types


def fetch_service_plan(
    service_type_id: str, plan_id: str, service_date: str
) -> ServicePlan:
    """Fetches a service plan and its items from the Planning Center API.
    
    Parses the JSON response from Planning Center, extracts items labeled as 
    'song', and maps them into the standardized ServicePlan dataclass for the 
    pipeline to process.
    
    Args:
        service_type_id (str): The PCO Service Type ID.
        plan_id (str): The specific PCO Plan ID.
        service_date (str): The date of the service in YYYY-MM-DD format.
        
    Returns:
        ServicePlan: The structured data contract containing the songs.
        
    Raises:
        ValueError: If PCO credentials are not found in the environment.
        requests.exceptions.HTTPError: If the API request fails (e.g., 401 or 404).
    """
    # Endpoint to retrieve all items within a specific service plan
    url: str = f"{PCO_BASE_URL}/service_types/{service_type_id}/plans/{plan_id}/items"
    
    print(f"📡 Fetching Planning Center data for Plan ID: {plan_id}...")
    data = _make_pco_request(url)
    
    songs: List[Song] = []

    # Iterate through the timeline items
    for item in data.get("data", []):
        attributes: Dict[str, Any] = item.get("attributes", {})
        item_type: str = attributes.get("item_type", "").lower()
        
        if item_type == "song":
            title: str = attributes.get("title", "Unknown Song").strip()
            
            # Depending on how your PCO is configured, the key might be stored 
            # in the description, or a custom field. Adapt this extraction as needed.
            key: str = attributes.get("key_name") or attributes.get("description") or ""
            key = key.strip()
            
            songs.append(Song(title=title, key=key))

    print(f"✅ Successfully loaded {len(songs)} songs from Planning Center.")
    return ServicePlan(date=service_date, songs=songs)


def fetch_recent_plans(
    service_type_id: str, 
    limit: Optional[int] = None,
    target_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[PlanSummary]:
    """Fetches service plans for a given service type.
    
    Supports date-targeted queries, date ranges, and recent plan listings.
    Handles Planning Center's API pagination automatically to retrieve up to the requested limit.
    
    Args:
        service_type_id (str): The PCO Service Type ID.
        limit (Optional[int]): The maximum number of plans to retrieve. Defaults to 100 for date searches, or 5 for recent listings.
        target_date (Optional[str]): Specific target date (YYYY-MM-DD) to query for.
        start_date (Optional[str]): Start date (YYYY-MM-DD) for a date range query.
        end_date (Optional[str]): End date (YYYY-MM-DD) for a date range query.
        
    Returns:
        List[PlanSummary]: A list of PlanSummary dataclasses containing id, dates_raw, date, and title.
        
    Raises:
        ValueError: If PCO credentials are not found.
        requests.exceptions.HTTPError: If the API request fails.
    """
    url: str = f"{PCO_BASE_URL}/service_types/{service_type_id}/plans"
    
    effective_limit = limit if limit is not None else (100 if (target_date or (start_date and end_date)) else 5)
    per_page = min(effective_limit, 100)
    
    params: Dict[str, Any] = {"per_page": per_page, "order": "-sort_date", "filter": "past"}
    
    if target_date:
        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            prev_day = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
            next_day = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
            params = {
                "filter": "before,after",
                "after": f"{prev_day}T00:00:00Z",
                "before": f"{next_day}T23:59:59Z",
                "order": "-sort_date",
                "per_page": per_page
            }
            print(f"📡 Querying Planning Center for plans around date '{target_date}' (up to {effective_limit})...")
        except ValueError:
            print(f"📡 Fetching up to {effective_limit} recent plans from Planning Center...")
    elif start_date and end_date:
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d")
            prev_day = (s_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            next_day = (e_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            params = {
                "filter": "before,after",
                "after": f"{prev_day}T00:00:00Z",
                "before": f"{next_day}T23:59:59Z",
                "order": "-sort_date",
                "per_page": per_page
            }
            print(f"📡 Querying Planning Center for plans between {start_date} and {end_date} (up to {effective_limit})...")
        except ValueError:
            print(f"📡 Fetching up to {effective_limit} recent plans from Planning Center...")
    else:
        print(f"📡 Fetching up to {effective_limit} recent plans from Planning Center...")

    recent_plans: List[PlanSummary] = []
    use_date_filter = params.get("filter") == "before,after"
    
    while url and len(recent_plans) < effective_limit:
        try:
            data = _make_pco_request(url, params=params)
        except Exception:
            # If the date-filtered query fails (e.g. mock server or API incompatibility), fall back to standard 'past' query
            if use_date_filter:
                use_date_filter = False
                params = {"per_page": per_page, "order": "-sort_date", "filter": "past"}
                data = _make_pco_request(url, params=params)
            else:
                raise

        page_items = data.get("data", [])
        if not page_items:
            break

        oldest_date_in_page = None
        for item in page_items:
            plan_id = item.get("id", "")
            attributes = item.get("attributes", {})
            raw_dates = attributes.get("dates", "Unknown Date")
            parsed_date = parse_pco_plan_date(raw_dates)
            sort_date_attr = attributes.get("sort_date")
            if not parsed_date and sort_date_attr and len(sort_date_attr) >= 10:
                parsed_date = sort_date_attr[:10]

            if parsed_date:
                oldest_date_in_page = parsed_date
            
            recent_plans.append(
                PlanSummary(
                    id=plan_id,
                    dates_raw=raw_dates,
                    date=parsed_date,
                    title=attributes.get("title") or ""
                )
            )
            
            if len(recent_plans) >= effective_limit:
                break
                
        # If paginating over 'past' plans in reverse-chronological order, early break once plans are older than target/start date
        if not use_date_filter and oldest_date_in_page:
            if target_date and oldest_date_in_page < target_date:
                break
            if start_date and oldest_date_in_page < start_date:
                break

        # Handle pagination for the next request
        links = data.get("links", {})
        url = links.get("next", None)
        params = None # Query params like per_page and offset are embedded in the 'next' URL
        
    return recent_plans
