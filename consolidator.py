"""
TMC Cultural Calendar - Event Consolidator
Merges, deduplicates, and normalizes events from all scrapers.
"""

import csv
import json
import logging
import re
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

# Map legacy / abbreviated source names → canonical full names
# so scraper renames don't create duplicate entries
SOURCE_CANONICAL = {
    # NYC
    "AMNH":                 "American Museum of Natural History",
    "MoMA":                 "Museum of Modern Art",
    "Whitney":              "Whitney Museum of American Art",
    "MCNY":                 "Museum of the City of New York",
    "NY Historical":        "New-York Historical Society",
    "NY Historical Society":"New-York Historical Society",
    # DC
    "NGA":                  "National Gallery of Art",
    "Hirshhorn":            "Hirshhorn Museum",
    "NMNH":                 "National Museum of Natural History",
    "NMAAHC":               "National Museum of African American History and Culture",
    "Spy Museum":           "International Spy Museum",
    # Paris
    "Pompidou":             "Centre Pompidou",
    "Louvre":               "Musée du Louvre",
    "Musée d'Orsay":        "Musée d'Orsay",
    "Jeu de Paume":         "Jeu de Paume",
    "Musée Picasso":        "Musée Picasso Paris",
}

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

DC_NEIGHBORHOODS = [
    "National Mall",
    "Penn Quarter",
    "Capitol Hill",
    "Georgetown",
    "Dupont Circle",
    "Adams Morgan",
    "Logan Circle",
    "Shaw",
    "U Street",
    "Brookland",
    "Foggy Bottom",
    "Southwest Waterfront",
]

PARIS_ARRONDISSEMENTS = [
    "1st Arrondissement",
    "3rd Arrondissement",
    "4th Arrondissement",
    "5th Arrondissement",
    "6th Arrondissement",
    "7th Arrondissement",
    "8th Arrondissement",
    "9th Arrondissement",
    "13th Arrondissement",
    "16th Arrondissement",
    "18th Arrondissement",
]


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


def _split_location_parts(location: str):
    """Split 'Venue Name, 123 Street, City, State ZIP' → (location_name, location_address)."""
    if not location:
        return "", ""
    parts = [p.strip() for p in location.split(",", 1)]
    return parts[0], parts[1] if len(parts) > 1 else ""


def _is_after_hours(time_str: str) -> bool:
    """Return True if event starts at 6 pm or later."""
    if not time_str:
        return False
    m24 = re.match(r"^(\d{1,2}):\d{2}", time_str.strip())
    if m24:
        return int(m24.group(1)) >= 18
    m12 = re.search(r"(\d{1,2})(?::\d{2})?\s*(am|pm)", time_str, re.I)
    if m12:
        hour, meridiem = int(m12.group(1)), m12.group(2).lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        return hour >= 18
    return False


