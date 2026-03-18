"""
Musée d'Orsay — Paris, France
Events: https://www.musee-orsay.fr/en/whats-on

Uses cloudscraper; falls back gracefully if JS-rendered.
"""

import logging
import re
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import List, Dict

logger = logging.getLogger(__name__)

ORSAY_URLS = [
    "https://www.musee-orsay.fr/en/whats-on",
    "https://www.musee-orsay.fr/en/whats-on/all-events",
]
ORSAY_BASE = "https://www.musee-orsay.fr"
LOCATION = "Musée d'Orsay, 1 Rue de la Légion d'Honneur, 75007 Paris, France"
ARRONDISSEMENT = "7th Arrondissement"

CATEGORY_MAP = {
    "exhibition": "Arts & Culture",
    "concert": "Music",
    "conference": "Heritage & History",
    "lecture": "Heritage & History",
    "tour": "Heritage & History",
    "workshop": "Community",
    "film": "Arts & Culture",
    "performance": "Arts & Culture",
    "festival": "Festivals",
    "family": "Community",
    "children": "Community",
    "impressionism": "Arts & Culture",
    "painting": "Arts & Culture",
}


def _parse_date(text: str) -> str:
    if not text:
        return ""
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        d = iso.group(1)
        try:
            if datetime.strptime(d, "%Y-%m-%d").date() < date.today():
                return ""
        except ValueError:
            pass
        return d
    date_match = re.search(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s*(\d{4})?", text, re.I
    )
    if date_match:
        day = int(date_match.group(1))
        month_str = date_match.group(2)
        year_s = date_match.group(3)
        year = int(year_s) if year_s else datetime.now().year
        try:
            dt = datetime.strptime(f"{day} {month_str} {year}", "%d %B %Y")
            if dt.date() < date.today():
                return ""
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_orsay_events() -> List[Dict]:
    """Scrape events from Musée d'Orsay."""
    events = []
    seen_urls = set()

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )

        soup = None
        for url in ORSAY_URLS:
            try:
                resp = scraper.get(url, timeout=20)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    break
            except Exception as e:
                logger.debug(f"Orsay: {url} failed: {e}")

        if not soup:
            logger.warning("Orsay: could not load events page")
            return events

        selectors = [
            ".event-card", ".event-item", ".agenda-item", ".program-item",
            "[class*='event']", "[class*='agenda']", "[class*='program']", "article",
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
                    url = href if href.startswith("http") else ORSAY_BASE + href
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                date_el = card.find("time") or card.select_one("[class*='date']")
                date_str = ""
                if date_el:
                    raw = date_el.get("datetime") or date_el.get_text(strip=True)
                    date_str = _parse_date(raw)
                if not date_str:
                    continue

                desc_el = card.select_one("[class*='desc'],[class*='summary'],p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or ""
                    image_url = src if src.startswith("http") else (ORSAY_BASE + src if src else "")

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": "",
                    "end_time": "",
                    "location": LOCATION,
                    "location_name": "Musée d'Orsay",
                    "location_address": "1 Rue de la Légion d'Honneur, 75007 Paris, France",
                    "neighborhood": "7th Arrondissement",
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "Musée d'Orsay",
                    "borough": ARRONDISSEMENT,
                    "image_url": image_url,
                    "price": "See website",
                    "is_free": False,
                    "is_family_friendly": any(w in (title).lower() for w in ["famille","family","enfant","kids","jeune"]),
                    "is_outdoor": False,
                    "city": "Paris",
                })
            except Exception as e:
                logger.debug(f"Orsay: error parsing card: {e}")

    except Exception as e:
        logger.error(f"Orsay scraper failed: {e}")

    logger.info(f"Orsay: scraped {len(events)} events")
    return events
