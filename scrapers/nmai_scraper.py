"""
National Museum of the American Indian (NMAI) — Washington DC / New York NY
Events: https://americanindian.si.edu/calendar

Uses the Trumba calendar JSON API (no JS rendering required):
  https://www.trumba.com/calendars/american-indian-museum.json?format=json

Returns ~90 upcoming events with ISO 8601 datetimes, full descriptions,
image objects, location strings, and a requiresPayment flag.

NMAI has two branches:
  - Washington DC  : 4th St & Independence Ave SW (National Mall)
  - New York, NY   : One Bowling Green, Lower Manhattan
Location is detected from the event's `location` field and routed accordingly.
"""

import html
import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

NMAI_JSON = (
    "https://www.trumba.com/calendars/american-indian-museum.json?format=json"
)
NMAI_BASE = "https://americanindian.si.edu"

LOCATION_DC = (
    "National Museum of the American Indian, "
    "4th St & Independence Ave SW, Washington, DC 20560"
)
LOCATION_NY = (
    "National Museum of the American Indian, "
    "One Bowling Green, New York, NY 10004"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_MAP = {
    "film":          "Arts & Culture",
    "screening":     "Arts & Culture",
    "exhibition":    "Arts & Culture",
    "performance":   "Arts & Culture",
    "concert":       "Music",
    "music":         "Music",
    "lecture":       "Heritage & History",
    "talk":          "Heritage & History",
    "discussion":    "Heritage & History",
    "tour":          "Heritage & History",
    "ceremony":      "Heritage & History",
    "cultural":      "Heritage & History",
    "history":       "Heritage & History",
    "native":        "Heritage & History",
    "indigenous":    "Heritage & History",
    "tribal":        "Heritage & History",
    "symposium":     "Heritage & History",
    "demonstration": "Heritage & History",
    "workshop":      "Community",
    "family":        "Community",
    "kids":          "Community",
    "children":      "Community",
    "festival":      "Festivals",
    "celebration":   "Festivals",
    "powwow":        "Festivals",
}


def _infer_category(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Heritage & History"


def _parse_iso(dt_str: str):
    """Parse '2026-03-18T10:30:00' → (date_iso, time_str) or ('', '') if past."""
    if not dt_str:
        return "", ""
    try:
        dt = datetime.fromisoformat(re.sub(r"[+-]\d{2}:\d{2}$|Z$", "", dt_str))
        if dt.date() < date.today() or dt.date() > date.today() + timedelta(days=183):
            return "", ""
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except Exception:
        return "", ""


def _strip_html(html_str: str) -> str:
    """Strip HTML tags and return plain text."""
    if not html_str:
        return ""
    return BeautifulSoup(html_str, "html.parser").get_text(separator=" ", strip=True)


def scrape_nmai_events() -> List[Dict]:
    """Scrape events from NMAI via the Trumba JSON API."""
    try:
        resp = requests.get(NMAI_JSON, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        logger.error(f"NMAI: failed to fetch JSON feed: {e}")
        return []

    # API returns a list directly
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("events", raw.get("data", []))
    else:
        logger.error(f"NMAI: unexpected JSON type: {type(raw)}")
        return []

    logger.info(f"NMAI: {len(items)} raw items from API")

    events    = []
    seen_ids  = set()

    for item in items:
        try:
            if not isinstance(item, dict):
                continue

            # Skip cancelled events
            if item.get("canceled", False):
                continue

            event_id = item.get("eventID", "")
            if event_id and event_id in seen_ids:
                continue
            if event_id:
                seen_ids.add(event_id)

            # ── Title ────────────────────────────────────────────────
            title = html.unescape((item.get("title") or "").strip())
            if not title:
                continue

            # ── Dates ────────────────────────────────────────────────
            date_iso, time_str   = _parse_iso(item.get("startDateTime", ""))
            if not date_iso:
                continue                               # past or undated
            _, end_time_str      = _parse_iso(item.get("endDateTime", ""))

            # ── URL ──────────────────────────────────────────────────
            event_url = (
                item.get("permaLinkUrl")
                or item.get("eventActionUrl")
                or item.get("webLink")
                or ""
            )
            if event_url and not event_url.startswith("http"):
                event_url = (
                    "https:" + event_url
                    if event_url.startswith("//")
                    else NMAI_BASE + event_url
                )

            # ── Image ────────────────────────────────────────────────
            image_url = ""
            for img_key in ("eventImage", "detailImage"):
                img_obj = item.get(img_key)
                if isinstance(img_obj, dict) and img_obj.get("url"):
                    image_url = img_obj["url"]
                    break
            if image_url and not image_url.startswith("http"):
                image_url = (
                    "https:" + image_url
                    if image_url.startswith("//")
                    else NMAI_BASE + image_url
                )

            # ── Description ──────────────────────────────────────────
            description = _strip_html(item.get("description", ""))[:400]

            # ── Location routing ─────────────────────────────────────
            loc_text  = (item.get("location") or "").strip()
            loc_lower = loc_text.lower()
            # Trumba titles often start with branch prefix: "NY | Title" or "DC | Title"
            title_branch = re.match(r"^(NY|DC|ONLINE)\s*\|", title, re.I)
            branch_code  = title_branch.group(1).upper() if title_branch else ""
            # Strip branch prefix from display title
            if title_branch:
                title = title[title_branch.end():].strip()

            if (
                "new york" in loc_lower
                or "bowling green" in loc_lower
                or branch_code == "NY"
            ):
                location         = LOCATION_NY
                location_name    = "National Museum of the American Indian"
                location_address = "One Bowling Green, New York, NY 10004"
                neighborhood     = "Lower Manhattan"
                borough          = "Lower Manhattan"
                city             = "New York"
            elif (
                "online" in loc_lower
                or "virtual" in loc_lower
                or "zoom" in loc_lower
                or branch_code == "ONLINE"
            ):
                location         = "Online"
                location_name    = "Online"
                location_address = ""
                neighborhood     = "National Mall"
                borough          = "Online"
                city             = "Washington DC"
            else:
                # Default to DC (National Mall branch)
                location         = LOCATION_DC
                location_name    = "National Museum of the American Indian"
                location_address = "4th St & Independence Ave SW, Washington, DC 20560"
                neighborhood     = "National Mall"
                borough          = "National Mall"
                city             = "Washington DC"

            # ── Price ────────────────────────────────────────────────
            is_free  = not item.get("requiresPayment", False)
            price    = "Free" if is_free else ""

            # ── Flags ────────────────────────────────────────────────
            combined = (title + " " + description).lower()
            is_family  = any(w in combined for w in
                             ["family", "kids", "children", "all ages"])
            is_outdoor = any(w in combined for w in
                             ["outdoor", "garden", "plaza", "open air"])

            events.append({
                "title":              title,
                "date":               date_iso,
                "end_date":           "",
                "time":               time_str,
                "end_time":           end_time_str,
                "location":           location,
                "location_name":      location_name,
                "location_address":   location_address,
                "neighborhood":       neighborhood,
                "description":        description,
                "url":                event_url,
                "category":           _infer_category(title, description),
                "source":             "National Museum of the American Indian",
                "borough":            borough,
                "image_url":          image_url,
                "price":              price,
                "is_free":            is_free,
                "is_family_friendly": is_family,
                "is_outdoor":         is_outdoor,
                "city":               city,
            })

        except Exception as e:
            logger.debug(f"NMAI: error parsing event: {e}")

    logger.info(f"NMAI: scraped {len(events)} events")
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_nmai_events()
    print(f"\nFound {len(results)} NMAI events:")
    for ev in results:
        end = f" → {ev['end_time']}" if ev.get("end_time") else ""
        print(f"  [{ev['date']}] {ev['title']}")
        print(
            f"           {ev['time']}{end} | {ev['category']} "
            f"| {ev.get('location_name', '')} | {ev['city']}"
        )
