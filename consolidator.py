"""
TMC Cultural Calendar - Event Consolidator
Merges, deduplicates, and normalizes events from all scrapers.
"""

import json
import logging
import re
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

CATEGORIES = [
    "Arts & Culture",
    "Music",
    "Theater",
    "Dance",
    "Festivals",
    "Parks & Recreation",
    "Heritage & History",
    "Community",
    "Weekend Picks",
    "Other",
]

BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "The Bronx", "Staten Island"]


def normalize_date(date_str: str) -> str:
    """Normalize date strings to ISO format YYYY-MM-DD."""
    if not date_str:
        return ""
    try:
        # Already ISO format
        if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
            return date_str[:10]
        dt = dateutil_parser.parse(date_str, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str


def normalize_time(time_str: str) -> str:
    """Normalize time strings to HH:MM format."""
    if not time_str:
        return ""
    try:
        match = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)?", time_str, re.I)
        if match:
            hour, minute, meridiem = match.groups()
            hour = int(hour)
            if meridiem and meridiem.lower() == "pm" and hour < 12:
                hour += 12
            elif meridiem and meridiem.lower() == "am" and hour == 12:
                hour = 0
            return f"{hour:02d}:{minute}"
        # Try ISO datetime
        dt = dateutil_parser.parse(time_str, fuzzy=True)
        return dt.strftime("%H:%M")
    except Exception:
        return ""


def infer_borough(location: str) -> str:
    """Infer NYC borough from location string."""
    if not location:
        return ""
    loc_lower = location.lower()
    if any(b in loc_lower for b in ["brooklyn", "bk"]):
        return "Brooklyn"
    if any(b in loc_lower for b in ["queens", "flushing", "astoria", "jamaica"]):
        return "Queens"
    if any(b in loc_lower for b in ["bronx", "the bronx"]):
        return "The Bronx"
    if any(b in loc_lower for b in ["staten island", "si "]):
        return "Staten Island"
    if any(b in loc_lower for b in ["manhattan", "midtown", "downtown", "uptown", "harlem",
                                     "tribeca", "soho", "chelsea", "east village", "west village",
                                     "upper east", "upper west", "lower east"]):
        return "Manhattan"
    return ""


def generate_event_id(event: Dict) -> str:
    """Generate a unique ID for an event based on title + date + source."""
    key = f"{event.get('title','').lower()}{event.get('date','')}{event.get('source','')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def normalize_event(event: Dict) -> Dict:
    """Normalize an event dict to a standard format."""
    normalized = {
        "id": "",
        "title": event.get("title", "").strip(),
        "date": normalize_date(event.get("date", "")),
        "end_date": normalize_date(event.get("end_date", "")),
        "time": normalize_time(event.get("time", "") or event.get("date", "")),
        "location": event.get("location", "New York, NY").strip(),
        "description": event.get("description", "").strip(),
        "url": event.get("url", ""),
        "category": event.get("category", "Other"),
        "source": event.get("source", "Unknown"),
        "borough": event.get("borough", "") or infer_borough(event.get("location", "")),
        "image_url": event.get("image_url", ""),
        "price": event.get("price", "See website"),
        "tags": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "is_featured": False,
        "is_free": False,
    }
    
    # Determine if free
    price_lower = normalized["price"].lower()
    if any(word in price_lower for word in ["free", "$0", "no cost", "complimentary"]):
        normalized["is_free"] = True
    
    # Auto-generate tags
    tags = []
    title_desc = (normalized["title"] + " " + normalized["description"]).lower()
    tag_keywords = {
        "family": ["family", "kids", "children", "all ages"],
        "outdoor": ["outdoor", "park", "garden", "open air"],
        "free": ["free", "no cost"],
        "music": ["music", "concert", "live music", "band", "jazz", "classical"],
        "art": ["art", "gallery", "exhibition", "museum", "painting"],
        "food": ["food", "culinary", "tasting", "dining"],
        "dance": ["dance", "ballet", "salsa", "hip hop"],
        "theater": ["theater", "theatre", "play", "performance", "broadway"],
        "film": ["film", "movie", "cinema", "screening"],
        "festival": ["festival", "fair", "carnival", "celebration"],
        "heritage": ["heritage", "culture", "history", "tradition"],
        "community": ["community", "neighborhood", "local"],
    }
    for tag, keywords in tag_keywords.items():
        if any(kw in title_desc for kw in keywords):
            tags.append(tag)
    normalized["tags"] = tags
    
    # Generate unique ID
    normalized["id"] = generate_event_id(normalized)
    
    return normalized


