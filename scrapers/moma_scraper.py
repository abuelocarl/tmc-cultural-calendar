"""
Museum of Modern Art (MoMA) - Events Scraper
Scrapes upcoming events from https://www.moma.org/calendar/
"""

import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, date
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

BASE_URL = "https://www.moma.org"
CALENDAR_URL = f"{BASE_URL}/calendar/"

CATEGORY_MAP = {
    "gallery experience": "Arts & Culture",
    "film": "Arts & Culture",
    "talk": "Arts & Culture",
    "performance": "Arts & Culture",
    "music": "Music",
    "dance": "Dance",
    "workshop": "Arts & Culture",
    "tour": "Arts & Culture",
    "for members": "Arts & Culture",
    "family": "Arts & Culture",
}


def _to_24h(time_raw: str) -> str:
    """Convert MoMA time formats to HH:MM 24h.
    Handles: '4:00\xa0p.m.', '6:00–8:00\xa0p.m.', '7:00 p.m.', '10:00 a.m.'
    Returns only the start time (ignores range end).
    """
    if not time_raw:
        return ""
    # Normalize non-breaking space and p.m./a.m. notation
    t = time_raw.replace("\xa0", " ")
    t = re.sub(r"p\.m\.", "pm", t, flags=re.I)
    t = re.sub(r"a\.m\.", "am", t, flags=re.I)
    # Extract only the start time (before any range separator)
    t = re.split(r"[–\-]", t)[0].strip()
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", t, re.I)
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


def _to_24h_end(time_raw: str) -> str:
    """Extract end time from range like '6:00–8:00\xa0p.m.' → '20:00'."""
    if not time_raw:
        return ""
    t = time_raw.replace("\xa0", " ")
    t = re.sub(r"p\.m\.", "pm", t, flags=re.I)
    t = re.sub(r"a\.m\.", "am", t, flags=re.I)
    parts = re.split(r"[–\-]", t)
    if len(parts) < 2:
        return ""
    return _to_24h(parts[1].strip())


def _parse_moma_date(date_str: str) -> str:
    """
    Parse MoMA date strings like 'Sun, Mar 15' or 'Mon, Mar 16' into ISO format.
    Assumes current or next year based on month context.
    """
    if not date_str:
        return ""
    date_str = re.sub(r"^[A-Za-z]{3},\s*", "", date_str.strip())  # strip weekday
    today = date.today()
    for year in [today.year, today.year + 1]:
        try:
            dt = datetime.strptime(f"{date_str} {year}", "%b %d %Y")
            if dt.date() >= today:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def scrape_moma_events() -> List[Dict]:
    """Scrape upcoming events from MoMA's calendar."""
    events = []

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        response = scraper.get(CALENDAR_URL, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"MoMA: failed to fetch calendar: {e}")
        return events

    soup = BeautifulSoup(response.text, "html.parser")

    # The event list: <ul aria-label="Events"> contains date-group <li> items,
    # each with a date heading and a nested <ul> of event <li>s.
    event_list = soup.find("ul", attrs={"aria-label": "Events"})
    if not event_list:
        # Fallback: find all event links directly
        event_links = soup.find_all("a", href=re.compile(r"^/calendar/events/\d+"))
        date_iso = ""
    else:
        # Iterate date groups
        date_groups = event_list.find_all("li", recursive=False)
        for group in date_groups:
            # Date heading: <h2> nested inside the sticky left-column div
            date_text = ""
            heading = group.find("h2")
            if heading:
                date_text = heading.get_text(strip=True)

            date_iso = _parse_moma_date(date_text)

            # Find event links in this group
            group_links = group.find_all("a", href=re.compile(r"^/calendar/events/\d+"))
            for link in group_links:
                _parse_and_append(link, date_iso, events)

        # If date-group parsing found nothing, fall back to flat link scan
        if not events:
            for link in soup.find_all("a", href=re.compile(r"^/calendar/events/\d+")):
                _parse_and_append(link, "", events)

    # Deduplicate by URL
    seen = set()
    unique = []
    for e in events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)

    logger.info(f"MoMA scraper found {len(unique)} events")
    return unique


def _parse_and_append(link, date_iso: str, events: List[Dict]) -> None:
    """Extract fields from a MoMA event <a> tag and append to events list."""
    href = link.get("href", "")
    url = BASE_URL + href if href.startswith("/") else href

    # Title: <p class="...typography/truncate:5..."><span class="balance-text">
    title = ""
    title_p = link.find("p", class_=re.compile(r"truncate"))
    if title_p:
        title = title_p.get_text(strip=True)

    if not title:
        # Fallback: first heading-like element
        h = link.find(["h2", "h3", "h4"])
        if h:
            title = h.get_text(strip=True)
    if not title:
        return

    # All scale-down paragraphs: [0]=time, [1]=location, [2]=event type
    detail_paras = link.find_all("p", class_=re.compile(r"scale:down|scale-down"))
    raw_time    = detail_paras[0].get_text(strip=True) if len(detail_paras) > 0 else ""
    time_str    = _to_24h(raw_time)
    end_time_cv = _to_24h_end(raw_time)
    location_raw = detail_paras[1].get_text(strip=True) if len(detail_paras) > 1 else ""
    event_type = detail_paras[2].get_text(strip=True) if len(detail_paras) > 2 else ""

    full_location = "MoMA, 11 W 53rd St, New York, NY 10019"
    loc_name = "Museum of Modern Art"
    loc_addr = "11 W 53rd St, New York, NY 10019"
    if location_raw and location_raw.lower() not in ("moma", ""):
        full_location = f"{location_raw} — MoMA, 11 W 53rd St, New York, NY 10019"
        loc_name = location_raw

    category = CATEGORY_MAP.get(event_type.lower().strip(), "Arts & Culture")

    # Detect free / family / after-hours from link text
    link_text = link.get_text(" ", strip=True).lower()
    is_free = any(w in link_text for w in ["free", "no cost", "no charge"])
    is_family = any(w in link_text for w in ["family", "kids", "children", "all ages"])
    if event_type.lower() in ("family",):
        is_family = True
    price = "Free" if is_free else "See website"

    events.append({
        "title": title,
        "date": date_iso,
        "end_date": "",
        "time": time_str,
        "end_time": end_time_cv,
        "location": full_location,
        "location_name": loc_name,
        "location_address": loc_addr,
        "neighborhood": "Midtown West",
        "description": event_type,
        "url": url,
        "category": category,
        "source": "Museum of Modern Art",
        "borough": "Manhattan",
        "image_url": "",
        "price": price,
        "is_free": is_free,
        "is_family_friendly": is_family,
        "city": "New York",
    })


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_moma_events()
    print(f"\nFound {len(results)} MoMA events:")
    for ev in results:
        print(f"  [{ev['date']}] {ev['title']} | {ev['time']}")
