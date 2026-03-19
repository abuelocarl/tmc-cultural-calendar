"""
National Postal Museum — Washington, DC (NoMa)
Calendar: https://postalmuseum.si.edu/visit/calendar

The site uses Trumba calendar (webName: "published-calendars-npm").
Events are fetched directly from the public Trumba JSON API:
  https://www.trumba.com/calendars/published-calendars-npm.json

The feed returns up to 200 future event instances, including many
recurring occurrences (e.g. "Highlights Tour" runs every Wednesday).
The scraper deduplicates by title, keeping only the next upcoming
occurrence of each distinct program.

JSON fields used:
  startDateTime    ISO "2026-03-18T11:00:00"
  endDateTime      ISO "2026-03-18T14:00:00"
  title            event name
  description      plain-text description
  permaLinkUrl     link back to the calendar on postalmuseum.si.edu
  eventImage.url   image thumbnail
  categoryCalendar "National Postal Museum|One-Time Events" etc.
  customFields     list of {label, value} dicts — contains Cost, Venue,
                   Event Location, Accessibility
  canceled         bool — skip if true
  requiresPayment  bool
"""

import html as html_mod
import logging
import re
import requests
from datetime import datetime, date
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

TRUMBA_URL = "https://www.trumba.com/calendars/published-calendars-npm.json"
LOCATION    = "National Postal Museum, 2 Massachusetts Ave NE, Washington, DC 20002"
NEIGHBORHOOD = "NoMa"
ARRONDISSEMENT = "NoMa"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, */*;q=0.8",
}

CATEGORY_MAP = {
    "tour": "Heritage & History",
    "highlights": "Heritage & History",
    "gallery": "Heritage & History",
    "lecture": "Heritage & History",
    "talk": "Heritage & History",
    "discussion": "Heritage & History",
    "story time": "Community",
    "family": "Community",
    "kids": "Community",
    "children": "Community",
    "workshop": "Community",
    "yoga": "Community",
    "craft": "Community",
    "design": "Community",
    "film": "Arts & Culture",
    "concert": "Music",
    "music": "Music",
    "jazz": "Music",
    "performance": "Arts & Culture",
    "exhibition": "Arts & Culture",
    "book": "Heritage & History",
    "symposium": "Heritage & History",
    "symposia": "Heritage & History",
    "webcast": "Arts & Culture",
    "online": "Arts & Culture",
    "virtual": "Arts & Culture",
    "festival": "Festivals",
    "celebration": "Festivals",
}


def _clean(text: str) -> str:
    """Decode HTML entities and strip whitespace."""
    if not text:
        return ""
    return html_mod.unescape(text).strip()


def _parse_iso(dt_str: str) -> Tuple[str, str]:
    """
    Parse ISO datetime string '2026-03-18T11:00:00'
    → ('2026-03-18', '11:00').
    Returns ('', '') for past dates or parse errors.
    """
    if not dt_str:
        return "", ""
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.date() < date.today():
            return "", ""
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except ValueError:
        return "", ""


def _get_custom_field(custom_fields: list, label: str) -> str:
    """Return the value of the first custom field matching label (case-insensitive)."""
    for field in custom_fields:
        if field.get("label", "").lower() == label.lower():
            return _clean(field.get("value", ""))
    return ""


def _infer_category(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Heritage & History"


def scrape_npm_events() -> List[Dict]:
    """Scrape upcoming events from the National Postal Museum via Trumba."""
    events = []
    today = date.today()

    try:
        resp = requests.get(TRUMBA_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        raw_events = resp.json()
        logger.info(f"NPM: fetched {len(raw_events)} raw Trumba records")
    except Exception as e:
        logger.error(f"NPM scraper failed to fetch Trumba feed: {e}")
        return events

    # Deduplicate recurring events: keep the earliest upcoming occurrence per title
    best: Dict[str, dict] = {}
    for ev in raw_events:
        if ev.get("canceled"):
            continue
        start = ev.get("startDateTime", "")
        if not start:
            continue
        try:
            if datetime.fromisoformat(start).date() < today:
                continue
        except ValueError:
            continue

        title = _clean(ev.get("title", ""))
        if not title:
            continue

        if title not in best or start < best[title]["startDateTime"]:
            best[title] = ev

    logger.info(f"NPM: {len(best)} unique upcoming events after deduplication")

    for ev in sorted(best.values(), key=lambda x: x["startDateTime"]):
        try:
            title = _clean(ev.get("title", ""))
            description = _clean(ev.get("description", ""))
            custom_fields = ev.get("customFields", [])

            date_str, start_time = _parse_iso(ev.get("startDateTime", ""))
            _, end_time = _parse_iso(ev.get("endDateTime", ""))
            if not date_str:
                continue

            # URL: use permaLinkUrl (always resolves to postalmuseum.si.edu)
            url = ev.get("permaLinkUrl", "") or ""

            # Image
            image_url = ""
            ev_img = ev.get("eventImage") or ev.get("detailImage")
            if ev_img and isinstance(ev_img, dict):
                image_url = ev_img.get("url", "")

            # Cost from customFields
            cost_raw = _get_custom_field(custom_fields, "Cost")
            is_free = bool(re.search(r"\bfree\b", cost_raw, re.I)) or not ev.get("requiresPayment", False)
            price = "Free" if is_free else (cost_raw if cost_raw else "See website")

            # Location detail
            event_location = _get_custom_field(custom_fields, "Event Location")
            location_name = "National Postal Museum"
            location = LOCATION
            is_online = bool(re.search(r"\bonline\b|\bvirtual\b", event_location, re.I))

            # Family-friendly keywords
            family_kw = ["story time", "family", "kids", "children", "youth"]
            is_family = any(w in title.lower() for w in family_kw)

            events.append({
                "title": title,
                "date": date_str,
                "time": start_time,
                "end_time": end_time,
                "location": location,
                "location_name": location_name,
                "location_address": "2 Massachusetts Ave NE, Washington, DC 20002",
                "neighborhood": NEIGHBORHOOD,
                "description": description[:400],
                "url": url,
                "category": _infer_category(title, description),
                "source": "National Postal Museum",
                "borough": ARRONDISSEMENT,
                "image_url": image_url,
                "price": price,
                "is_free": is_free,
                "is_family_friendly": is_family,
                "is_outdoor": False,
                "city": "Washington DC",
            })

        except Exception as e:
            logger.debug(f"NPM: error parsing event: {e}")

    logger.info(f"NPM: scraped {len(events)} events")
    return events
