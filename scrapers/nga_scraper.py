"""
National Gallery of Art (NGA) — Washington DC
Events: https://www.nga.gov/calendar.html

Actual HTML (Drupal content cards inside .views-row):
<div class="views-row">
  <div class="c-content-card ...">
    <img ...>
    <h3 class="c-content-card__title"><a href="/calendar/event-slug?evd=202603161500">Title</a></h3>
  </div>
</div>

Date is embedded in the ?evd= URL param (YYYYMMDDHHmm format).
Uses cloudscraper to bypass the 403 block on the main site.
"""

import logging
import re
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

NGA_EVENTS_URL = "https://www.nga.gov/calendar.html"
NGA_BASE = "https://www.nga.gov"
LOCATION = "National Gallery of Art, 6th St & Constitution Ave NW, Washington, DC 20565"
BOROUGH = "National Mall"

CATEGORY_MAP = {
    "talk": "Heritage & History",
    "lecture": "Heritage & History",
    "conversation": "Heritage & History",
    "concert": "Music",
    "music": "Music",
    "tour": "Arts & Culture",
    "film": "Arts & Culture",
    "family": "Community",
    "hands-on": "Community",
    "sketchbook": "Arts & Culture",
    "drawing": "Arts & Culture",
    "performance": "Arts & Culture",
    "symposium": "Heritage & History",
}


def _parse_evd(evd: str) -> tuple:
    """Parse evd=YYYYMMDDHHmm into (date_iso, time_str)."""
    if not evd or len(evd) < 8:
        return "", ""
    try:
        year = int(evd[0:4])
        month = int(evd[4:6])
        day = int(evd[6:8])
        date_str = datetime(year, month, day).strftime("%Y-%m-%d")
        time_str = ""
        if len(evd) >= 12:
            hour = int(evd[8:10])
            minute = int(evd[10:12])
            time_str = f"{hour:02d}:{minute:02d}"
        return date_str, time_str
    except (ValueError, IndexError):
        return "", ""


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_nga_events() -> List[Dict]:
    """Scrape events from the National Gallery of Art."""
    events = []
    seen_urls = set()

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        resp = scraper.get(NGA_EVENTS_URL, timeout=25)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # NGA: .views-row > .c-content-card
        cards = soup.select(".views-row .c-content-card")
        if not cards:
            cards = soup.select(".views-row")

        for card in cards[:40]:
            try:
                # Title + link
                title_el = card.find(["h2", "h3", "h4"])
                if not title_el:
                    continue
                link = title_el.find("a", href=True) or card.find("a", href=True)
                title_text = title_el.get_text(separator=" ", strip=True)
                # NGA titles sometimes have "Category:Title" format
                if ":" in title_text:
                    parts = title_text.split(":", 1)
                    title = parts[1].strip()
                else:
                    title = title_text.strip()
                if not title or len(title) < 3:
                    continue

                url = ""
                date_str = ""
                time_str = ""
                if link:
                    href = link["href"]
                    url = href if href.startswith("http") else NGA_BASE + href
                    # Extract ?evd= param
                    evd_match = re.search(r"evd=(\d+)", href)
                    if evd_match:
                        date_str, time_str = _parse_evd(evd_match.group(1))

                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                # Description from subtitle / body text
                desc_el = card.select_one(
                    ".c-content-card__description, .c-content-card__subtitle, p"
                )
                description = desc_el.get_text(strip=True) if desc_el else ""

                # Image
                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or ""
                    if src.startswith("/"):
                        src = NGA_BASE + src
                    image_url = src

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "location": LOCATION,
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title_text, description),
                    "source": "NGA",
                    "borough": BOROUGH,
                    "image_url": image_url,
                    "price": "Free",
                    "city": "Washington DC",
                })
            except Exception as e:
                logger.debug(f"NGA: error parsing card: {e}")

    except Exception as e:
        logger.error(f"NGA scraper failed: {e}")

    logger.info(f"NGA: scraped {len(events)} events")
    return events
