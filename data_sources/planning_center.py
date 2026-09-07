import os
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

from core.schemas import ServicePlan, Song

# Load variables from .env file into the environment
load_dotenv()

# ==============================================================================
# CONFIGURATION
# ==============================================================================
PCO_APP_ID: str = os.getenv("PCO_APP_ID", "")
PCO_SECRET: str = os.getenv("PCO_SECRET", "")
PCO_BASE_URL: str = "https://api.planningcenteronline.com/services/v2"


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
    if not PCO_APP_ID or not PCO_SECRET:
        raise ValueError(
            "ERROR: Planning Center credentials missing. "
            "Please define PCO_APP_ID and PCO_SECRET in your .env file."
        )

    # Endpoint to retrieve all items within a specific service plan
    url: str = f"{PCO_BASE_URL}/service_types/{service_type_id}/plans/{plan_id}/items"
    
    print(f"📡 Fetching Planning Center data for Plan ID: {plan_id}...")
    
    response = requests.get(url, auth=(PCO_APP_ID, PCO_SECRET), timeout=15)
    response.raise_for_status()
    
    data: Dict[str, Any] = response.json()
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
