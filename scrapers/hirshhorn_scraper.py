"""
Hirshhorn Museum and Sculpture Garden — Washington DC
Events: https://hirshhorn.si.edu/art-and-programs/

Uses cloudscraper to handle JS challenges. Falls back across multiple URL paths.
"""

import logging
import re
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

HIRSHHORN_URLS = [
    "https://hirshhorn.si.edu/art-and-programs/",
    "https://hirshhorn.si.edu/explore/",
]
HIRSHHORN_BASE = "https://hirshhorn.si.edu"
LOCATION = "Hirshhorn Museum and Sculpture Garden, Independence Ave SW & 7th St SW, Washington, DC 20560"
BOROUGH = "National Mall"

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

CATEGORY_MAP = {
    "exhibition": "Arts & Culture",
    "talk": "Heritage & History",
    "lecture": "Heritage & History",
    "opening": "Arts & Culture",
    "tour": "Arts & Culture",
    "film": "Arts & Culture",
    "performance": "Arts & Culture",
    "screening": "Arts & Culture",
    "artist": "Arts & Culture",
    "workshop": "Community",
    "conversation": "Community",
}


def _parse_date(text: str):
    if not text:
        return "", ""
    text = text.strip()
    time_match = re.search(r"(\d{1,2}:\d{2})\s*(am|pm)?", text, re.I)
    time_str = time_match.group(0).strip() if time_match else ""
    date_match = re.search(
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+(\d{1,2})", text, re.I
    )
    year_match = re.search(r"\b(20\d{2})\b", text)
    if date_match:
        month_num = MONTHS.get(date_match.group(1).lower()[:3], 0)
        day = int(date_match.group(2))
        year = int(year_match.group(1)) if year_match else datetime.now().year
        if month_num:
            try:
                return datetime(year, month_num, day).strftime("%Y-%m-%d"), time_str
            except ValueError:
                pass
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        return iso.group(1), time_str
    return "", time_str


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_hirshhorn_events() -> List[Dict]:
    """Scrape events from the Hirshhorn Museum."""
    events = []
    seen_urls = set()

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )

        soup = None
        for url in HIRSHHORN_URLS:
            try:
                resp = scraper.get(url, timeout=18)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    break
            except Exception as e:
                logger.debug(f"Hirshhorn: {url} failed: {e}")

        if not soup:
            logger.warning("Hirshhorn: could not load any events page")
            return events

        selectors = [
            ".event-item", ".program-item", "article.post", "article.program",
            ".card", ".listing-item", "[class*='event']", "[class*='program']", "article",
        ]

        cards = []
        for sel in selectors:
            found = soup.select(sel)
            if found and len(found) > 1:
                cards = found
                break

        for card in cards[:40]:
            try:
                title_el = (
                    card.select_one("[class*='title'],[class*='heading']")
                    or card.find(["h2", "h3", "h4"])
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                link = title_el.find("a", href=True) or card.find("a", href=True)
                url = ""
                if link:
                    href = link["href"]
                    url = href if href.startswith("http") else HIRSHHORN_BASE + href
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                date_el = (
                    card.find("time")
                    or card.select_one("[class*='date'],[class*='time'],[class*='when']")
                )
                date_str, time_str = "", ""
                if date_el:
                    raw = date_el.get("datetime") or date_el.get_text(strip=True)
                    date_str, time_str = _parse_date(raw)

                desc_el = card.select_one("[class*='desc'],[class*='summary'],p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or ""
                    image_url = src if src.startswith("http") else (HIRSHHORN_BASE + src if src else "")

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "end_time": "",
                    "location": LOCATION,
                    "location_name": "Hirshhorn Museum and Sculpture Garden",
                    "location_address": "Independence Ave SW & 7th St SW, Washington, DC 20560",
                    "neighborhood": "National Mall",
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "Hirshhorn Museum",
                    "borough": BOROUGH,
                    "image_url": image_url,
                    "price": "Free",
                    "is_free": True,
                    "is_family_friendly": any(w in (title+" "+description).lower() for w in ["family","kids","children","all ages"]),
                    "is_outdoor": any(w in (title+" "+description).lower() for w in ["outdoor","garden","plaza","open air"]),
                    "city": "Washington DC",
                })
            except Exception as e:
                logger.debug(f"Hirshhorn: error parsing card: {e}")

    except Exception as e:
        logger.error(f"Hirshhorn scraper failed: {e}")

    logger.info(f"Hirshhorn: scraped {len(events)} events")
    return events
