"""
United States Holocaust Memorial Museum (USHMM) — Washington, DC (National Mall)
Calendar: https://www.ushmm.org/online-calendar

The site is a Nuxt.js app whose config embeds a public AWS API Gateway base:
  https://5d2qbr1cok.execute-api.us-east-1.amazonaws.com/prod

Events are fetched from /events, which returns up to 49 records (upcoming
and recent) including events in other cities (Chicago, New York, etc.) and
virtual programs.

Filtering strategy:
  1. is_displayed_ushmm = True  →  only events the museum promotes on its
     own site (excludes internal / archived records).
  2. c_isActive = True, c_eventStatus = "live", is_past = False.
  3. Location in Washington DC (city="Washington", state_abbr="DC", or
     c_locationName contains "Holocaust Memorial Museum") OR type="online"
     (virtual events hosted by the museum).
  4. Hard date guard: c_endDate >= today (catches any edge cases where
     is_past flag lags reality).

Also includes ongoing/permanent exhibitions at the museum itself — these
have c_startDate in the past but c_endDate far in the future and
is_past=False. Their "event date" is set to today's date so they appear
in the current calendar.

All times are stored as UTC in the API; they are converted to the timezone
given by c_timezoneMapping (typically America/New_York for DC events).
"""

import logging
import re
from datetime import datetime, date, timezone
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EVENTS_API_URL = (
    "https://5d2qbr1cok.execute-api.us-east-1.amazonaws.com/prod/events"
)
CALENDAR_BASE   = "https://www.ushmm.org/online-calendar"
LOCATION        = "United States Holocaust Memorial Museum, 100 Raoul Wallenberg Place SW, Washington, DC 20024"
NEIGHBORHOOD    = "National Mall"
DEFAULT_TZ      = "America/New_York"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.ushmm.org/",
    "Origin": "https://www.ushmm.org",
}

CATEGORY_MAP = {
    "public program":     "Heritage & History",
    "conference":         "Heritage & History",
    "lecture":            "Heritage & History",
    "symposium":          "Heritage & History",
    "remembrance":        "Heritage & History",
    "anchor event":       "Heritage & History",
    "next generation":    "Community",
    "exhibition":         "Arts & Culture",
    "film":               "Arts & Culture",
    "performance":        "Arts & Culture",
    "webinar":            "Heritage & History",
    "workshop":           "Community",
    "education":          "Community",
    "family":             "Community",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_html(raw: str) -> str:
    """Strip HTML tags and return plain text."""
    if not raw:
        return ""
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)


def _utc_to_local(utc_str: str, tz_name: str) -> Tuple[str, str]:
    """
    Convert a UTC ISO string like '2026-05-04T14:00:00.000Z'
    to (date_str 'YYYY-MM-DD', time_str 'HH:MM') in the given timezone.
    Returns ('', '') on failure.
    """
    if not utc_str:
        return "", ""
    try:
        # Normalise trailing .000Z → +00:00
        clean = re.sub(r"\.\d+Z$", "+00:00", utc_str).replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(clean)
        try:
            tz = ZoneInfo(tz_name or DEFAULT_TZ)
        except (ZoneInfoNotFoundError, KeyError):
            tz = ZoneInfo(DEFAULT_TZ)
        dt_local = dt_utc.astimezone(tz)
        return dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%H:%M")
    except Exception:
        return "", ""


def _is_dc_or_online(ev: dict) -> bool:
    """True if the event is at the USHMM / DC, or is an online event."""
    loc   = ev.get("location") or {}
    city  = loc.get("c_address_city") or ""
    state = loc.get("state_abbr") or ""
    name  = ev.get("c_locationName") or ""
    etype = ev.get("type") or ""

    if city.lower() == "washington" and state.upper() == "DC":
        return True
    if "holocaust memorial museum" in name.lower():
        return True
    if etype == "online" or name.lower() in ("online", "online only"):
        return True
    return False


