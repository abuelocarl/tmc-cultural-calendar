"""
National Mall & Memorial Parks — Washington, DC (National Mall)
Events: https://www.nps.gov/nama/planyourvisit/calendar.htm

Uses the NPS Data API (https://developer.nps.gov/api/v1/events).
API key is free — register at https://www.nps.gov/subjects/developer/get-started.htm
Set the NPS_API_KEY environment variable, or update NPS_API_KEY_DEFAULT below.

Park code: nama  (National Mall and Memorial Parks)
Covers: Washington Monument, Lincoln Memorial, FDR Memorial, Jefferson Memorial,
        WWII Memorial, Vietnam Veterans Memorial, Korean War Veterans Memorial,
        Martin Luther King Jr. Memorial, and more.

API response structure:
  {
    "id": "41ECC",
    "title": "Franklin Delano Roosevelt Memorial",
    "dates": ["2026-03-21", "2026-03-22"],   ← actual upcoming occurrence dates
    "times": [{"timestart": "03:00 PM", "timeend": "03:45 PM", ...}],
    "location": "Meet at the bookstore in the memorial.",
    "description": "...",
    "isfree": "true",
    "feeinfo": "",
    "types": ["Guided Tour", "Talk"],
    "tags": ["History", "art", ...],
    "images": [{"url": "...", ...}],
  }

Each entry in dates[] becomes its own event record.
"""

import logging
import os
import re
import requests
from datetime import datetime, date
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

NPS_API_KEY_DEFAULT = "trPRqy6d8jy3cpooM19DOA6xFIJJx77EHzixOq8N"
NPS_API_KEY  = os.environ.get("NPS_API_KEY", NPS_API_KEY_DEFAULT)
NPS_API_BASE = "https://developer.nps.gov/api/v1/events"
PARK_CODE    = "nama"

LOCATION_FULL = "National Mall & Memorial Parks, Washington, DC"
LOCATION_NAME = "National Mall & Memorial Parks"
NEIGHBORHOOD  = "National Mall"

# NPS event types → our categories
TYPE_MAP = {
    "Guided Tour":         "Arts & Culture",
    "Talk":                "Arts & Culture",
    "Living History":      "Arts & Culture",
    "Demonstration":       "Arts & Culture",
    "Exhibit":             "Arts & Culture",
    "Film":                "Arts & Culture",
    "Junior Ranger":       "Community",
    "Family":              "Community",
    "Workshop":            "Community",
    "Volunteer":           "Community",
    "Cultural Demonstration": "Arts & Culture",
    "Stargazing":          "Community",
    "Wildlife Watching":   "Community",
    "Music":               "Music",
    "Concert":             "Music",
    "Festival":            "Festivals",
}

FAMILY_KEYWORDS = ["family", "junior ranger", "kids", "children", "youth"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_time_12h(s: str) -> str:
    """'03:00 PM' → '15:00'  |  '' → ''"""
    s = s.strip()
    if not s:
        return ""
    try:
        dt = datetime.strptime(s, "%I:%M %p")
        return dt.strftime("%H:%M")
    except ValueError:
        pass
    try:
        dt = datetime.strptime(s, "%I:%M%p")
        return dt.strftime("%H:%M")
    except ValueError:
        return ""


def _infer_category(types: list, tags: list, title: str) -> str:
    for t in types:
        if t in TYPE_MAP:
            return TYPE_MAP[t]
    combined = (title + " " + " ".join(tags)).lower()
    if any(k in combined for k in ["music", "concert", "performance"]):
        return "Music"
    if any(k in combined for k in ["festival", "celebration"]):
        return "Festivals"
    return "Arts & Culture"


def _is_family(types: list, tags: list, title: str) -> bool:
    combined = (title + " " + " ".join(types) + " " + " ".join(tags)).lower()
    return any(k in combined for k in FAMILY_KEYWORDS)


def _build_url(event_id: str, info_url: str) -> str:
    if info_url and info_url.startswith("http"):
        return info_url
    if event_id:
        return f"https://www.nps.gov/planyourvisit/event-details.htm?id={event_id}"
    return "https://www.nps.gov/nama/planyourvisit/calendar.htm"


def _extract_image(images: list) -> str:
    for img in images or []:
        url = img.get("url", "")
        if url and url.startswith("http"):
            return url
    return ""


def _clean(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_nps_nama_events() -> List[Dict]:
    """Scrape upcoming events from National Mall & Memorial Parks via NPS API."""
    events: List[Dict] = []
    today = date.today()

    if not NPS_API_KEY:
        logger.error("NPS_API_KEY not set — skipping National Mall scraper")
        return events

    try:
        resp = requests.get(
            NPS_API_BASE,
            params={
                "parkCode": PARK_CODE,
                "api_key":  NPS_API_KEY,
                "limit":    500,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning(f"NPS API returned HTTP {resp.status_code}")
            return events

        raw_events = resp.json().get("data", [])
        logger.info(f"NPS NAMA: {len(raw_events)} event records from API")

    except Exception as e:
        logger.error(f"NPS NAMA API request failed: {e}")
        return events

    seen: set = set()

    for raw in raw_events:
        try:
            title = _clean(raw.get("title", ""))
            if not title or len(title) < 3:
                continue

            event_id  = raw.get("id") or raw.get("eventid", "")
            info_url  = raw.get("infourl", "")
            event_url = _build_url(event_id, info_url)

            description = _clean(raw.get("description", ""))[:400]
            location    = _clean(raw.get("location", "")) or LOCATION_FULL

            times      = raw.get("times") or []
            first_time = times[0] if times else {}
            start_time = _parse_time_12h(first_time.get("timestart", ""))
            end_time   = _parse_time_12h(first_time.get("timeend", ""))

            types  = raw.get("types") or []
            tags   = [t.strip() for t in (raw.get("tags") or [])]
            images = raw.get("images") or []

            is_free_str = str(raw.get("isfree", "")).lower()
            fee_info    = _clean(raw.get("feeinfo", ""))
            is_free     = is_free_str == "true" or "free" in fee_info.lower()
            price       = "Free" if is_free else (fee_info or "See website")

            category  = _infer_category(types, tags, title)
            family    = _is_family(types, tags, title)
            image_url = _extract_image(images)

            # Expand each occurrence date into its own event record
            occurrence_dates = raw.get("dates") or []
            if not occurrence_dates:
                # Fall back to datestart if dates array is empty
                ds = raw.get("datestart") or raw.get("date", "")
                if ds:
                    occurrence_dates = [ds]

            for date_str in occurrence_dates:
                try:
                    dt = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
                    if dt < today:
                        continue
                    date_iso = dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

                dedup_key = f"{event_id}_{date_iso}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                events.append({
                    "title":            title,
                    "date":             date_iso,
                    "time":             start_time,
                    "end_time":         end_time,
                    "location":         location,
                    "location_name":    LOCATION_NAME,
                    "location_address": "National Mall, Washington, DC",
                    "neighborhood":     NEIGHBORHOOD,
                    "description":      description,
                    "url":              event_url,
                    "category":         category,
                    "source":           "National Mall & Memorial Parks",
                    "borough":          NEIGHBORHOOD,
                    "image_url":        image_url,
                    "price":            price,
                    "is_free":          is_free,
                    "is_family_friendly": family,
                    "is_outdoor":       True,
                    "city":             "Washington DC",
                })

        except Exception as e:
            logger.debug(f"NPS NAMA: error parsing event '{raw.get('title', '')}': {e}")

    logger.info(f"NPS NAMA: scraped {len(events)} event occurrences")
    return events
