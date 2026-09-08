from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Song:
    """Represents a single musical piece scheduled in a service.
    
    Attributes:
        title (str): The name of the song (e.g., "Amazing Grace").
        key (str, optional): The musical key of the song (e.g., "G", "Bm"). 
            Defaults to an empty string.
    """
    title: str
    key: str = ""

# =============================================================================
# FUTURE EXTENSIBILITY STUBS
# =============================================================================

@dataclass
class PlanSummary:
    """A lightweight representation of a Planning Center plan for list views and menus.
    
    Attributes:
        id (str): The unique Planning Center Plan ID.
        dates_raw (str): The human-readable raw date string provided by Planning Center (e.g. 'September 6, 2026').
        date (Optional[str]): The normalized date in YYYY-MM-DD format (e.g. '2026-09-06').
        title (str): An optional custom title for the service plan (e.g., 'Vision Sunday').
    """
    id: str
    dates_raw: str = ""
    date: Optional[str] = None
    title: str = ""

    def __init__(
        self,
        id: str,
        dates_raw: str = "",
        date: Optional[str] = None,
        title: str = "",
        dates: Optional[str] = None,
    ):
        self.id = id
        self.dates_raw = dates if (dates is not None and not dates_raw) else dates_raw
        self.date = date
        self.title = title

    @property
    def dates(self) -> str:
        """Backward-compatible alias for dates_raw."""
        return self.dates_raw

    @dates.setter
    def dates(self, value: str) -> None:
        self.dates_raw = value

@dataclass
class Sermon:
    """Represents the main spoken message or sermon in a service.
    
    This is stubbed for future extensibility (e.g., automated podcast 
    generation or AI video clipping).
    
    Attributes:
        title (str): The title of the message.
        speaker (str, optional): The name of the person delivering the message.
        passage (str, optional): The primary scripture reference.
    """
    title: str
    speaker: str = ""
    passage: str = ""

# =============================================================================
# CORE MODELS
# =============================================================================

@dataclass
class ServicePlan:
    """The master container representing a single church service event.
    
    Acts as the standard data contract passed between the ingestion 
    orchestrator and the processing workers.
    
    Attributes:
        date (str): The date of the service in YYYY-MM-DD format.
        songs (List[Song]): An ordered list of songs performed during the service.
        sermon (Sermon, optional): Sermon details, if applicable. Defaults to None.
        raw_audio_filepath (str, optional): The absolute local path to the 
            source .wav file. Populated dynamically by the orchestrator.
        dates_raw (str, optional): The human-readable raw date string from 
            Planning Center, if available. Defaults to an empty string.
    """
    date: str
    songs: List[Song] = field(default_factory=list)
    sermon: Optional[Sermon] = None
    raw_audio_filepath: Optional[str] = None
    dates_raw: str = ""

@dataclass
class ServiceType:
    """A representation of a Planning Center Service Type."""
    id: str
    name: str
