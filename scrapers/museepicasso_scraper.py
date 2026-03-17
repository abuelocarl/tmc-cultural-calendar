"""
Musée Picasso Paris — Paris, France
Events: https://www.museepicassoparis.fr/en/agenda

Uses requests + BeautifulSoup. The Picasso Museum site uses a
relatively accessible agenda structure.
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

PICASSO_URLS = [
    "https://www.museepicassoparis.fr/en/agenda",
    "https://www.museepicassoparis.fr/en/events",
]
PICASSO_BASE = "https://www.museepicassoparis.fr"
LOCATION = "Musée Picasso Paris, 5 Rue de Thorigny, 75003 Paris, France"
ARRONDISSEMENT = "3rd Arrondissement"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_MAP = {
    "exhibition": "Arts & Culture",
    "conference": "Heritage & History",
    "lecture": "Heritage & History",
    "tour": "Heritage & History",
    "workshop": "Community",
    "family": "Community",
    "children": "Community",
    "performance": "Arts & Culture",
    "concert": "Music",
    "film": "Arts & Culture",
}


def _parse_date(text: str) -> str:
    if not text:
        return ""
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        return iso.group(1)
    date_match = re.search(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s*(\d{4})?", text, re.I
    )
    if date_match:
        day = int(date_match.group(1))
        year_s = date_match.group(3)
        year = int(year_s) if year_s else datetime.now().year
        try:
            return datetime.strptime(
                f"{day} {date_match.group(2)} {year}", "%d %B %Y"
            ).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_museepicasso_events() -> List[Dict]:
    """Scrape events from Musée Picasso Paris."""
    events = []
    seen_urls = set()

    try:
        soup = None
        for url in PICASSO_URLS:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=20)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    break
            except Exception as e:
                logger.debug(f"Picasso: {url} failed: {e}")

        if not soup:
            logger.warning("Picasso Museum: could not load agenda page")
            return events

        selectors = [
            ".event-card", ".event-item", ".agenda-item",
            "[class*='event']", "[class*='agenda']", "article",
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
                    url = href if href.startswith("http") else PICASSO_BASE + href
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                date_el = card.find("time") or card.select_one("[class*='date']")
                date_str = ""
                if date_el:
                    raw = date_el.get("datetime") or date_el.get_text(strip=True)
                    date_str = _parse_date(raw)

                desc_el = card.select_one("[class*='desc'],[class*='summary'],p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
                    image_url = src if src.startswith("http") else (PICASSO_BASE + src if src else "")

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": "",
                    "end_time": "",
                    "location": LOCATION,
                    "location_name": "Musée Picasso Paris",
                    "location_address": "5 Rue de Thorigny, 75003 Paris, France",
                    "neighborhood": "3rd Arrondissement",
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "Musée Picasso Paris",
                    "borough": ARRONDISSEMENT,
                    "image_url": image_url,
                    "price": "See website",
                    "is_free": False,
                    "is_family_friendly": any(w in (title).lower() for w in ["famille","family","enfant","kids","jeune"]),
                    "is_outdoor": False,
                    "city": "Paris",
                })
            except Exception as e:
                logger.debug(f"Picasso: error parsing card: {e}")

    except Exception as e:
        logger.error(f"Picasso Museum scraper failed: {e}")

    logger.info(f"Picasso Museum: scraped {len(events)} events")
    return events
