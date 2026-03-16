"""
International Spy Museum — Washington DC
Events: https://www.spymuseum.org/calendar/

Actual HTML:
<div class="event_item">
  <figure class="event_figure">
    <a class="event_figure_link" href="..."><img ...></a>
  </figure>
  <div class="event_wrapper">
    <div class="event_header">
      <div class="event_detail">
        <div class="event_date">
          <span class="event_date_month">Mar</span>
          <span class="event_date_day">18</span>
        </div>
      </div>
      <div class="event_detail">
        <div class="event_time">6:30 PM ET</div>
      </div>
    </div>
    <div class="event_body">
      <h2 class="event_title">
        <a class="event_title_link" href="...">
          <span class="event_title_link_label">Event Title</span>
        </a>
      </h2>
    </div>
  </div>
</div>
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

SPY_EVENTS_URL = "https://www.spymuseum.org/calendar/"
SPY_BASE = "https://www.spymuseum.org"
LOCATION = "International Spy Museum, 700 L'Enfant Plaza SW, Washington, DC 20024"
BOROUGH = "Penn Quarter"

MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

CATEGORY_MAP = {
    "lecture": "Heritage & History",
    "talk": "Heritage & History",
    "tour": "Heritage & History",
    "family": "Community",
    "kids": "Community",
    "film": "Arts & Culture",
    "screening": "Arts & Culture",
    "trivia": "Community",
    "author": "Heritage & History",
    "book": "Heritage & History",
    "history": "Heritage & History",
    "spy": "Heritage & History",
    "intel": "Heritage & History",
    "luncheon": "Community",
    "dinner": "Community",
}


def _parse_spy_date(month_abbr: str, day: str) -> str:
    """Parse month abbreviation + day into YYYY-MM-DD."""
    month_num = MONTH_ABBR.get(month_abbr.lower()[:3], 0)
    if not month_num:
        return ""
    year = datetime.now().year
    try:
        dt = datetime(year, month_num, int(day))
        # If the date is in the past by more than 30 days, assume next year
        if (dt - datetime.now()).days < -30:
            dt = datetime(year + 1, month_num, int(day))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Heritage & History"


def scrape_spymuseum_events() -> List[Dict]:
    """Scrape events from the International Spy Museum."""
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
        resp = requests.get(SPY_EVENTS_URL, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        cards = soup.select(".event_item")

        for card in cards[:40]:
            try:
                # Title
                title_el = card.select_one(".event_title_link_label") or card.select_one(".event_title")
                if not title_el:
                    title_el = card.find(["h2", "h3", "h4"])
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                # URL
                link = card.select_one("a.event_title_link") or card.select_one("a.event_figure_link")
                url = ""
                if link:
                    href = link.get("href", "")
                    url = href if href.startswith("http") else (SPY_BASE + href if href else "")
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                # Date: month abbreviation + day number
                month_el = card.select_one(".event_date_month")
                day_el = card.select_one(".event_date_day")
                date_str = ""
                if month_el and day_el:
                    date_str = _parse_spy_date(month_el.get_text(strip=True), day_el.get_text(strip=True))

                # Time
                time_el = card.select_one(".event_time")
                time_str = ""
                if time_el:
                    raw = time_el.get_text(strip=True)
                    # Clean up e.g. "6:30 PM  ET" → "6:30 PM"
                    m = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM))", raw, re.I)
                    if m:
                        time_str = m.group(1).strip()

                # Description (not always present in list view)
                desc_el = card.select_one(".event_description, .event_body p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                # Image
                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or ""
                    image_url = src if src.startswith("http") else (SPY_BASE + src if src else "")

                price = "See website"
                if "free" in (title + " " + description).lower():
                    price = "Free"

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "location": LOCATION,
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "Spy Museum",
                    "borough": BOROUGH,
                    "image_url": image_url,
                    "price": price,
                    "city": "Washington DC",
                })
            except Exception as e:
                logger.debug(f"Spy Museum: error parsing card: {e}")

    except Exception as e:
        logger.error(f"Spy Museum scraper failed: {e}")

    logger.info(f"Spy Museum: scraped {len(events)} events")
    return events
