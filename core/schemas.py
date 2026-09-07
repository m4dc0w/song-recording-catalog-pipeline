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
    """
    date: str
    songs: List[Song] = field(default_factory=list)
    sermon: Optional[Sermon] = None
    raw_audio_filepath: Optional[str] = None
