"""
National Museum of Women in the Arts (NMWA) — Washington, DC (Downtown)
Events: https://nmwa.org/whats-on/calendar/

Uses the WordPress REST API at /wp-json/wp/v2/event.
All events are returned without pagination (typically fewer than 20 at a time).

Key ACF fields (item["acf"]):
  event_start_date  — "20260321"  (YYYYMMDD)
  event_end_date    — "20260321"  (YYYYMMDD, may be empty)
  start_time        — "120000"    (HHMMSS)
  end_time          — "124500"    (HHMMSS, may be empty)
  free_event        — bool
  free_w_admission  — bool
  location          — HTML string (e.g. "<p>Meet near the Ticketing Desk.</p>")
  subheading        — short description
  featured_image_large → dict with "url" key
  reservations      — ticket/reservation URL

Top-level fields also used:
  event_image       — direct resized image URL
"""

import logging
import re
import requests
from datetime import date
from typing import List, Dict

logger = logging.getLogger(__name__)

NMWA_BASE = "https://nmwa.org"
NMWA_API_URL = "https://nmwa.org/wp-json/wp/v2/event"

LOCATION_FULL = "National Museum of Women in the Arts, 1250 New York Ave NW, Washington, DC 20005"
LOCATION_NAME = "National Museum of Women in the Arts"
NEIGHBORHOOD = "Downtown"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

CATEGORY_MAP = {
    "tour": "Heritage & History",
    "gallery talk": "Heritage & History",
    "lecture": "Heritage & History",
    "talk": "Heritage & History",
    "discussion": "Heritage & History",
    "symposium": "Heritage & History",
    "film": "Arts & Culture",
    "screening": "Arts & Culture",
    "performance": "Arts & Culture",
    "exhibition": "Arts & Culture",
    "concert": "Music",
    "workshop": "Community",
    "family": "Community",
    "kids": "Community",
    "children": "Community",
    "edit-a-thon": "Community",
    "celebration": "Festivals",
    "festival": "Festivals",
}


def _parse_date(raw: str) -> str:
    """Convert 'YYYYMMDD' → 'YYYY-MM-DD'. Returns '' if past or invalid."""
    if not raw or len(raw) < 8:
        return ""
    try:
        y, m, d = int(raw[:4]), int(raw[4:6]), int(raw[6:8])
        dt = date(y, m, d)
        if dt < date.today():
            return ""
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def _parse_time(raw: str) -> str:
    """Convert 'HHMMSS' or 'HHMM' → 'HH:MM'. Returns '' if invalid."""
    if not raw or len(raw) < 4:
        return ""
    try:
        h, m = int(raw[:2]), int(raw[2:4])
        return f"{h:02d}:{m:02d}"
    except (ValueError, TypeError):
        return ""


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def _extract_image(item: dict, acf: dict) -> str:
    """Pull image URL from event_image (top-level) or featured_image_large (acf)."""
    # Prefer the pre-resized top-level event_image
    url = item.get("event_image", "")
    if url and url.startswith("http"):
        return url
    # Fall back to acf featured_image_large
    try:
        img_large = acf.get("featured_image_large") or {}
        if isinstance(img_large, dict):
            url = img_large.get("url") or img_large.get("src") or ""
            if url and url.startswith("http"):
                return url
    except Exception:
        pass
    return ""


def scrape_nmwa_events() -> List[Dict]:
    """Scrape upcoming events from the National Museum of Women in the Arts."""
    events: List[Dict] = []
    seen_urls: set = set()

    try:
        resp = requests.get(
            NMWA_API_URL,
            params={"per_page": 100, "page": 1},
            headers=HEADERS,
            timeout=25,
        )
        if resp.status_code != 200:
            logger.warning(f"NMWA: API returned HTTP {resp.status_code}")
            return events

        raw_events = resp.json()
        if not isinstance(raw_events, list):
            logger.warning("NMWA: unexpected API response format")
            return events

        logger.info(f"NMWA: {len(raw_events)} raw events from API")

        for item in raw_events:
            try:
                acf = item.get("acf") or {}

                # ── Date ─────────────────────────────────────────────────
                date_str = _parse_date(acf.get("event_start_date", ""))
                if not date_str:
                    continue

                # ── Title ────────────────────────────────────────────────
                title = (item.get("title") or {}).get("rendered", "").strip()
                title = re.sub(r"<[^>]+>", "", title)
                if not title or len(title) < 3:
                    continue

                # ── URL ──────────────────────────────────────────────────
                url = item.get("link", "")
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                # ── Times ────────────────────────────────────────────────
                start_time = _parse_time(acf.get("start_time", ""))
                end_time = _parse_time(acf.get("end_time", ""))

                # ── Price ────────────────────────────────────────────────
                is_free = bool(acf.get("free_event")) or bool(acf.get("free_w_admission"))
                price = "Free" if bool(acf.get("free_event")) else \
                        "Free with admission" if bool(acf.get("free_w_admission")) else \
                        "See website"

                # ── Description ──────────────────────────────────────────
                description = re.sub(r"<[^>]+>", "", acf.get("subheading") or "").strip()

                # ── Image ────────────────────────────────────────────────
                image_url = _extract_image(item, acf)

                # ── Family friendly ──────────────────────────────────────
                family_keywords = ["family", "kids", "children", "families", "youth"]
                is_family = any(w in title.lower() for w in family_keywords)

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": start_time,
                    "end_time": end_time,
                    "location": LOCATION_FULL,
                    "location_name": LOCATION_NAME,
                    "location_address": "1250 New York Ave NW, Washington, DC 20005",
                    "neighborhood": NEIGHBORHOOD,
                    "description": description,
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "National Museum of Women in the Arts",
                    "borough": NEIGHBORHOOD,
                    "image_url": image_url,
                    "price": price,
                    "is_free": is_free,
                    "is_family_friendly": is_family,
                    "is_outdoor": False,
                    "city": "Washington DC",
                })

            except Exception as e:
                logger.debug(f"NMWA: error parsing event: {e}")

    except Exception as e:
        logger.error(f"NMWA scraper failed: {e}")

    logger.info(f"NMWA: scraped {len(events)} events")
    return events
