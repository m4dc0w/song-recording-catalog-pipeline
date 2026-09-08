import os
import time
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


def fetch_recent_plans(service_type_id: str, limit: int = 5) -> List[PlanSummary]:
    """Fetches a list of the most recent service plans for a given service type.
    
    Handles Planning Center's API pagination automatically to retrieve up to the requested limit.
    
    Args:
        service_type_id (str): The PCO Service Type ID.
        limit (int): The maximum number of recent plans to retrieve.
        
    Returns:
        List[PlanSummary]: A list of PlanSummary dataclasses containing id, dates, and title.
        
    Raises:
        ValueError: If PCO credentials are not found.
        requests.exceptions.HTTPError: If the API request fails.
    """
    url: str = f"{PCO_BASE_URL}/service_types/{service_type_id}/plans"
    
    # We will fetch up to 100 per page to minimize API calls (PCO max is usually 100)
    per_page = min(limit, 100)
    params = {"per_page": per_page, "order": "-sort_date"}
    
    print(f"📡 Fetching up to {limit} recent plans from Planning Center...")
    recent_plans: List[PlanSummary] = []
    
    while url and len(recent_plans) < limit:
        data = _make_pco_request(url, params=params)
        
        for item in data.get("data", []):
            plan_id = item.get("id", "")
            attributes = item.get("attributes", {})
            
            recent_plans.append(
                PlanSummary(
                    id=plan_id,
                    dates=attributes.get("dates", "Unknown Date"),
                    title=attributes.get("title") or ""
                )
            )
            
            if len(recent_plans) >= limit:
                break
                
        # Handle pagination for the next request
        links = data.get("links", {})
        url = links.get("next", None)
        params = None # Query params like per_page and offset are embedded in the 'next' URL
        
    return recent_plans