def normalize_event(event: Dict) -> Dict:
    """Normalize an event dict to a standard format."""
    city = event.get("city", "New York")
    raw_time = event.get("time", "") or event.get("date", "")
    location = event.get("location", "New York, NY").strip()
    loc_name, loc_addr = _split_location_parts(location)

    # End time: support explicit end_time or extraction from time range "7–10 pm"
    end_time_raw = event.get("end_time", "")
    if not end_time_raw:
        range_m = re.search(r"[-–]\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*$", raw_time, re.I)
        if range_m:
            end_time_raw = range_m.group(1).strip()

    raw_source = event.get("source", "Unknown")
    canonical_source = SOURCE_CANONICAL.get(raw_source, raw_source)

    normalized = {
        "id": "",
        "title": event.get("title", "").strip(),
        "date": normalize_date(event.get("date", "")),
        "end_date": normalize_date(event.get("end_date", "")),
        "time": normalize_time(raw_time),
        "end_time": normalize_time(end_time_raw),
        "location": location,
        "location_name": event.get("location_name", loc_name),
        "location_address": event.get("location_address", loc_addr),
        "neighborhood": event.get("neighborhood", ""),
        "description": event.get("description", "").strip(),
        "url": event.get("url", ""),
        "category": event.get("category", "Other"),
        "source": canonical_source,
        "city": city,
        "borough": event.get("borough", "") or infer_borough(event.get("location", "")),
        "image_url": event.get("image_url", ""),
        "price": event.get("price", "See website"),
        "tags": list(event.get("tags", [])),   # preserve any tags from import
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "is_featured": False,
        "is_free": bool(event.get("is_free", False)),
        "is_outdoor": bool(event.get("is_outdoor", False)),
        "is_after_hours": bool(event.get("is_after_hours", False)),
        "is_family_friendly": bool(event.get("is_family_friendly", False)),
    }

    # Determine if free
    price_lower = normalized["price"].lower()
    if any(word in price_lower for word in ["free", "$0", "no cost", "complimentary"]):
        normalized["is_free"] = True

    # Derive behavioral flags from time / tags / description
    title_desc = (normalized["title"] + " " + normalized["description"]).lower()
    existing_tags = set(normalized["tags"])

    if not normalized["is_after_hours"]:
        normalized["is_after_hours"] = _is_after_hours(normalized["time"])

    if not normalized["is_outdoor"]:
        normalized["is_outdoor"] = any(
            kw in title_desc for kw in ["outdoor", "open air", " park ", "garden", "plaza"]
        ) or "outdoor" in existing_tags

    if not normalized["is_family_friendly"]:
        normalized["is_family_friendly"] = any(
            kw in title_desc for kw in ["family", "kids", "children", "all ages"]
        ) or "family" in existing_tags

    # Auto-generate tags (merge with any pre-existing tags)
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
        "after_hours": [],   # driven by flag only
    }
    for tag, keywords in tag_keywords.items():
        if tag not in existing_tags and any(kw in title_desc for kw in keywords):
            existing_tags.add(tag)

    # Add flag-driven tags
    if normalized["is_free"] and "free" not in existing_tags:
        existing_tags.add("free")
    if normalized["is_outdoor"] and "outdoor" not in existing_tags:
        existing_tags.add("outdoor")
    if normalized["is_family_friendly"] and "family" not in existing_tags:
        existing_tags.add("family")
    if normalized["is_after_hours"] and "after_hours" not in existing_tags:
        existing_tags.add("after_hours")

    normalized["tags"] = sorted(existing_tags)

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
    # DC sources
    nga_events: List[Dict] = None,
    hirshhorn_events: List[Dict] = None,
    nmnh_events: List[Dict] = None,
    nmah_events: List[Dict] = None,
    nasm_events: List[Dict] = None,
    nmai_events: List[Dict] = None,
    nmaahc_events: List[Dict] = None,
    nbm_events: List[Dict] = None,
    spymuseum_events: List[Dict] = None,
    # Paris sources
    pompidou_events: List[Dict] = None,
    louvre_events: List[Dict] = None,
    orsay_events: List[Dict] = None,
    palaisdetokyo_events: List[Dict] = None,
    fondationlv_events: List[Dict] = None,
    museepicasso_events: List[Dict] = None,
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
        # DC
        ("NGA", nga_events),
        ("Hirshhorn", hirshhorn_events),
        ("NMNH", nmnh_events),
        ("NMAH", nmah_events),
        ("NASM", nasm_events),
        ("NMAI", nmai_events),
        ("NMAAHC", nmaahc_events),
        ("National Building Museum", nbm_events),
        ("Spy Museum", spymuseum_events),
        # Paris
        ("Pompidou", pompidou_events),
        ("Louvre", louvre_events),
        ("Musée d'Orsay", orsay_events),
        ("Jeu de Paume", palaisdetokyo_events),
        ("Musée de l'Orangerie", fondationlv_events),
        ("Musée Picasso", museepicasso_events),
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


