from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, List, Tuple
from core.schemas import Song

# Regex pattern for recognizing musical keys:
# Root: A-G, accidental: #, b, ♯, ♭
# Mode: m, min, minor, maj, major, M (with optional leading space)
# Optional bass note for slash chords: /F#, /B, etc.
_SINGLE_KEY_PATTERN = r'[A-Ga-g][#b♯♭]?(?:\s*(?:major|minor|maj|min|m|M))?(?:/[A-Ga-g][#b♯♭]?)?'

# Complete key pattern: supports single keys (e.g. 'E', 'Bm', 'C# Major', 'Eb/G')
# or key modulations / transitions (e.g. 'D-E', 'C-D-E', 'C#-D#', 'Eb-F', 'D->E', 'D - E')
KEY_PATTERN = re.compile(
    rf'^{_SINGLE_KEY_PATTERN}(?:\s*(?:->|–|-)\s*{_SINGLE_KEY_PATTERN})*$',
    re.IGNORECASE,
)


def normalize_musical_key(key: str) -> str:
    """Normalizes a musical key string, e.g. removing irregular spaces in key changes
    like 'D - E' or 'D -> E' -> 'D-E'.
    """
    if not key:
        return ""
    cleaned = re.sub(r'\s+', ' ', key.strip())
    return re.sub(r'\s*(?:->|–|-)\s*', '-', cleaned)


def is_valid_musical_key(candidate: str) -> bool:
    """Checks if a string conforms to standard musical key notation,
    including single keys ('E', 'Bm', 'C# Major', 'Eb/G') and modulations ('D-E', 'C-D-E', 'Eb-F').
    """
    if not candidate or not candidate.strip():
        return False
    return bool(KEY_PATTERN.match(candidate.strip()))


def normalize_song_title(title: str) -> str:
    """Normalizes a song title for robust comparison by lowercasing,
    stripping duplicate suffixes like '(2)', and removing non-alphanumeric chars.
    """
    if not title:
        return ""
    # Strip duplicate suffix like (2) or (3)
    cleaned = re.sub(r'\s*\(\d+\)$', '', title.strip())
    # Remove all non-alphanumeric characters and lowercase
    return re.sub(r'[^a-z0-9]', '', cleaned.lower())


def strip_embedded_key_from_title(title: str, matching_key: Optional[str] = None) -> Tuple[str, str]:
    """Strips an embedded musical key in parentheses or brackets from the end of a song title,
    while preserving other parenthetical title components (e.g. '(Bless The Lord)', '(Live)', '(Part 1)')
    and duplicate track suffixes (e.g. '(2)').
    
    If matching_key is provided, ONLY strips the embedded key if it is an exact (case-insensitive,
    normalized) match to matching_key.
    
    Examples:
        - 'Yet Not I But Through Christ In Me (D)'                    -> ('Yet Not I But Through Christ In Me', 'D')
        - '10,000 Reasons (Bless The Lord) (D)'                       -> ('10,000 Reasons (Bless The Lord)', 'D')
        - '10,000 Reasons (Bless The Lord)'                           -> ('10,000 Reasons (Bless The Lord)', '')
        - 'Yet Not I But Through Christ In Me (D) (2)'                -> ('Yet Not I But Through Christ In Me (2)', 'D')
        - 'Yet Not I But Through Christ In Me (2) (D)'                -> ('Yet Not I But Through Christ In Me (2)', 'D')
        - 'Amazing Grace'                                             -> ('Amazing Grace', '')
        - 'Build My Life (C# Major)'                                  -> ('Build My Life', 'C# Major')
        - 'In Christ Alone (D-E)'                                     -> ('In Christ Alone', 'D-E')
        - 'Angels We Have Heard On High (1)'                          -> ('Angels We Have Heard On High (1)', '')
        - strip_embedded_key_from_title('Song (G)', matching_key='E') -> ('Song (G)', '')
        - strip_embedded_key_from_title('Song (E)', matching_key='E') -> ('Song', 'E')
    """
    if not title or not str(title).strip():
        return ("", "")

    raw = str(title).strip()

    # Check for duplicate counter suffix at the very end: e.g. ' (2)'
    dup_match = re.search(r'\s*\((\d+)\)$', raw)
    dup_suffix = ""
    title_without_dup = raw
    if dup_match:
        dup_suffix = f" ({dup_match.group(1)})"
        title_without_dup = raw[:dup_match.start()].strip()

    # Look for trailing parenthetical or bracketed candidate at the end of title_without_dup
    key_match = re.search(r'\s*[\(\[]([^()\[\]]+)[\)\]]$', title_without_dup)
    if key_match:
        candidate = key_match.group(1).strip()
        if is_valid_musical_key(candidate):
            norm_cand = normalize_musical_key(candidate)
            if matching_key is not None:
                norm_match = normalize_musical_key(matching_key)
                if norm_cand.upper() != norm_match.upper():
                    return (raw, "")
            cleaned = title_without_dup[:key_match.start()].strip()
            if dup_suffix:
                cleaned = f"{cleaned}{dup_suffix}"
            return (cleaned, norm_cand)

    return (raw, "")