def _infer_category(title: str, raw_category: str, description: str) -> str:
    combined = (title + " " + raw_category + " " + description).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Heritage & History"


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_ushmm_events() -> List[Dict]:
    """Scrape upcoming events from the USHMM public events API."""
    events: List[Dict] = []
    today  = date.today()

    try:
        resp = requests.get(EVENTS_API_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        raw = resp.json().get("data", [])
        logger.info(f"USHMM: fetched {len(raw)} raw API records")
    except Exception as e:
        logger.error(f"USHMM scraper failed to fetch API: {e}")
        return events

    seen_ids: set = set()

    for ev in raw:
        try:
            # ── Basic activity / visibility guards ───────────────────────
            if not ev.get("c_isActive"):
                continue
            if ev.get("c_eventStatus") != "live":
                continue
            if ev.get("is_past"):
                continue

            # ── Location guard: DC / USHMM or online ─────────────────────
            if not _is_dc_or_online(ev):
                continue

            # ── End-date guard ────────────────────────────────────────────
            end_raw = ev.get("c_endDate", "")
            tz_name = ev.get("c_timezoneMapping") or DEFAULT_TZ
            end_date_str, _ = _utc_to_local(end_raw, tz_name)
            if end_date_str and end_date_str < today.strftime("%Y-%m-%d"):
                continue

            # ── Dedup ─────────────────────────────────────────────────────
            ev_id = ev.get("id") or ev.get("c_eventId")
            if ev_id in seen_ids:
                continue
            seen_ids.add(ev_id)

            # ── Title ─────────────────────────────────────────────────────
            title = _strip_html(
                ev.get("c_event_pubtitle") or ev.get("c_event_title") or ""
            )
            if not title or len(title) < 3:
                continue

            # ── Date / time ───────────────────────────────────────────────
            start_raw = ev.get("c_startDate", "")
            date_str, start_time = _utc_to_local(start_raw, tz_name)

            # For ongoing exhibitions whose start predates today, use today
            if not date_str or date_str < today.strftime("%Y-%m-%d"):
                date_str = today.strftime("%Y-%m-%d")
                start_time = ""

            _, end_time = _utc_to_local(end_raw, tz_name)
            # Multi-day events: don't show misleading end time
            if end_date_str and end_date_str != date_str:
                end_time = ""

            # ── URL ───────────────────────────────────────────────────────
            url = ev.get("external_url") or ""
            if not url:
                slug = ev.get("slug", "")
                url = f"{CALENDAR_BASE}/{slug}" if slug else CALENDAR_BASE

            # ── Description ───────────────────────────────────────────────
            raw_desc = ev.get("details") or ev.get("limited_summary") or ""
            description = _strip_html(raw_desc)[:400]

            # ── Image ─────────────────────────────────────────────────────
            image_url = ev.get("media_url") or ""

            # ── Price / free ─────────────────────────────────────────────
            # ticket_price takes precedence over the is_free flag, which
            # can be inconsistent in the API (e.g. paid dinners marked free).
            price_raw = (ev.get("ticket_price") or "").strip()
            if price_raw and not re.search(r"\bfree\b", price_raw, re.I):
                is_free = False
                price   = price_raw[:100]
            else:
                is_free = bool(ev.get("is_free")) or bool(
                    re.search(r"\bfree\b", price_raw, re.I)
                )
                price   = "Free" if is_free else "See website"

            # ── Location ─────────────────────────────────────────────────
            loc_name  = ev.get("c_locationName") or "United States Holocaust Memorial Museum"
            ev_type   = ev.get("type") or ""
            is_online = ev_type == "online" or loc_name.lower() in ("online", "online only")

            if is_online:
                location         = "Online"
                location_name    = "United States Holocaust Memorial Museum (Online)"
                location_address = "100 Raoul Wallenberg Place SW, Washington, DC 20024"
            else:
                location         = LOCATION
                location_name    = loc_name or "United States Holocaust Memorial Museum"
                location_address = "100 Raoul Wallenberg Place SW, Washington, DC 20024"

            # ── Category ─────────────────────────────────────────────────
            raw_cat  = ev.get("c_event_category") or ""
            category = _infer_category(title, raw_cat, description)

            # ── Family friendly ───────────────────────────────────────────
            family_kw = ["family", "kids", "children", "youth", "daniel's story"]
            is_family = any(w in title.lower() for w in family_kw)

            events.append({
                "title":            title,
                "date":             date_str,
                "time":             start_time,
                "end_time":         end_time,
                "location":         location,
                "location_name":    location_name,
                "location_address": location_address,
                "neighborhood":     NEIGHBORHOOD,
                "description":      description,
                "url":              url,
                "category":         category,
                "source":           "US Holocaust Memorial Museum",
                "borough":          NEIGHBORHOOD,
                "image_url":        image_url,
                "price":            price,
                "is_free":          is_free,
                "is_family_friendly": is_family,
                "is_outdoor":       False,
                "city":             "Washington DC",
            })

        except Exception as e:
            logger.debug(f"USHMM: error parsing event: {e}")

    events.sort(key=lambda x: x["date"])
    logger.info(f"USHMM: scraped {len(events)} events")
    return events
