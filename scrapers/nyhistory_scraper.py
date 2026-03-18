"""
New-York Historical Society - Programs/Events Scraper
Scrapes upcoming programs from https://www.nyhistory.org/programs
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nyhistory.org"
PROGRAMS_URL = f"{BASE_URL}/programs"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# CSS module class prefixes (hashes change per deploy, so we match by prefix)
LINK_CLASS = re.compile(r"HalfSlildeItem_link|FullSlideItem_container")
TITLE_CLASS = re.compile(r"HalfSlildeItem_title|FullSlideItem_title")
DATE_CLASS = re.compile(r"HalfSlildeItem_date|FullSlideItem_date")
EYEBROW_CLASS = re.compile(r"HalfSlildeItem_eyebrow|FullSlideItem_eyebrow")


def _to_24h(time_raw: str) -> str:
    """Convert '6:30pm', '7 pm', '12pm' → '18:30', '19:00', '12:00'."""
    if not time_raw:
        return ""
    t = time_raw.strip().replace("\xa0", " ")
    # Handle ranges — take only start time
    t = re.split(r"[-–]", t)[0].strip()
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


def _parse_nyhistory_date(date_str: str):
    """
    Parse dates like 'Friday, June 13, 2025' or 'June 13, 2025'.
    Returns (date_iso, time_str).
    """
    if not date_str:
        return "", ""
    cleaned = re.sub(r"^[A-Za-z]+,\s*", "", date_str.strip())  # strip weekday

    # Extract time if present
    time_match = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)(?:\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))?)", cleaned, re.I)
    time_str = time_match.group(1).strip() if time_match else ""

    # Strip time from date portion
    date_part = re.sub(r",?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm).*$", "", cleaned, flags=re.I).strip()

    date_iso = ""
    for fmt in ("%B %d, %Y", "%B %d"):
        try:
            dt = datetime.strptime(date_part, fmt)
            if fmt == "%B %d":
                dt = dt.replace(year=datetime.today().year)
            if dt.date() < date.today():
                return "", ""
            date_iso = dt.strftime("%Y-%m-%d")
            break
        except ValueError:
            continue

    return date_iso, _to_24h(time_str)


def scrape_nyhistory_events() -> List[Dict]:
    """Scrape upcoming programs from the New-York Historical Society."""
    events = []

    try:
        response = requests.get(PROGRAMS_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"NY Historical: failed to fetch programs page: {e}")
        return events

    soup = BeautifulSoup(response.text, "html.parser")

    # Programs are <a> elements whose class matches HalfSlildeItem_link (CSS modules with hash suffix)
    program_links = soup.find_all("a", class_=LINK_CLASS)

    # Fallback: find all <a> elements with href starting /programs/ that have title content
    if not program_links:
        program_links = soup.find_all(
            "a", href=re.compile(r"^/programs/[^/]+")
        )

    for link in program_links:
        href = link.get("href", "")
        if not href or href == "/programs" or href == "/programs/":
            continue
        url = BASE_URL + href if href.startswith("/") else href

        # Title: from aria-label, or <h3> with matching class, or first <h3>
        title = link.get("aria-label", "").strip()
        if not title:
            title_el = link.find(class_=TITLE_CLASS) or link.find("h3") or link.find("h2")
            title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        # Date
        date_el = link.find(class_=DATE_CLASS)
        date_str = date_el.get_text(strip=True) if date_el else ""
        date_iso, time_str = _parse_nyhistory_date(date_str)

        # Category / eyebrow
        eyebrow_el = link.find(class_=EYEBROW_CLASS)
        category_raw = eyebrow_el.get_text(strip=True) if eyebrow_el else ""

        # Description (RichText container below title)
        desc_el = link.find(class_=re.compile(r"HalfSlildeItem_description|FullSlideItem_description"))
        description = ""
        if desc_el:
            rich_text = desc_el.find(class_=re.compile(r"RichText_container"))
            description = (rich_text or desc_el).get_text(" ", strip=True)[:300]

        # Image: second <img> in the image div (first is print-hidden)
        image_url = ""
        img_div = link.find(class_=re.compile(r"HalfSlildeItem_image|FullSlideItem_image"))
        if img_div:
            imgs = img_div.find_all("img")
            visible = [i for i in imgs if "display:none" not in (i.get("style") or "")]
            img = visible[-1] if visible else (imgs[-1] if imgs else None)
            if img:
                image_url = img.get("src", "")

        link_text = (title + " " + description + " " + category_raw).lower()
        is_free = any(w in link_text for w in ["free", "no cost", "complimentary"])
        is_family = any(w in link_text for w in ["family", "kids", "children", "all ages"])
        events.append({
            "title": title,
            "date": date_iso,
            "end_date": "",
            "time": time_str,
            "end_time": "",
            "location": "New-York Historical Society, 170 Central Park West, New York, NY 10024",
            "location_name": "New-York Historical Society",
            "location_address": "170 Central Park West, New York, NY 10024",
            "neighborhood": "Upper West Side",
            "description": description,
            "url": url,
            "category": "Heritage & History",
            "source": "New-York Historical Society",
            "borough": "Manhattan",
            "image_url": image_url,
            "price": "Free" if is_free else "See website",
            "is_free": is_free,
            "is_family_friendly": is_family,
            "city": "New York",
        })

    # Filter to upcoming events only and deduplicate by URL
    today = datetime.today().strftime("%Y-%m-%d")
    seen = set()
    unique = []
    for e in events:
        if e["url"] not in seen and (e["date"] and e["date"] >= today):
            seen.add(e["url"])
            unique.append(e)

    logger.info(f"NY Historical scraper found {len(unique)} events")
    return unique


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_nyhistory_events()
    print(f"\nFound {len(results)} NY Historical events:")
    for ev in results:
        print(f"  [{ev['date']}] {ev['title']} | {ev['nyhistory_category']}")
