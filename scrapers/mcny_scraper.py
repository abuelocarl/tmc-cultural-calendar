"""
Museum of the City of New York (MCNY) - Events Scraper
Scrapes upcoming events from https://www.mcny.org/events
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mcny.org"
EVENTS_URL = f"{BASE_URL}/events"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_mcny_date(date_str: str):
    """
    Parse MCNY date strings like 'Thursday, April 2, 6:30pm' or 'Thursday, April 2'.
    Returns (date_iso, time_str).
    """
    if not date_str:
        return "", ""

    cleaned = date_str.strip()

    # Extract time portion (e.g. '6:30pm', '7pm')
    time_match = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))", cleaned, re.I)
    time_str = time_match.group(1) if time_match else ""

    # Strip weekday and time to get just the date
    date_part = re.sub(r"^[A-Za-z]+,\s*", "", cleaned)
    date_part = re.sub(r",?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*$", "", date_part, flags=re.I).strip()

    date_iso = ""
    for fmt in ("%B %d, %Y", "%B %d"):
        try:
            dt = datetime.strptime(date_part, fmt)
            if fmt == "%B %d":
                dt = dt.replace(year=datetime.today().year)
            date_iso = dt.strftime("%Y-%m-%d")
            break
        except ValueError:
            continue

    return date_iso, time_str


def scrape_mcny_events() -> List[Dict]:
    """Scrape upcoming events from MCNY."""
    events = []

    try:
        response = requests.get(EVENTS_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"MCNY: failed to fetch events page: {e}")
        return events

    soup = BeautifulSoup(response.text, "html.parser")

    # Events are in <article class="card"> elements
    cards = soup.find_all("article", class_="card")

    for card in cards:
        # Title and URL: <h2><a href="...">TITLE</a></h2>
        title_el = card.find("h2")
        if not title_el:
            continue
        link_el = title_el.find("a")
        if not link_el:
            continue
        title = link_el.get_text(strip=True)
        href = link_el.get("href", "")
        url = href if href.startswith("http") else BASE_URL + href
        if not title:
            continue

        # Date: <span class="date">
        date_el = card.find("span", class_="date")
        date_str = date_el.get_text(strip=True) if date_el else ""
        date_iso, time_str = _parse_mcny_date(date_str)

        # Category: <span class="category"><a>
        cat_el = card.find("span", class_="category")
        category_raw = ""
        if cat_el:
            cat_link = cat_el.find("a")
            category_raw = cat_link.get_text(strip=True) if cat_link else cat_el.get_text(strip=True)

        # Description: <div class="card-summary"> or hidden block
        desc_el = card.find("div", class_=re.compile(r"card-summary|hidden"))
        description = desc_el.get_text(strip=True)[:300] if desc_el else ""

        # Image
        img = card.find("img")
        image_url = img.get("src", "") if img else ""
        if image_url and not image_url.startswith("http"):
            image_url = BASE_URL + image_url

        link_text = (title + " " + description + " " + category_raw).lower()
        is_free = any(w in link_text for w in ["free", "no cost", "complimentary"])
        is_family = any(w in link_text for w in ["family", "kids", "children", "all ages"])
        events.append({
            "title": title,
            "date": date_iso,
            "end_date": "",
            "time": time_str,
            "end_time": "",
            "location": "Museum of the City of New York, 1220 Fifth Ave, New York, NY 10029",
            "location_name": "Museum of the City of New York",
            "location_address": "1220 Fifth Ave, New York, NY 10029",
            "neighborhood": "East Harlem",
            "description": description,
            "url": url,
            "category": "Heritage & History",
            "source": "Museum of the City of New York",
            "borough": "Manhattan",
            "image_url": image_url,
            "price": "Free" if is_free else "See website",
            "is_free": is_free,
            "is_family_friendly": is_family,
        })

    # Deduplicate by URL
    seen = set()
    unique = []
    for e in events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)

    logger.info(f"MCNY scraper found {len(unique)} events")
    return unique


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_mcny_events()
    print(f"\nFound {len(results)} MCNY events:")
    for ev in results:
        print(f"  [{ev['date']}] {ev['title']} | {ev['time']}")
