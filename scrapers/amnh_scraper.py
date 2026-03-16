"""
American Museum of Natural History - Events Scraper
Scrapes upcoming ticketed events from https://www.amnh.org/calendar
"""

import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

BASE_URL = "https://www.amnh.org"
CALENDAR_URL = f"{BASE_URL}/calendar"

# Map AMNH category labels to normalized project categories
CATEGORY_MAP = {
    "lectures and talks": "Arts & Culture",
    "planetarium program": "Arts & Culture",
    "science social": "Arts & Culture",
    "festival": "Festivals",
    "educator professional learning": "Arts & Culture",
    "after-hours program": "Arts & Culture",
    "member program": "Arts & Culture",
    "benefit event": "Arts & Culture",
    "event": "Arts & Culture",
}


def _parse_date_time(date_str: str):
    """
    Parse AMNH date text like:
      'Tuesday, March 17, 2026 | Sold Out 7 pm'
      'Saturday, April 18, 2026 11 am–4 pm'
    Returns (date_iso, time_str).
    """
    if not date_str:
        return "", ""

    cleaned = re.sub(r"\|\s*sold\s*out", "", date_str, flags=re.I).strip()

    date_match = re.search(
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},\s+\d{4}",
        cleaned,
        re.I,
    )
    date_iso = ""
    if date_match:
        try:
            dt = datetime.strptime(date_match.group(0), "%B %d, %Y")
            date_iso = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    time_str = ""
    if date_match:
        after_date = cleaned[date_match.end():].strip()
        time_match = re.search(
            r"(\d{1,2}(?::\d{2})?(?:\s*[–\-]\s*\d{1,2}(?::\d{2})?)?\s*(?:am|pm))",
            after_date,
            re.I,
        )
        if time_match:
            time_str = time_match.group(0).strip()

    return date_iso, time_str


def scrape_amnh_events() -> List[Dict]:
    """Scrape upcoming events from the AMNH calendar page."""
    events = []

    try:
        # cloudscraper handles Cloudflare JS challenges and sets its own headers
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        response = scraper.get(CALENDAR_URL, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"AMNH: failed to fetch calendar page: {e}")
        return events

    soup = BeautifulSoup(response.text, "html.parser")

    # Each event is <a class="amnh-calendar-new-event" href="/calendar/<slug>">
    # Structure:
    #   div.amnh-calendar-new-event__image
    #     span.amnh-label > span.title  — category label
    #   div.amnh-calendar-new-event__info
    #     h3                             — event title
    #     p.small-paragraph             — description
    #     p                             — date/time text (with <br> between date and time)
    event_links = soup.find_all("a", class_="amnh-calendar-new-event")

    for link in event_links:
        href = link.get("href", "")
        url = BASE_URL + href

        # Category
        cat_span = link.find("span", class_="title")
        category_raw = cat_span.get_text(strip=True) if cat_span else ""

        # Info block
        info = link.find("div", class_="amnh-calendar-new-event__info")
        if not info:
            continue

        # Title
        h3 = info.find("h3")
        title = h3.get_text(strip=True) if h3 else ""
        if not title:
            continue

        # Description (first <p> with class small-paragraph, or any first <p>)
        desc_p = info.find("p", class_="small-paragraph") or info.find("p")
        description = desc_p.get_text(" ", strip=True) if desc_p else ""

        # Date/time: last <p> in the info block
        all_paras = info.find_all("p")
        date_text = all_paras[-1].get_text(" ", strip=True) if all_paras else ""

        # Image
        img_span = link.find("span", class_=re.compile(r"amnh-tile__image"))
        image_url = ""
        if img_span:
            bgset = img_span.get("data-bgset", "")
            # Take the highest-res URL (first entry in srcset-style string)
            first = bgset.split(",")[0].strip().split(" ")[0] if bgset else ""
            if first:
                image_url = first if first.startswith("http") else BASE_URL + first

        date_iso, time_str = _parse_date_time(date_text)
        sold_out = bool(re.search(r"sold\s*out", date_text, re.I))

        normalized_category = CATEGORY_MAP.get(
            category_raw.lower().strip(), "Arts & Culture"
        )

        events.append({
            "title": title,
            "date": date_iso,
            "end_date": "",
            "time": time_str,
            "location": "American Museum of Natural History, 200 Central Park West, New York, NY 10024",
            "description": description[:300],
            "url": url,
            "category": normalized_category,
            "source": "AMNH",
            "borough": "Manhattan",
            "image_url": image_url,
            "price": "Sold Out" if sold_out else "See website",
            "amnh_category": category_raw,
        })

    # Deduplicate by URL
    seen = set()
    unique = []
    for e in events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)

    logger.info(f"AMNH scraper found {len(unique)} events")
    return unique


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_amnh_events()
    print(f"\nFound {len(results)} AMNH events:")
    for ev in results:
        sold = " [SOLD OUT]" if ev["price"] == "Sold Out" else ""
        print(f"  [{ev['date']}] {ev['title']}{sold}")
        print(f"           {ev['amnh_category']} | {ev['time']}")
