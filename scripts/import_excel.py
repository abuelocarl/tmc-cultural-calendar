"""
Import NYC events from TMC Excel submission file into data/events.json.

Maps the TMC submission template columns to the internal event schema,
normalizes all flags, infers categories, and merges with existing data.

Usage:
    python scripts/import_excel.py <path_to_xlsx>
    python scripts/import_excel.py ~/Downloads/"NY TMC Event Submission  (11).xlsx"
"""

import sys
import json
import hashlib
import logging
import re
from pathlib import Path
from datetime import datetime

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from consolidator import normalize_event, deduplicate_events, save_events, load_events

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Category inference ─────────────────────────────────────────────────────────
HOST_CATEGORY = {
    "whitney":              "Arts & Culture",
    "brooklyn museum":      "Arts & Culture",
    "moma":                 "Arts & Culture",
    "met ":                 "Arts & Culture",
    "metropolitan museum":  "Arts & Culture",
    "guggenheim":           "Arts & Culture",
    "frick":                "Arts & Culture",
    "poster house":         "Arts & Culture",
    "jewish museum":        "Heritage & History",
    "studio museum":        "Arts & Culture",
    "museum of the moving image": "Arts & Culture",
    "ny historical":        "Heritage & History",
    "new-york historical":  "Heritage & History",
    "mcny":                 "Heritage & History",
    "museum of arts and design": "Arts & Culture",
    "asia society":         "Heritage & History",
    "museum of sex":        "Arts & Culture",
    "new museum":           "Arts & Culture",
    "amnh":                 "Heritage & History",
    "natural history":      "Heritage & History",
    "intrepid":             "Heritage & History",
    "grand central":        "Heritage & History",
    "high line":            "Parks & Recreation",
    "bryant park":          "Parks & Recreation",
    "brooklyn bridge park": "Parks & Recreation",
    "prospect park":        "Parks & Recreation",
    "central park":         "Parks & Recreation",
    "lincoln center":       "Music",
    "carnegie hall":        "Music",
    "bargemusic":           "Music",
    "jazz":                 "Music",
    "philharmonic":         "Music",
    "opera":                "Music",
    "ballet":               "Dance",
    "dance":                "Dance",
    "theater":              "Theater",
    "theatre":              "Theater",
    "film":                 "Arts & Culture",
    "cinema":               "Arts & Culture",
    "children":             "Community",
    "kids":                 "Community",
    "library":              "Community",
}

KEYWORD_CATEGORY = {
    "concert":      "Music",
    "jazz":         "Music",
    "classical":    "Music",
    "symphony":     "Music",
    "opera":        "Music",
    "recital":      "Music",
    "ballet":       "Dance",
    "dance":        "Dance",
    "theater":      "Theater",
    "theatre":      "Theater",
    "broadway":     "Theater",
    "play":         "Theater",
    "exhibition":   "Arts & Culture",
    "exhibit":      "Arts & Culture",
    "gallery":      "Arts & Culture",
    "art":          "Arts & Culture",
    "festival":     "Festivals",
    "fair":         "Festivals",
    "film":         "Arts & Culture",
    "movie":        "Arts & Culture",
    "screening":    "Arts & Culture",
    "tour":         "Heritage & History",
    "history":      "Heritage & History",
    "heritage":     "Heritage & History",
    "walk":         "Parks & Recreation",
    "park":         "Parks & Recreation",
    "outdoor":      "Parks & Recreation",
    "workshop":     "Community",
    "community":    "Community",
    "family":       "Community",
    "kids":         "Community",
    "children":     "Community",
}


def infer_category(host: str, title: str, description: str) -> str:
    combined = f"{host} {title} {description}".lower()
    for key, cat in HOST_CATEGORY.items():
        if key in combined:
            return cat
    for key, cat in KEYWORD_CATEGORY.items():
        if key in combined:
            return cat
    return "Arts & Culture"


# ── Area → borough mapping ─────────────────────────────────────────────────────
AREA_BOROUGH = {
    "chelsea":          "Manhattan",
    "midtown":          "Manhattan",
    "upper east":       "Manhattan",
    "upper west":       "Manhattan",
    "harlem":           "Manhattan",
    "financial":        "Manhattan",
    "hudson":           "Manhattan",
    "hell's kitchen":   "Manhattan",
    "lower east":       "Manhattan",
    "greenwich":        "Manhattan",
    "brooklyn":         "Brooklyn",
    "dumbo":            "Brooklyn",
    "prospect":         "Brooklyn",
    "queens":           "Queens",
    "long island city": "Queens",
    "flushing":         "Queens",
    "online":           "Online",
}

