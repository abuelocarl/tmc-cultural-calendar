"""
National Museum of American History (NMAH) — Washington DC
Events: https://americanhistory.si.edu/events/calendar

Actual HTML structure (Drupal CMS, server-rendered, 20 cards/page):
<div class="c-view__row">
  <div class="c-card c-card--teaser">
    <div class="c-card__media"><img src="/sites/default/files/..." /></div>
    <div class="c-card__body">
      <h3 class="c-card__title"><a href="/events/calendar/...">Title</a></h3>
      <div class="c-card__end-date"><span>March 19, 2026, 7:00 - 9:30pm EDT</span></div>
      <div class="c-card__location"><span>American History Museum</span></div>
    </div>
  </div>
</div>

Pagination: ?page=1, ?page=2, ... — follow .c-pager__link--next until absent.
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

NMAH_BASE = "https://americanhistory.si.edu"
NMAH_URL = f"{NMAH_BASE}/events/calendar"
LOCATION = "National Museum of American History, 1300 Constitution Ave NW, Washington, DC 20560"
BOROUGH = "National Mall"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_MAP = {
    "film":         "Arts & Culture",
    "lecture":      "Heritage & History",
    "talk":         "Heritage & History",
    "discussion":   "Heritage & History",
    "tour":         "Heritage & History",
    "exhibition":   "Arts & Culture",
    "concert":      "Music",
    "music":        "Music",
    "performance":  "Arts & Culture",
    "workshop":     "Community",
    "family":       "Community",
    "kids":         "Community",
    "children":     "Community",
    "festival":     "Festivals",
    "celebration":  "Festivals",
    "demonstration":"Heritage & History",
    "history":      "Heritage & History",
    "symposium":    "Heritage & History",
    "conference":   "Heritage & History",
}


def _infer_category(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Heritage & History"


def _parse_date_time(dt_str: str):
    """
    Parse strings like:
      'March 19, 2026, 7:00 - 9:30pm EDT'
      'April 5, 2026, 12:00 - 1:30pm EDT'
      'March 20, 2026'
    Returns (date_iso, time_str, end_time_str).
    """
    if not dt_str:
        return "", "", ""

    # Strip timezone suffix
    cleaned = re.sub(r"\s+[A-Z]{2,4}$", "", dt_str.strip())

    # Extract date
    date_m = re.search(
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{1,2}),\s+(\d{4})",
        cleaned, re.I
    )
    date_iso = ""
    if date_m:
        try:
            dt = datetime.strptime(date_m.group(0), "%B %d, %Y")
            # Only include upcoming dates
            if date.today() <= dt.date() <= date.today() + timedelta(days=183):
                date_iso = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Extract time range: "7:00 - 9:30pm" or "12:00pm - 1:30pm"
    time_str = ""
    end_time_str = ""
    time_m = re.search(
        r"(\d{1,2}(?::\d{2})?(?:\s*[ap]m)?)\s*[-–]\s*(\d{1,2}(?::\d{2})?\s*[ap]m)",
        cleaned, re.I
    )
    if time_m:
        raw_start = time_m.group(1).strip()
        raw_end   = time_m.group(2).strip()
        # Inherit am/pm from end time if start is missing it
        end_meridiem = re.search(r"(am|pm)", raw_end, re.I)
        if end_meridiem and not re.search(r"(am|pm)", raw_start, re.I):
            raw_start += end_meridiem.group(1)
        time_str     = _to_24h(raw_start)
        end_time_str = _to_24h(raw_end)
    else:
        # Single time e.g. "7:00pm"
        single_m = re.search(r"(\d{1,2}(?::\d{2})?\s*[ap]m)", cleaned, re.I)
        if single_m:
            time_str = _to_24h(single_m.group(1).strip())

    return date_iso, time_str, end_time_str


def _to_24h(time_raw: str) -> str:
    """Convert '7:00pm', '9:30am', '12:00pm' → '19:00', '09:30', '12:00'."""
    time_raw = time_raw.strip()
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", time_raw, re.I)
    if not m:
        return time_raw
    hour   = int(m.group(1))
    minute = m.group(2) or "00"
    meridiem = m.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def scrape_nmah_events() -> List[Dict]:
    """Scrape events from the National Museum of American History calendar."""
    events = []
    seen_urls = set()
    page = 0

    while True:
        url = NMAH_URL if page == 0 else f"{NMAH_URL}?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"NMAH: failed to fetch page {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select(".c-view__row")
        logger.info(f"NMAH: page {page} — {len(rows)} rows")

        if not rows:
            break

        for row in rows:
            try:
                # Title + URL
                title_a = row.select_one(".c-card__title a")
                if not title_a:
                    continue
                title = title_a.get_text(strip=True)
                if not title:
                    continue
                href = title_a.get("href", "")
                event_url = href if href.startswith("http") else NMAH_BASE + href
                if event_url in seen_urls:
                    continue
                seen_urls.add(event_url)

                # Date + time
                dt_el = row.select_one(".c-card__end-date span, .c-card__date span")
                dt_str = dt_el.get_text(strip=True) if dt_el else ""
                date_iso, time_str, end_time_str = _parse_date_time(dt_str)

                # Skip past events (no date parsed = likely past)
                if not date_iso:
                    continue

                # Image
                img_el = row.select_one(".c-card__media img")
                image_url = ""
                if img_el:
                    src = img_el.get("src", "")
                    image_url = src if src.startswith("http") else NMAH_BASE + src

                # Description: brief — type label from card tags or location
                type_el = row.select_one(".c-card__type, .c-card__tags, [class*='type']")
                description = type_el.get_text(strip=True) if type_el else ""

                # Detect free / family / outdoor
                combined_text = (title + " " + description).lower()
                is_family = any(w in combined_text for w in ["family", "kids", "children", "all ages"])
                is_outdoor = any(w in combined_text for w in ["outdoor", "garden", "plaza", "open air"])

                events.append({
                    "title": title,
                    "date": date_iso,
                    "end_date": "",
                    "time": time_str,
                    "end_time": end_time_str,
                    "location": LOCATION,
                    "location_name": "National Museum of American History",
                    "location_address": "1300 Constitution Ave NW, Washington, DC 20560",
                    "neighborhood": "National Mall",
                    "description": description[:400],
                    "url": event_url,
                    "category": _infer_category(title, description),
                    "source": "National Museum of American History",
                    "borough": BOROUGH,
                    "image_url": image_url,
                    "price": "Free",
                    "is_free": True,
                    "is_family_friendly": is_family,
                    "is_outdoor": is_outdoor,
                    "city": "Washington DC",
                })

            except Exception as e:
                logger.debug(f"NMAH: error parsing row: {e}")

        # Follow pagination
        next_link = soup.select_one(".c-pager__link--next, a[title='Go to next page']")
        if not next_link or len(events) >= 60:
            break
        page += 1

    logger.info(f"NMAH: scraped {len(events)} events")
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_nmah_events()
    print(f"\nFound {len(results)} NMAH events:")
    for ev in results:
        end = f" → {ev['end_time']}" if ev.get("end_time") else ""
        print(f"  [{ev['date']}] {ev['title']}")
        print(f"           {ev['time']}{end} | {ev['category']}")