# Neighborhood lookup for known NYC museum addresses
_NEIGHBORHOOD_MAP = {
    # NYC
    "200 central park west":    "Upper West Side",
    "11 w 53rd":                "Midtown West",
    "99 gansevoort":            "Meatpacking District",
    "1220 fifth ave":           "East Harlem",
    "235 bowery":               "Lower East Side",
    "170 central park west":    "Upper West Side",
    "1000 fifth avenue":        "Upper East Side",
    "79th street":              "Upper East Side",
    "fort tryon":               "Washington Heights",
    "lincoln center":           "Lincoln Square",
    "brooklyn museum":          "Prospect Heights",
    "200 eastern pkwy":         "Prospect Heights",
    # Washington DC
    "constitution ave":         "National Mall",
    "independence ave":         "National Mall",
    "national mall":            "National Mall",
    "smithsonian":              "National Mall",
    "6th st & constitution":    "National Mall",
    "10th st & constitution":   "National Mall",
    "7th st sw":                "National Mall",
    "1400 constitution":        "National Mall",
    "401 f st":                 "Penn Quarter",
    "700 l'enfant":             "Penn Quarter",
    "l'enfant plaza":           "Penn Quarter",
    "f st nw":                  "Penn Quarter",
    "pennsylvania ave":         "Penn Quarter",
    "dupont circle":            "Dupont Circle",
    "georgetown":               "Georgetown",
    "capitol hill":             "Capitol Hill",
    "adams morgan":             "Adams Morgan",
    "u street":                 "U Street",
    "14th st nw":               "Logan Circle",
    "shaw":                     "Shaw",
    # Paris
    "place georges-pompidou":   "4th Arrondissement",
    "centre pompidou":          "4th Arrondissement",
    "rue de rivoli":            "1st Arrondissement",
    "musée du louvre":          "1st Arrondissement",
    "louvre":                   "1st Arrondissement",
    "rue de la légion":         "7th Arrondissement",
    "musée d'orsay":            "7th Arrondissement",
    "avenue du président wilson": "16th Arrondissement",
    "palais de tokyo":          "16th Arrondissement",
    "avenue du mahatma gandhi": "16th Arrondissement",
    "bois de boulogne":         "16th Arrondissement",
    "fondation louis vuitton":  "16th Arrondissement",
    "place de la concorde":     "8th Arrondissement",
    "jeu de paume":             "8th Arrondissement",
    "jardin des tuileries":     "1st Arrondissement",
    "orangerie":                "1st Arrondissement",
    "rue de thorigny":          "3rd Arrondissement",
    "musée picasso":            "3rd Arrondissement",
    "75001":                    "1st Arrondissement",
    "75003":                    "3rd Arrondissement",
    "75004":                    "4th Arrondissement",
    "75007":                    "7th Arrondissement",
    "75116":                    "16th Arrondissement",
}

# CSV column names exactly as in the TMC template (preserving spaces in flag columns)
CSV_COLUMNS = [
    "form_submitted_by",
    "form_event_title",
    "form_event_city",
    "form_event_borough",
    "form_event_area",
    "form_event_date",
    "form_event_description",
    "form_event_time",
    "form_event_endtime",
    "form_event_host_name",
    "form_event_location_name",
    "form_event_location_address",
    "form_event_neighborhood",
    "form_event_url",
    "form _flag_price",
    "form _flag_audience",
    "form _flag_food",
    "form _flag_after_hours",
    "form _flag_flag_outdoor",
]


def _split_location(location: str):
    """Split 'Venue Name, 123 Street, City, State ZIP' into (name, address)."""
    if not location:
        return "", ""
    parts = location.split(",", 1)
    name = parts[0].strip()
    address = parts[1].strip() if len(parts) > 1 else ""
    return name, address


