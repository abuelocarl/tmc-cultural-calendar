"""
Centre Pompidou — Paris, France
Events: https://www.centrepompidou.fr/en/agenda/

Uses cloudscraper to handle JS challenges.
Selectors target the agenda listing cards.
"""

import logging
import re
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

POMPIDOU_URLS = [
    "https://www.centrepompidou.fr/en/agenda/",
    "https://www.centrepompidou.fr/en/program/agenda",
]
POMPIDOU_BASE = "https://www.centrepompidou.fr"
LOCATION = "Centre Pompidou, Place Georges-Pompidou, 75004 Paris, France"
ARRONDISSEMENT = "4th Arrondissement"

MONTHS_FR = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

CATEGORY_MAP = {
    "exhibition": "Arts & Culture",
    "exposition": "Arts & Culture",
    "concert": "Music",
    "music": "Music",
    "musique": "Music",
    "film": "Arts & Culture",
    "cinema": "Arts & Culture",
    "performance": "Arts & Culture",
    "spectacle": "Arts & Culture",
    "conference": "Heritage & History",
    "talk": "Heritage & History",
    "workshop": "Community",
    "atelier": "Community",
    "dance": "Dance",
    "danse": "Dance",
    "festival": "Festivals",
}


def _parse_date(text: str):
    if not text:
        return "", ""
    text = text.strip()
    # ISO date
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        return iso.group(1), ""
    # "18 March 2026" or "March 18, 2026"
    date_match = re.search(
        r"(\d{1,2})\s+(jan(?:vier)?|f[eé]v(?:rier)?|mars?|avr(?:il)?|mai|juin?|"
        r"juil(?:let)?|ao[uû]t?|sep(?:tembre)?|oct(?:obre)?|nov(?:embre)?|d[eé]c(?:embre)?)"
        r"\s*(\d{4})?", text, re.I
    )
    if date_match:
        day = int(date_match.group(1))
        month_str = date_match.group(2).lower()[:3]
        month_num = MONTHS_FR.get(month_str, 0)
        year_s = date_match.group(3)
        year = int(year_s) if year_s else datetime.now().year
        if month_num:
            try:
                return datetime(year, month_num, day).strftime("%Y-%m-%d"), ""
            except ValueError:
                pass
    return "", ""


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_pompidou_events() -> List[Dict]:
    """Scrape events from Centre Pompidou."""
    events = []
    seen_urls = set()

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )

        soup = None
        for url in POMPIDOU_URLS:
            try:
                resp = scraper.get(url, timeout=20)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    break
            except Exception as e:
                logger.debug(f"Pompidou: {url} failed: {e}")

        if not soup:
            logger.warning("Pompidou: could not load agenda page")
            return events

        selectors = [
            ".agenda-item", ".event-item", ".program-item",
            "[class*='agenda']", "[class*='event']", "article",
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
                    card.select_one("[class*='title'],[class*='heading'],[class*='name']")
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
                    url = href if href.startswith("http") else POMPIDOU_BASE + href
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                date_el = (
                    card.find("time")
                    or card.select_one("[class*='date'],[class*='time'],[class*='when']")
                )
                date_str = ""
                if date_el:
                    raw = date_el.get("datetime") or date_el.get_text(strip=True)
                    date_str, _ = _parse_date(raw)

                desc_el = card.select_one("[class*='desc'],[class*='summary'],[class*='intro'],p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
                    image_url = src if src.startswith("http") else (POMPIDOU_BASE + src if src else "")

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": "",
                    "location": LOCATION,
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "Pompidou",
                    "borough": ARRONDISSEMENT,
                    "image_url": image_url,
                    "price": "See website",
                    "city": "Paris",
                })
            except Exception as e:
                logger.debug(f"Pompidou: error parsing card: {e}")

    except Exception as e:
        logger.error(f"Pompidou scraper failed: {e}")

    logger.info(f"Pompidou: scraped {len(events)} events")
    return events