def extract_key_from_song(song: Song) -> str:
    """Extracts the musical key from a Song object.
    
    Checks song.key first, and if empty, checks if the key is embedded
    in the title in parentheses, e.g., 'Amazing Grace (E)' or 'In Christ Alone (D-E)'.
    """
    if song.key and song.key.strip():
        return normalize_musical_key(song.key.strip())
    
    # Check if key is embedded in parentheses/brackets in the title
    _, embedded_key = strip_embedded_key_from_title(song.title)
    if embedded_key:
        return embedded_key

    # Fallback search anywhere in parentheses
    m = re.search(
        rf'\(({_SINGLE_KEY_PATTERN}(?:\s*(?:->|–|-)\s*{_SINGLE_KEY_PATTERN})*)\)',
        song.title,
        re.IGNORECASE,
    )
    if m:
        return normalize_musical_key(m.group(1).strip())
        
    return ""


def filename_to_song(filename: str) -> Optional[Song]:
    """Deserializes a standardized audio/video filename into a Song dataclass.
    
    Supported formats:
        - '<Title> - <Date>.<ext>'            -> Song(title='<Title>', key='', date='<Date>')
        - '<Title> - <Key> - <Date>.<ext>'      -> Song(title='<Title>', key='<Key>', date='<Date>')
        - '<Title> - <Key>.<ext>'              -> Song(title='<Title>', key='<Key>', date=None)
        - '<Title>.<ext>'                      -> Song(title='<Title>', key='', date=None)
        
    Also automatically normalizes embedded parenthetical keys in titles, e.g.:
        - 'Yet Not I But Through Christ In Me (D) - 2026-08-02.mp4'     -> Song(title='Yet Not I But Through Christ In Me', key='D', date='2026-08-02')
        - 'Yet Not I But Through Christ In Me (D) - D - 2026-08-02.mp4' -> Song(title='Yet Not I But Through Christ In Me', key='D', date='2026-08-02')
        - '10,000 Reasons (Bless The Lord) (D) - 2026-08-02.mp4'         -> Song(title='10,000 Reasons (Bless The Lord)', key='D', date='2026-08-02')
        - '10,000 Reasons (Bless The Lord) (D) - D - 2026-08-02.mp4'     -> Song(title='10,000 Reasons (Bless The Lord)', key='D', date='2026-08-02')
    """
    if not filename or not str(filename).strip():
        return None

    base = os.path.basename(str(filename).strip())
    stem = Path(base).stem

    if not stem:
        return None

    # Check for date suffix at the end: ' - YYYY-MM-DD' or ' - YYYYMMDD'
    date_match = re.match(r'^(.*?)\s*-\s*(\d{4}-\d{2}-\d{2}|\d{8})$', stem)
    if date_match:
        prefix = date_match.group(1).strip()
        date_str = date_match.group(2).strip()

        # Check if prefix has a key at the end: e.g. '<Title> - <Key>'
        if " - " in prefix:
            parts = prefix.rsplit(" - ", 1)
            candidate_key = parts[1].strip()
            if is_valid_musical_key(candidate_key):
                raw_title = parts[0].strip()
                cleaned_title, _ = strip_embedded_key_from_title(raw_title, matching_key=candidate_key)
                return Song(title=cleaned_title, key=normalize_musical_key(candidate_key), date=date_str)

        cleaned_title, embedded_key = strip_embedded_key_from_title(prefix)
        return Song(title=cleaned_title, key=embedded_key, date=date_str)

    # If no date suffix, check if stem ends with a key: '<Title> - <Key>'
    if " - " in stem:
        parts = stem.rsplit(" - ", 1)
        candidate_key = parts[1].strip()
        if is_valid_musical_key(candidate_key):
            raw_title = parts[0].strip()
            cleaned_title, _ = strip_embedded_key_from_title(raw_title, matching_key=candidate_key)
            return Song(title=cleaned_title, key=normalize_musical_key(candidate_key), date=None)

    cleaned_title, embedded_key = strip_embedded_key_from_title(stem)
    return Song(title=cleaned_title, key=embedded_key, date=None)