def _infer_neighborhood(location: str) -> str:
    """Best-effort neighborhood from location string."""
    loc_lower = location.lower()
    for key, neighborhood in _NEIGHBORHOOD_MAP.items():
        if key in loc_lower:
            return neighborhood
    return ""


def _format_date_for_csv(date_iso: str) -> str:
    """Convert YYYY-MM-DD to M/D/YYYY for the submission form."""
    if not date_iso:
        return ""
    try:
        dt = datetime.strptime(date_iso[:10], "%Y-%m-%d")
        return dt.strftime("%-m/%-d/%Y")
    except ValueError:
        return date_iso


def _flag_after_hours(time_str: str) -> str:
    """Return 'Yes' if event starts at 6 pm or later."""
    if not time_str:
        return ""
    # 24-hour format: HH:MM
    match_24 = re.match(r"^(\d{2}):(\d{2})$", time_str.strip())
    if match_24:
        return "Yes" if int(match_24.group(1)) >= 18 else ""
    # 12-hour format: e.g. '7 pm', '6:30 pm'
    match_12 = re.search(r"(\d{1,2})(?::\d{2})?\s*(am|pm)", time_str, re.I)
    if match_12:
        hour, meridiem = int(match_12.group(1)), match_12.group(2).lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        return "Yes" if hour >= 18 else ""
    return ""


def _flag_price(event: Dict) -> str:
    """Return 'Free', 'Paid', or empty string."""
    if event.get("is_free"):
        return "Free"
    price = event.get("price", "").lower()
    if "free" in price or "$0" in price:
        return "Free"
    if re.search(r"\$\d", price):
        return "Paid"
    return ""


def event_to_csv_row(event: Dict) -> Dict:
    """Map a normalized event dict to a TMC CSV submission row."""
    # Use stored split fields first, fall back to inference
    location_name = event.get("location_name", "") or ""
    location_address = event.get("location_address", "") or ""
    if not location_name and not location_address:
        location_name, location_address = _split_location(event.get("location", ""))

    neighborhood = event.get("neighborhood", "") or _infer_neighborhood(event.get("location", ""))
    area = event.get("neighborhood", "") or neighborhood

    time_str = event.get("time", "")
    end_time = event.get("end_time", "")

    # Audience flag
    audience = ""
    tags = event.get("tags", [])
    if event.get("is_family_friendly") or "family" in tags:
        audience = "family friendly"
    elif not event.get("is_family_friendly"):
        audience = "adults"

    # Food flag
    food_flag = "True" if "food" in tags else "BLANK"

    # After-hours: use stored flag or derive from time
    after_hours = "1" if (event.get("is_after_hours") or _flag_after_hours(time_str) == "Yes") else "0"

    # Outdoor flag
    outdoor = "1" if (event.get("is_outdoor") or "outdoor" in tags) else "0"

    return {
        "form_submitted_by":           event.get("source", "TMC Scraper"),
        "form_event_title":            event.get("title", ""),
        "form_event_city":             event.get("city", "New York"),
        "form_event_borough":          event.get("borough", ""),
        "form_event_area":             area,
        "form_event_date":             _format_date_for_csv(event.get("date", "")),
        "form_event_description":      event.get("description", ""),
        "form_event_time":             time_str,
        "form_event_endtime":          end_time,
        "form_event_host_name":        event.get("source", ""),
        "form_event_location_name":    location_name,
        "form_event_location_address": location_address,
        "form_event_neighborhood":     neighborhood,
        "form_event_url":              event.get("url", ""),
        "form _flag_price":            _flag_price(event),
        "form _flag_audience":         audience,
        "form _flag_food":             food_flag,
        "form _flag_after_hours":      after_hours,
        "form _flag_flag_outdoor":     outdoor,
    }


def save_events_csv(events: List[Dict], filepath: str = "data/events.csv") -> None:
    """Save consolidated events to CSV in TMC submission format."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for event in events:
            writer.writerow(event_to_csv_row(event))

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
