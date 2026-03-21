"""
American Museum of Natural History - Events Scraper
Scrapes upcoming ticketed events from https://www.amnh.org/calendar
"""

import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
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


def _to_24h(time_raw: str) -> str:
    """Convert '7 pm', '6:30 PM', '11 am', '12:00 pm' → '19:00', '18:30', '11:00', '12:00'."""
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


def _parse_time_range(raw: str):
    """Parse '6–8 pm', '11 am–4 pm', '7 pm' → (start_24h, end_24h)."""
    if not raw:
        return "", ""
    raw = raw.replace("\u2013", "-").replace("\u2014", "-")  # en/em dash → hyphen
    # Range: "6-8 pm", "11 am-4 pm"
    range_m = re.match(
        r"(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*-\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)",
        raw.strip(), re.I
    )
    if range_m:
        s_num, s_mer, e_num, e_mer = range_m.groups()
        s_mer = s_mer or e_mer  # "6-8 pm" → s_mer=None, borrow end's meridiem
        return _to_24h(f"{s_num} {s_mer}"), _to_24h(f"{e_num} {e_mer}")
    return _to_24h(raw.strip()), ""


def _parse_date_time(date_str: str):
    """
    Parse AMNH date text like:
      'Tuesday, March 17, 2026 | Sold Out 7 pm'
      'Saturday, April 18, 2026 11 am–4 pm'
    Returns (date_iso, raw_time_str).  raw_time_str may be a range like '6–8 pm'.
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
            if date.today() <= dt.date() <= date.today() + timedelta(days=183):
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

        date_iso, raw_time = _parse_date_time(date_text)
        if not date_iso:
            continue
        sold_out = bool(re.search(r"sold\s*out", date_text, re.I))

        normalized_category = CATEGORY_MAP.get(
            category_raw.lower().strip(), "Arts & Culture"
        )

        # Detect free / family / after-hours
        link_text = (title + " " + description + " " + category_raw).lower()
        is_free = any(w in link_text for w in ["free", "no cost", "complimentary"])
        is_family = any(w in link_text for w in ["family", "kids", "children", "all ages"])
        is_after_hours = category_raw.lower() == "after-hours program"

        # Convert time range to 24h start + end
        time_str, end_time = _parse_time_range(raw_time)

        price = "Sold Out" if sold_out else ("Free" if is_free else "See website")

        events.append({
            "title": title,
            "date": date_iso,
            "end_date": "",
            "time": time_str,
            "end_time": end_time,
            "location": "American Museum of Natural History, 200 Central Park West, New York, NY 10024",
            "location_name": "American Museum of Natural History",
            "location_address": "200 Central Park West, New York, NY 10024",
            "neighborhood": "Upper West Side",
            "description": description[:300],
            "url": url,
            "category": normalized_category,
            "source": "American Museum of Natural History",
            "borough": "Manhattan",
            "image_url": image_url,
            "price": price,
            "is_free": is_free,
            "is_family_friendly": is_family,
            "is_after_hours": is_after_hours,
            "city": "New York",
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