def deduplicate_events(events: List[Dict]) -> List[Dict]:
    """Remove duplicate events based on title similarity and date."""
    seen_ids = set()
    unique = []
    for event in events:
        eid = event.get("id", "")
        if eid and eid not in seen_ids:
            seen_ids.add(eid)
            unique.append(event)
        elif not eid:
            unique.append(event)
    return unique


def consolidate_events(
    nyc_events: List[Dict] = None,
    eventbrite_events: List[Dict] = None,
    timeout_events: List[Dict] = None,
    amnh_events: List[Dict] = None,
    moma_events: List[Dict] = None,
    whitney_events: List[Dict] = None,
    mcny_events: List[Dict] = None,
    newmuseum_events: List[Dict] = None,
    nyhistory_events: List[Dict] = None,
) -> List[Dict]:
    """Merge events from all sources, normalize, and deduplicate."""
    all_raw = []

    for label, batch in [
        ("NYC.gov", nyc_events),
        ("Eventbrite", eventbrite_events),
        ("TimeOut NY", timeout_events),
        ("AMNH", amnh_events),
        ("MoMA", moma_events),
        ("Whitney", whitney_events),
        ("MCNY", mcny_events),
        ("New Museum", newmuseum_events),
        ("NY Historical", nyhistory_events),
    ]:
        if batch:
            all_raw.extend(batch)
            logger.info(f"Added {len(batch)} {label} events")
    
    logger.info(f"Total raw events: {len(all_raw)}")
    
    # Normalize all events
    normalized = [normalize_event(e) for e in all_raw if e.get("title")]
    
    # Deduplicate
    unique = deduplicate_events(normalized)
    logger.info(f"After deduplication: {len(unique)} unique events")
    
    # Sort by date (events with no date go to end)
    def sort_key(e):
        d = e.get("date", "")
        return d if d else "9999-99-99"
    
    unique.sort(key=sort_key)
    return unique


def save_events(events: List[Dict], filepath: str = "data/events.json") -> None:
    """Save consolidated events to JSON file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        "last_updated": datetime.utcnow().isoformat(),
        "total_events": len(events),
        "sources": list(set(e.get("source", "") for e in events)),
        "events": events,
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(events)} events to {filepath}")


def load_events(filepath: str = "data/events.json") -> List[Dict]:
    """Load events from JSON file."""
    path = Path(filepath)
    if not path.exists():
        logger.warning(f"Events file not found: {filepath}")
        return []
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data.get("events", [])


def add_manual_event(event: Dict, filepath: str = "data/events.json") -> Dict:
    """Add a manually created event to the data store."""
    events = load_events(filepath)
    event["source"] = event.get("source", "Manual Entry")
    normalized = normalize_event(event)
    events.append(normalized)
    events.sort(key=lambda e: e.get("date", "9999-99-99"))
    save_events(events, filepath)
    return normalized


def delete_event(event_id: str, filepath: str = "data/events.json") -> bool:
    """Delete an event by ID."""
    events = load_events(filepath)
    original_count = len(events)
    events = [e for e in events if e.get("id") != event_id]
    if len(events) < original_count:
        save_events(events, filepath)
        return True
    return False


def update_event(event_id: str, updates: Dict, filepath: str = "data/events.json") -> Optional[Dict]:
    """Update an existing event."""
    events = load_events(filepath)
    for i, event in enumerate(events):
        if event.get("id") == event_id:
            events[i].update(updates)
            events[i]["updated_at"] = datetime.utcnow().isoformat()
            save_events(events, filepath)
            return events[i]
    return None
