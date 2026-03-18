"""
National Museum of African American History and Culture (NMAAHC) — Washington DC
Events: https://nmaahc.si.edu/events

Actual HTML: <div class="teaser teaser--event ..." about="/events/...">
  <h3 class="teaser__title mt-0">
    <a href="/events/..."><span>Event Title</span></a>
  </h3>
  <div class="teaser__date ...">...</div>
</div>
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import List, Dict

logger = logging.getLogger(__name__)

NMAAHC_EVENTS_URL = "https://nmaahc.si.edu/events"
NMAAHC_BASE = "https://nmaahc.si.edu"
LOCATION = "National Museum of African American History and Culture, 1400 Constitution Ave NW, Washington, DC 20560"
BOROUGH = "National Mall"

CATEGORY_MAP = {
    "film": "Arts & Culture",
    "screening": "Arts & Culture",
    "concert": "Music",
    "music": "Music",
    "performance": "Arts & Culture",
    "dance": "Dance",
    "lecture": "Heritage & History",
    "talk": "Heritage & History",
    "symposium": "Heritage & History",
    "tour": "Heritage & History",
    "family": "Community",
    "workshop": "Community",
    "youth": "Community",
    "conversation": "Community",
    "heritage": "Heritage & History",
    "history": "Heritage & History",
    "curation": "Arts & Culture",
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _to_24h(time_raw: str) -> str:
    """Convert '1:30 pm', '11am', '12:00 PM' → '13:30', '11:00', '12:00'."""
    if not time_raw:
        return ""
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", time_raw.strip(), re.I)
    if not m:
        return ""
    hour = int(m.group(1))
    minute = m.group(2) or "00"
    meridiem = m.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def _parse_date(text: str):
    """Parse date strings like 'March 15, 2026' or 'March 15–17, 2026'.
    Returns (date_iso, time_str) where time_str is HH:MM 24h or ''."""
    if not text:
        return "", ""
    text = text.strip()

    time_str = ""
    time_match = re.search(r"(\d{1,2}:\d{2})\s*(am|pm|AM|PM)?", text)
    if time_match:
        raw_time = time_match.group(1)
        meridiem = time_match.group(2) or ""
        time_str = _to_24h(raw_time + " " + meridiem) if meridiem else raw_time

    date_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2})",
        text, re.I
    )
    year_match = re.search(r"\b(20\d{2})\b", text)
    if date_match:
        month = date_match.group(1)
        day = int(date_match.group(2))
        year = int(year_match.group(1)) if year_match else datetime.now().year
        month_num = MONTHS.get(month.lower(), 1)
        try:
            dt = datetime(year, month_num, day)
            if dt.date() < date.today():
                return "", ""
            return dt.strftime("%Y-%m-%d"), time_str
        except ValueError:
            pass

    # Try ISO date in datetime attribute
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        iso_date = iso.group(1)
        try:
            if datetime.strptime(iso_date, "%Y-%m-%d").date() < date.today():
                return "", ""
        except ValueError:
            pass
        return iso_date, time_str

    return "", time_str


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Heritage & History"


def scrape_nmaahc_events() -> List[Dict]:
    """Scrape events from the NMAAHC."""
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
        resp = requests.get(NMAAHC_EVENTS_URL, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # NMAAHC: <div class="teaser teaser--event ...">
        cards = soup.select(".teaser--event")
        if not cards:
            # Broader fallback
            cards = soup.select(".teaser")

        for card in cards[:40]:
            try:
                title_el = card.select_one("h2, h3, h4, .teaser__title")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                link = title_el.find("a", href=True) or card.find("a", href=True)
                url = ""
                if link:
                    href = link["href"]
                    url = href if href.startswith("http") else NMAAHC_BASE + href
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                # Date: look for time tag or date-like divs
                date_el = (
                    card.find("time")
                    or card.select_one(".teaser__date, [class*=date], [class*=time]")
                )
                date_str, time_str = "", ""
                if date_el:
                    raw = date_el.get("datetime") or date_el.get_text(strip=True)
                    date_str, time_str = _parse_date(raw)
                if not date_str:
                    continue

                desc_el = card.select_one(".teaser__description, .teaser__body, p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or ""
                    image_url = src if src.startswith("http") else (NMAAHC_BASE + src if src else "")

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "end_time": "",
                    "location": LOCATION,
                    "location_name": "National Museum of African American History and Culture",
                    "location_address": "1400 Constitution Ave NW, Washington, DC 20560",
                    "neighborhood": "National Mall",
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "National Museum of African American History and Culture",
                    "borough": BOROUGH,
                    "image_url": image_url,
                    "price": "Free",
                    "is_free": True,
                    "is_family_friendly": any(w in (title+" "+description).lower() for w in ["family","kids","children","all ages"]),
                    "is_outdoor": any(w in (title+" "+description).lower() for w in ["outdoor","garden","plaza","open air"]),
                    "city": "Washington DC",
                })
            except Exception as e:
                logger.debug(f"NMAAHC: error parsing card: {e}")

    except Exception as e:
        logger.error(f"NMAAHC scraper failed: {e}")

    logger.info(f"NMAAHC: scraped {len(events)} events")
    return events
