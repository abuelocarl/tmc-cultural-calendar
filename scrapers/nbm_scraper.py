"""
National Building Museum — Washington DC
Events: https://nbm.org/events/

Actual HTML (The Events Calendar / tribe):
<article class="tribe-events-calendar-list__event ...">
  <img class="tribe-events-calendar-list__event-featured-image" ...>
  <h4 class="tribe-events-calendar-list__event-title ...">
    <a class="tribe-events-calendar-list__event-title-link ..." href="...">Event Title</a>
  </h4>
  <time class="tribe-events-calendar-list__event-datetime" datetime="YYYY-MM-DD">
    <span class="tribe-event-date-start">March 18 @ 6:00 pm</span>
    - <span class="tribe-event-time">8:00 pm</span>
  </time>
  <div class="tribe-events-calendar-list__event-description ...">...</div>
</article>
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import List, Dict

logger = logging.getLogger(__name__)

NBM_EVENTS_URL = "https://nbm.org/events/"
NBM_BASE = "https://nbm.org"
LOCATION = "National Building Museum, 401 F St NW, Washington, DC 20001"
BOROUGH = "Penn Quarter"

CATEGORY_MAP = {
    "lecture": "Heritage & History",
    "talk": "Heritage & History",
    "tour": "Heritage & History",
    "architecture": "Arts & Culture",
    "design": "Arts & Culture",
    "exhibition": "Arts & Culture",
    "family": "Community",
    "kids": "Community",
    "workshop": "Community",
    "film": "Arts & Culture",
    "symposium": "Heritage & History",
    "opening": "Arts & Culture",
    "building": "Heritage & History",
    "urban": "Heritage & History",
}


def _to_24h(time_raw: str) -> str:
    """Convert '6:00 pm', '11am', '12:00 PM' → '18:00', '11:00', '12:00'."""
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


def _parse_tribe_time(text: str) -> str:
    """Extract start time from 'March 18 @ 6:00 pm' → '18:00'."""
    if not text:
        return ""
    m = re.search(r"@\s*(\d{1,2}:\d{2}\s*(?:am|pm))", text, re.I)
    return _to_24h(m.group(1)) if m else ""


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_nbm_events() -> List[Dict]:
    """Scrape events from the National Building Museum."""
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
        resp = requests.get(NBM_EVENTS_URL, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # The Events Calendar (tribe) plugin
        cards = soup.select(".tribe-events-calendar-list__event")

        for card in cards[:40]:
            try:
                title_el = card.select_one(
                    ".tribe-events-calendar-list__event-title-link"
                ) or card.find(["h3", "h4"])
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = title_el.get("href") or (title_el.find("a") or {}).get("href", "")
                url = href if href.startswith("http") else (NBM_BASE + href if href else "")
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                # Date from <time datetime="YYYY-MM-DD">
                time_el = card.select_one(".tribe-events-calendar-list__event-datetime")
                date_str = ""
                time_str = ""
                if time_el:
                    date_str = time_el.get("datetime", "")[:10]
                    start_span = time_el.select_one(".tribe-event-date-start")
                    if start_span:
                        time_str = _parse_tribe_time(start_span.get_text(strip=True))
                # Skip past or undated events
                if not date_str:
                    continue
                try:
                    if datetime.strptime(date_str, "%Y-%m-%d").date() < date.today():
                        continue
                except ValueError:
                    continue

                desc_el = card.select_one(
                    ".tribe-events-calendar-list__event-description, .tribe-common-b2, p"
                )
                description = desc_el.get_text(strip=True) if desc_el else ""

                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or ""
                    image_url = src if src.startswith("http") else (NBM_BASE + src if src else "")

                price = "See website"
                if "free" in (title + " " + description).lower():
                    price = "Free"

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "end_time": "",
                    "location": LOCATION,
                    "location_name": "National Building Museum",
                    "location_address": "401 F St NW, Washington, DC 20001",
                    "neighborhood": "Penn Quarter",
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "National Building Museum",
                    "borough": BOROUGH,
                    "image_url": image_url,
                    "price": price,
                    "is_free": False,
                    "is_family_friendly": any(w in (title+" "+description).lower() for w in ["family","kids","children","all ages"]),
                    "is_outdoor": any(w in (title+" "+description).lower() for w in ["outdoor","garden","plaza","open air"]),
                    "city": "Washington DC",
                })
            except Exception as e:
                logger.debug(f"NBM: error parsing card: {e}")

    except Exception as e:
        logger.error(f"NBM scraper failed: {e}")

    logger.info(f"National Building Museum: scraped {len(events)} events")
    return events