def song_to_filename(song: Song, ext: Optional[str] = None) -> str:
    """Serializes a Song dataclass into a standardized Title-Centric filename.
    
    Formatting rules:
        - If key and date:  '<Title> - <Key> - <Date><ext>'
        - If date only:      '<Title> - <Date><ext>'
        - If key only:       '<Title> - <Key><ext>'
        - If neither:        '<Title><ext>'
        
    Examples:
        - Song('Amazing Grace', date='2024-08-04'), ext='.mp3'
          -> 'Amazing Grace - 2024-08-04.mp3'
        - Song('Amazing Grace', key='E', date='2024-08-04'), ext='.mp3'
          -> 'Amazing Grace - E - 2024-08-04.mp3'
        - Song('In Christ Alone', key='D-E', date='2026-09-13'), ext='.mp4'
          -> 'In Christ Alone - D-E - 2026-09-13.mp4'
    """
    parts = [song.title.strip()]
    if song.key and song.key.strip():
        parts.append(normalize_musical_key(song.key.strip()))
    if song.date and song.date.strip():
        parts.append(song.date.strip())

    stem = " - ".join(parts)
    if ext:
        normalized_ext = ext if ext.startswith(".") else f".{ext}"
        return f"{stem}{normalized_ext}"
    return stem


def find_matching_song(target_title: str, candidates: List[Song]) -> Optional[Song]:
    """Finds the best matching Planning Center Song candidate for a given target song title.
    
    Resolution order:
        1. Exact case-insensitive title match.
        2. Normalized alphanumeric match (ignores punctuation/spaces).
        3. Stripped parenthetical match (e.g. 'Amazing Grace (E)' -> 'Amazing Grace').
        4. Prefixed / section split match (e.g. 'Offertory - Amazing Grace' -> 'Amazing Grace').
        5. Substring containment match.
        6. Heuristic fuzzy ratio match (difflib SequenceMatcher >= 0.70).
        
    Handles duplicate track indices (e.g. 'Amazing Grace (2)') by mapping to the 
    corresponding instance if multiple matches exist.
    """
    if not target_title or not candidates:
        return None

    # Determine duplicate index if present
    dup_match = re.search(r'\s*\((\d+)\)$', target_title.strip())
    dup_index = int(dup_match.group(1)) if dup_match else 1
    base_title = re.sub(r'\s*\(\d+\)$', '', target_title.strip()).strip()
    norm_base = normalize_song_title(base_title)

    # 1. Exact case-insensitive match
    exact_matches = [c for c in candidates if c.title.strip().lower() == base_title.lower()]
    if exact_matches:
        return exact_matches[dup_index - 1] if len(exact_matches) >= dup_index else exact_matches[0]

    # 2. Normalized alphanumeric match
    norm_matches = [c for c in candidates if normalize_song_title(c.title) == norm_base]
    if norm_matches:
        return norm_matches[dup_index - 1] if len(norm_matches) >= dup_index else norm_matches[0]

    # 3. Stripped parentheticals (e.g. 'Amazing Grace (E)', 'Song (Live)')
    stripped_matches = [
        c for c in candidates 
        if normalize_song_title(strip_embedded_key_from_title(c.title)[0]) == norm_base
        or normalize_song_title(re.sub(r'\s*\(.*?\)', '', c.title)) == norm_base
    ]
    if stripped_matches:
        return stripped_matches[dup_index - 1] if len(stripped_matches) >= dup_index else stripped_matches[0]

    # 4. Prefixed / compound title split match (e.g. 'Offertory - Amazing Grace', 'Prelude: Amazing Grace')
    prefix_matches = []
    for c in candidates:
        for delimiter in (" - ", ": ", " / ", " | "):
            parts = c.title.split(delimiter)
            if any(normalize_song_title(p) == norm_base for p in parts):
                prefix_matches.append(c)
                break
    if prefix_matches:
        return prefix_matches[dup_index - 1] if len(prefix_matches) >= dup_index else prefix_matches[0]

    # 5. Substring containment match
    sub_matches = []
    for c in candidates:
        cand_norm = normalize_song_title(c.title)
        if (norm_base in cand_norm or cand_norm in norm_base) and len(norm_base) >= 4 and len(cand_norm) >= 4:
            sub_matches.append(c)
    if sub_matches:
        return sub_matches[dup_index - 1] if len(sub_matches) >= dup_index else sub_matches[0]

    # 6. Heuristic fuzzy ratio match using SequenceMatcher
    best_candidate: Optional[Song] = None
    best_ratio = 0.0
    for c in candidates:
        cand_norm = normalize_song_title(c.title)
        cand_stripped = normalize_song_title(re.sub(r'\s*\(.*?\)', '', c.title))
        r1 = SequenceMatcher(None, norm_base, cand_norm).ratio()
        r2 = SequenceMatcher(None, norm_base, cand_stripped).ratio()
        ratio = max(r1, r2)
        if ratio > best_ratio:
            best_ratio = ratio
            best_candidate = c

    if best_candidate and best_ratio >= 0.70:
        return best_candidate

    return None


# Backward-compatible aliases as requested in user prompt
from_filename_to_song = filename_to_song
from_song_to_filename = song_to_filename
