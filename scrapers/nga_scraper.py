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
from datetime import datetime, date, timedelta
from typing import List, Dict
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

NGA_CALENDAR_URL = "https://www.nga.gov/calendar"
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
    """Parse evd=YYYYMMDDHHmm into (date_iso, time_str); returns ('','') for past dates."""
    if not evd or len(evd) < 8:
        return "", ""
    try:
        year = int(evd[0:4])
        month = int(evd[4:6])
        day = int(evd[6:8])
        dt = datetime(year, month, day)
        if dt.date() < date.today() or dt.date() > date.today() + timedelta(days=183):
            return "", ""
        date_str = dt.strftime("%Y-%m-%d")
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


def _parse_ampm_time(text: str) -> str:
    """Convert '11:00 a.m.' or '1:30 p.m.' to 24h 'HH:MM'. Returns '' on failure."""
    text = text.strip().replace("\u202f", " ").replace("\xa0", " ")
    m = re.match(r"(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)", text, re.I)
    if not m:
        return ""
    hour, minute, meridiem = int(m.group(1)), int(m.group(2)), m.group(3).lower().replace(".", "")
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _parse_page(soup, seen_urls, today, cap) -> List[Dict]:
    """Extract events from a single NGA calendar page."""
    events = []

    for item in soup.select("div.c-event-list-item"):
        try:
            # Title link — carries evd= param and all sub-fields
            a = item.select_one("a.c-event-list-item__title")
            if not a:
                continue

            href = a.get("href", "")
            url = href if href.startswith("http") else NGA_BASE + href

            evd_match = re.search(r"evd=(\d+)", href)
            if not evd_match:
                continue
            date_str, _ = _parse_evd(evd_match.group(1))
            if not date_str:
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Title from h4 span
            title_el = a.select_one("h4 span, h4")
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            # Event type (eyebrow label)
            type_el = a.select_one("span.f-text--eyebrow")
            event_type = type_el.get_text(strip=True) if type_el else ""

            # Location within gallery (p inside the link)
            loc_detail_el = a.select_one("p")
            loc_detail = loc_detail_el.get_text(strip=True) if loc_detail_el else ""

            # Time from meta div: "11:00 a.m. | – | 12:00 p.m."
            meta = item.select_one("div.c-event-list-item__meta")
            time_str = end_time_str = ""
            if meta:
                meta_parts = [t.strip() for t in meta.get_text(separator="|").split("|") if t.strip() and t.strip() != "–"]
                if meta_parts:
                    time_str = _parse_ampm_time(meta_parts[0])
                if len(meta_parts) >= 2:
                    end_time_str = _parse_ampm_time(meta_parts[-1])

            # Image
            img = item.find("img")
            image_url = ""
            if img:
                src = img.get("src") or img.get("data-src") or ""
                image_url = src if src.startswith("http") else (NGA_BASE + src if src.startswith("/") else src)

            # Build description from event type + gallery location
            description = " · ".join(filter(None, [event_type, loc_detail]))

            events.append({
                "title": title,
                "date": date_str,
                "time": time_str,
                "end_time": end_time_str,
                "location": LOCATION,
                "location_name": "National Gallery of Art",
                "location_address": "6th St & Constitution Ave NW, Washington, DC 20565",
                "neighborhood": "National Mall",
                "description": description[:400],
                "url": url,
                "category": _infer_category(title, description),
                "source": "National Gallery of Art",
                "borough": BOROUGH,
                "image_url": image_url,
                "price": "Free",
                "is_free": True,
                "is_family_friendly": any(w in (title + " " + description).lower() for w in ["family", "kids", "children", "all ages"]),
                "is_outdoor": any(w in (title + " " + description).lower() for w in ["outdoor", "garden", "plaza", "open air"]),
                "city": "Washington DC",
            })
        except Exception as e:
            logger.debug(f"NGA: error parsing item: {e}")

    return events


def scrape_nga_events() -> List[Dict]:
    """Scrape events from the National Gallery of Art, paginating across all future dates."""
    events = []
    seen_urls = set()
    today = date.today()
    cap = today + timedelta(days=183)

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )

        params = {
            "visit_start": today.strftime("%Y-%m-%d"),
            "visit_end": cap.strftime("%Y-%m-%d"),
        }

        page = 0
        while True:
            params["page"] = page
            resp = scraper.get(NGA_CALENDAR_URL, params=params, timeout=25)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            page_events = _parse_page(soup, seen_urls, today, cap)
            events.extend(page_events)

            # Stop if no events found on this page or no next-page link
            has_next = soup.select_one(f'a[href*="page={page + 1}"]')
            if not page_events or not has_next:
                break

            page += 1
            if page > 60:   # safety cap
                break

    except Exception as e:
        logger.error(f"NGA scraper failed: {e}")

    logger.info(f"NGA: scraped {len(events)} events")
    return events
