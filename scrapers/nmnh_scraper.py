"""
Smithsonian National Museum of Natural History (NMNH) — Washington DC
Events: https://naturalhistory.si.edu/events

Actual HTML: <a class="event-teaser" href="/events/...">
  <img class="image--teaser" ...>
  <div class="event-teaser__second">
    <h4 class="event-teaser__title">...</h4>
    <span class="event-teaser__location">...</span>
  </div>
  <div class="event-teaser__third">
    <div class="event-teaser__date"><p>Thursday, March 19, 2026, 6:30 – 8:15pm EDT</p></div>
  </div>
</a>
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import List, Dict

logger = logging.getLogger(__name__)

NMNH_EVENTS_URL = "https://naturalhistory.si.edu/events"
NMNH_BASE = "https://naturalhistory.si.edu"
LOCATION = "National Museum of Natural History, 10th St & Constitution Ave NW, Washington, DC 20560"
BOROUGH = "National Mall"

CATEGORY_MAP = {
    "lecture": "Heritage & History",
    "talk": "Heritage & History",
    "tour": "Heritage & History",
    "exhibition": "Arts & Culture",
    "film": "Arts & Culture",
    "workshop": "Community",
    "family": "Community",
    "science": "Heritage & History",
    "nature": "Parks & Recreation",
    "fossil": "Heritage & History",
    "ocean": "Heritage & History",
    "evening": "Arts & Culture",
    "gallery": "Arts & Culture",
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _to_24h(time_raw: str) -> str:
    """Convert '6:30 pm', '11am', '12:00 PM' → '18:30', '11:00', '12:00'."""
    if not time_raw:
        return ""
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", time_raw.strip(), re.I)
    if not m:
        # Already HH:MM with no meridiem — return as-is if valid
        hm = re.match(r"^(\d{1,2}):(\d{2})$", time_raw.strip())
        if hm:
            return f"{int(hm.group(1)):02d}:{hm.group(2)}"
        return ""
    hour = int(m.group(1))
    minute = m.group(2) or "00"
    meridiem = m.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def _parse_nmnh_date(text: str):
    """Parse 'Thursday, March 19, 2026, 6:30 – 8:15pm EDT' → (date_iso, time_str)."""
    if not text:
        return "", ""
    text = text.strip()

    # Time range: look for am/pm pattern first, then fall back to bare H:MM
    time_str = ""
    # Try to find a time with am/pm indicator (most reliable)
    time_m = re.search(r"(\d{1,2}(?::\d{2})?)\s*(am|pm)", text, re.I)
    if time_m:
        time_str = _to_24h(time_m.group(0))
    else:
        # Bare H:MM (e.g. "6:30 – 8:15")
        bare = re.search(r"(\d{1,2}:\d{2})", text)
        if bare:
            time_str = _to_24h(bare.group(1))

    # Date: Month Day, Year
    date_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),?\s*(\d{4})?",
        text, re.I
    )
    if date_match:
        month, day, year = date_match.groups()
        year = int(year) if year else datetime.now().year
        month_num = MONTHS.get(month.lower(), 1)
        try:
            dt = datetime(year, month_num, int(day))
            if dt.date() < date.today():
                return "", ""
            return dt.strftime("%Y-%m-%d"), time_str
        except ValueError:
            pass

    return "", time_str


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Heritage & History"


def scrape_nmnh_events() -> List[Dict]:
    """Scrape events from the Smithsonian National Museum of Natural History."""
    events = []
    seen_urls = set()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = requests.get(NMNH_EVENTS_URL, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # NMNH: each event is <a class="event-teaser" href="/events/...">
        cards = soup.select("a.event-teaser")

        for card in cards[:40]:
            try:
                title_el = card.select_one(".event-teaser__title")
                if not title_el:
                    title_el = card.find(["h3", "h4", "h5"])
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = card.get("href", "")
                url = href if href.startswith("http") else (NMNH_BASE + href if href else "")
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                date_el = card.select_one(".event-teaser__date")
                date_str, time_str = ("", "")
                if date_el:
                    raw = date_el.get_text(strip=True)
                    date_str, time_str = _parse_nmnh_date(raw)

                loc_el = card.select_one(".event-teaser__location")
                description = loc_el.get_text(strip=True) if loc_el else ""

                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or ""
                    image_url = src if src.startswith("http") else (NMNH_BASE + src if src else "")

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "end_time": "",
                    "location": LOCATION,
                    "location_name": "National Museum of Natural History",
                    "location_address": "10th St & Constitution Ave NW, Washington, DC 20560",
                    "neighborhood": "National Mall",
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "National Museum of Natural History",
                    "borough": BOROUGH,
                    "image_url": image_url,
                    "price": "Free",
                    "is_free": True,
                    "is_family_friendly": any(w in (title+" "+description).lower() for w in ["family","kids","children","all ages"]),
                    "is_outdoor": any(w in (title+" "+description).lower() for w in ["outdoor","garden","plaza","open air"]),
                    "city": "Washington DC",
                })
            except Exception as e:
                logger.debug(f"NMNH: error parsing card: {e}")

    except Exception as e:
        logger.error(f"NMNH scraper failed: {e}")

    logger.info(f"NMNH: scraped {len(events)} events")
    return events
