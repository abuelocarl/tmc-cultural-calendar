"""
Whitney Museum of American Art - Events Scraper
Scrapes upcoming events from https://whitney.org/events
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

BASE_URL = "https://whitney.org"
EVENTS_URL = f"{BASE_URL}/events"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _to_24h(time_raw: str) -> str:
    """Convert '1 pm', '12 pm', '3:30 pm' → '13:00', '12:00', '15:30'."""
    if not time_raw:
        return ""
    t = time_raw.strip().replace("\xa0", " ")
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


def _parse_whitney_date(date_str: str):
    """
    Parse Whitney date strings like 'Monday, March 16, 2026' or 'March 16, 2026'.
    Returns (date_iso, time_str).
    """
    if not date_str:
        return "", ""

    # Try to split on newline or br — date may be 'Monday, March 16, 2026\n1 pm'
    parts = re.split(r"\n|<br\s*/?>", date_str.strip())
    date_part = parts[0].strip() if parts else date_str
    time_part = parts[1].strip() if len(parts) > 1 else ""

    # Strip weekday prefix
    date_part = re.sub(r"^[A-Za-z]+,\s*", "", date_part).strip()

    date_iso = ""
    try:
        dt = datetime.strptime(date_part, "%B %d, %Y")
        if date.today() <= dt.date() <= date.today() + timedelta(days=183):
            date_iso = dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    return date_iso, time_part


def scrape_whitney_events() -> List[Dict]:
    """Scrape upcoming events from the Whitney Museum."""
    events = []

    try:
        response = requests.get(EVENTS_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Whitney: failed to fetch events page: {e}")
        return events

    soup = BeautifulSoup(response.text, "html.parser")

    # Events are <a href="/events/<slug>"> links (not the base /events page)
    event_links = soup.find_all(
        "a",
        href=re.compile(r"^/events/[^/]+/?$"),
    )

    for link in event_links:
        href = link.get("href", "")
        url = BASE_URL + href

        # Title: <h3 class="body-large-bold ...">
        title_el = link.find("h3")
        if not title_el:
            title_el = link.find(["h2", "h4"])
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        # Date/time block: <div class="body-large"><p ...> with <br/> separating date and time
        date_text = ""
        time_str = ""
        date_div = link.find("div", class_=re.compile(r"body-large"))
        if date_div:
            date_p = date_div.find("p")
            if date_p:
                # Use separator to preserve br as newline
                raw = date_p.get_text(separator="\n").strip()
                date_iso, time_str = _parse_whitney_date(raw)
            else:
                date_iso = ""
        else:
            date_iso = ""

        # Image
        img = link.find("img")
        image_url = img.get("src", "") if img else ""

        # Detect free events, family-friendly, outdoor from link text
        link_text = link.get_text(" ", strip=True).lower()
        is_free = any(w in link_text for w in ["free", "no cost", "complimentary"])
        is_family = any(w in link_text for w in ["family", "kids", "children", "all ages"])
        is_outdoor = any(w in link_text for w in ["outdoor", "terrace", "garden", "open air"])
        price = "Free" if is_free else "See website"

        # Convert time to 24h; extract end time from ranges like "1–3 pm"
        end_time = ""
        if time_str:
            range_m = re.search(r"[-–]\s*(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)\s*$", time_str, re.I)
            if range_m:
                end_raw = range_m.group(1).strip()
                if not re.search(r"am|pm", end_raw, re.I):
                    mer_m = re.search(r"(am|pm)", time_str, re.I)
                    if mer_m:
                        end_raw += " " + mer_m.group(1)
                end_time = _to_24h(end_raw)
            time_str = _to_24h(re.split(r"[–\-]", time_str)[0].strip())

        events.append({
            "title": title,
            "date": date_iso,
            "end_date": "",
            "time": time_str,
            "end_time": end_time,
            "location": "Whitney Museum of American Art, 99 Gansevoort St, New York, NY 10014",
            "location_name": "Whitney Museum of American Art",
            "location_address": "99 Gansevoort St, New York, NY 10014",
            "neighborhood": "Meatpacking District",
            "description": "",
            "url": url,
            "category": "Arts & Culture",
            "source": "Whitney Museum of American Art",
            "borough": "Manhattan",
            "image_url": image_url,
            "price": price,
            "is_free": is_free,
            "is_family_friendly": is_family,
            "is_outdoor": is_outdoor,
            "city": "New York",
        })

    # Deduplicate by URL
    seen = set()
    unique = []
    for e in events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)

    logger.info(f"Whitney scraper found {len(unique)} events")
    return unique


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_whitney_events()
    print(f"\nFound {len(results)} Whitney events:")
    for ev in results:
        print(f"  [{ev['date']}] {ev['title']} | {ev['time']}")