BOROUGH_NORMALIZE = {
    "manhattan": "Manhattan",
    "brooklyn":  "Brooklyn",
    "queens":    "Queens",
    "the bronx": "The Bronx",
    "bronx":     "The Bronx",
    "staten island": "Staten Island",
    "online":    "Online",
}


def normalize_borough(raw_borough: str, area: str) -> str:
    b = str(raw_borough or "").strip().lower()
    if b in BOROUGH_NORMALIZE:
        return BOROUGH_NORMALIZE[b]
    a = str(area or "").strip().lower()
    for key, boro in AREA_BOROUGH.items():
        if key in a:
            return boro
    return raw_borough.strip() if raw_borough else ""


# ── Flag helpers ───────────────────────────────────────────────────────────────
def parse_bool_flag(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() not in ("", "false", "blank", "0", "no")
    return False


def parse_price_flag(val) -> str:
    """Return 'free' or 'paid' or 'See website'."""
    s = str(val or "").strip().lower()
    if s == "free":
        return "free"
    if s == "paid":
        "paid"
    return s if s in ("free", "paid") else "See website"


# ── Time formatting ────────────────────────────────────────────────────────────
def format_time(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, str):
        # Already HH:MM or HH:MM:SS
        m = re.match(r"^(\d{1,2}):(\d{2})", val.strip())
        if m:
            return f"{int(m.group(1)):02d}:{m.group(2)}"
        return val.strip()
    # timedelta (pandas reads time-only as timedelta)
    try:
        total_seconds = int(val.total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        return f"{h:02d}:{m:02d}"
    except Exception:
        pass
    # datetime
    try:
        return val.strftime("%H:%M")
    except Exception:
        return str(val)


# ── Date formatting ────────────────────────────────────────────────────────────
def format_date(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, str):
        val = val.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}", val):
            return val[:10]
        return val
    try:
        return val.strftime("%Y-%m-%d")
    except Exception:
        return str(val)


# ── Main row converter ─────────────────────────────────────────────────────────
def row_to_event(row: pd.Series) -> dict:
    # Strip the space typos in column names by accessing with the exact names
    title       = str(row.get("form_event_title") or "").strip()
    host        = str(row.get("form_event_host_name") or "").strip()
    loc_name    = str(row.get("form_event_location_name") or "").strip()
    loc_addr    = str(row.get("form_event_location_address") or "").strip()
    neighborhood = str(row.get("form_event_neighborhood") or "").strip()
    area        = str(row.get("form_event_area") or "").strip()
    borough_raw = str(row.get("form_event_borough") or "").strip()
    description = str(row.get("form_event_description") or "").strip()
    url         = str(row.get("form_event_url") or "").strip()

    # Location: "Venue Name, Address" or just address
    if loc_name and loc_addr:
        location = f"{loc_name}, {loc_addr}"
    elif loc_name:
        location = loc_name
    elif loc_addr:
        location = loc_addr
    else:
        location = "New York, NY"

    # Date + time
    date_str = format_date(row.get("form_event_date"))
    time_str = format_time(row.get("form_event_time"))
    end_time = format_time(row.get("form_event_endtime"))

    # Price flag
    price_flag = str(row.get("form _flag_price") or "").strip().lower()
    is_free = price_flag == "free"
    price = "Free" if is_free else ("See website" if price_flag != "paid" else "Paid")

    # Audience + food + outdoor + after_hours → tags
    tags = []
    audience = str(row.get("form _flag_audience") or "").strip().lower()
    if "family" in audience:
        tags.append("family")
    if parse_bool_flag(row.get("form _flag_food")):
        tags.append("food")
    if parse_bool_flag(row.get("form _flag_flag_outdoor")):
        tags.append("outdoor")
    if parse_bool_flag(row.get("form _flag_after_hours")):
        tags.append("after_hours")

    # Borough + neighborhood
    borough = normalize_borough(borough_raw, area)
    # Use neighborhood as fine-grained area label in the borough field if no borough
    if not borough and neighborhood:
        borough = normalize_borough("", neighborhood)

    # Source: use host name if available, else generic
    source = host if host and host.lower() not in ("nan", "") else "TMC Submission"

    # Category
    category = infer_category(host, title, description)
    if is_free:
        tags.append("free")

    return {
        "title":       title,
        "date":        date_str,
        "end_date":    "",
        "time":        time_str,
        "end_time":    end_time,
        "location":    location,
        "description": description,
        "url":         url,
        "category":    category,
        "source":      source,
        "city":        "New York",
        "borough":     borough,
        "neighborhood": neighborhood or area,
        "image_url":   "",
        "price":       price,
        "is_free":     is_free,
        "tags":        tags,
    }


# ── Entry point ────────────────────────────────────────────────────────────────
def main(xlsx_path: str):
    path = Path(xlsx_path).expanduser()
    if not path.exists():
        logger.error(f"File not found: {path}")
        sys.exit(1)

    logger.info(f"Reading: {path.name}")
    sheets = pd.read_excel(str(path), sheet_name=None, dtype=str)

    # Find the submissions sheet (non-Instructions)
    data_sheet = None
    for name, df in sheets.items():
        if "event" in name.lower() or "submission" in name.lower():
            data_sheet = df
            break
    if data_sheet is None:
        # fallback: largest sheet
        data_sheet = max(sheets.values(), key=len)

    logger.info(f"Loaded {len(data_sheet)} rows from submissions sheet")

    # Drop completely blank rows
    data_sheet = data_sheet.dropna(how="all")
    # Drop rows with no title
    data_sheet = data_sheet[data_sheet["form_event_title"].notna()]
    logger.info(f"After cleaning: {len(data_sheet)} rows with titles")

    # Re-read with proper types for date/time columns
    sheets_typed = pd.read_excel(str(path), sheet_name=None)
    data_typed = None
    for name, df in sheets_typed.items():
        if "event" in name.lower() or "submission" in name.lower():
            data_typed = df
            break
    if data_typed is None:
        data_typed = max(sheets_typed.values(), key=len)

    data_typed = data_typed.dropna(how="all")
    data_typed = data_typed[data_typed["form_event_title"].notna()]

    # Convert rows to events
    new_events = []
    skipped = 0
    for _, row in data_typed.iterrows():
        title = str(row.get("form_event_title") or "").strip()
        if not title or len(title) < 2:
            skipped += 1
            continue
        evt = row_to_event(row)
        new_events.append(evt)

    logger.info(f"Converted {len(new_events)} events ({skipped} skipped)")

    # Normalize via consolidator (assigns IDs, tags, is_free, etc.)
    normalized_new = [normalize_event(e) for e in new_events if e.get("title")]
    logger.info(f"Normalized {len(normalized_new)} events")

    # Load existing events and upsert (add new + update existing with new fields)
    events_path = ROOT / "data" / "events.json"
    existing = load_events(str(events_path))
    existing_by_id = {e["id"]: e for e in existing}

    added = 0
    updated = 0
    for evt in normalized_new:
        eid = evt["id"]
        if eid not in existing_by_id:
            existing_by_id[eid] = evt
            added += 1
        else:
            # Update with richer fields from the new schema
            old = existing_by_id[eid]
            for field in ("end_time", "location_name", "location_address", "neighborhood",
                          "is_free", "is_outdoor", "is_after_hours", "is_family_friendly",
                          "tags", "price"):
                if evt.get(field) not in (None, "", [], False) or field in ("is_free", "is_outdoor", "is_after_hours", "is_family_friendly"):
                    old[field] = evt[field]
            updated += 1

    existing = list(existing_by_id.values())
    logger.info(f"Added {added} new, updated {updated} existing events")

    # Sort by date
    existing.sort(key=lambda e: e.get("date", "9999-99-99"))

    # Save
    save_events(existing, str(events_path))
    logger.info(f"Total events in store: {len(existing)}")

    # Summary by source (top 15)
    from collections import Counter
    sources = Counter(e["source"] for e in normalized_new)
    print("\n── Top sources in import ──")
    for src, cnt in sources.most_common(15):
        print(f"  {src:<40} {cnt:>4} events")

    boroughs = Counter(e["borough"] for e in normalized_new if e.get("borough"))
    print("\n── Borough breakdown ──")
    for boro, cnt in boroughs.most_common():
        print(f"  {boro:<25} {cnt:>4} events")

    cats = Counter(e["category"] for e in normalized_new)
    print("\n── Category breakdown ──")
    for cat, cnt in cats.most_common():
        print(f"  {cat:<25} {cnt:>4} events")

    free_count = sum(1 for e in normalized_new if e.get("is_free"))
    print(f"\n── Price ──")
    print(f"  Free:  {free_count}")
    print(f"  Paid:  {len(normalized_new) - free_count}")
    print(f"\n✅ Done — {added} events added to data/events.json")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path_to_xlsx>")
        sys.exit(1)
    main(sys.argv[1])
