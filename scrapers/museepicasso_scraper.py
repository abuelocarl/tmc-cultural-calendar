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
from datetime import datetime, date, timedelta
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
    """
    Parse date from text. Handles:
    - ISO: '2026-03-12'
    - Plain: '12 March 2026'
    - Range: 'From 12 March 2024 to 12 March 2027' — uses today if ongoing, start if future
    """
    if not text:
        return ""
    today = date.today()

    # ISO date
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        d = iso.group(1)
        try:
            if datetime.strptime(d, "%Y-%m-%d").date() < today:
                return ""
        except ValueError:
            pass
        return d

    # "From DD Month YYYY to DD Month YYYY" range pattern
    range_m = re.search(
        r"[Ff]rom\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{4})\s+to\s+(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|"
        r"November|December)\s+(\d{4})", text, re.I
    )
    if range_m:
        try:
            start_dt = datetime.strptime(
                f"{range_m.group(1)} {range_m.group(2)} {range_m.group(3)}", "%d %B %Y"
            )
            end_dt = datetime.strptime(
                f"{range_m.group(4)} {range_m.group(5)} {range_m.group(6)}", "%d %B %Y"
            )
            if end_dt.date() < today:
                return ""  # exhibition has ended
            if start_dt.date() <= today:
                return today.strftime("%Y-%m-%d")  # ongoing — use today
            return start_dt.strftime("%Y-%m-%d")  # future start
        except ValueError:
            pass

    # Single plain date
    date_match = re.search(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s*(\d{4})?", text, re.I
    )
    if date_match:
        day = int(date_match.group(1))
        year_s = date_match.group(3)
        year = int(year_s) if year_s else datetime.now().year
        try:
            dt = datetime.strptime(f"{day} {date_match.group(2)} {year}", "%d %B %Y")
            if dt.date() < today:
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

        # Picasso agenda uses <article class="node exhibition ..."> cards
        cards = soup.find_all("article", class_=re.compile(r"node"))
        if not cards:
            selectors = [
                ".event-card", ".event-item", ".agenda-item",
                "[class*='event']", "[class*='agenda']",
            ]
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
                # Strip leading noise like "Image Image"
                title = re.sub(r"^(?:Image\s+)+", "", title).strip()
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

                # Date: try <time>, [class*='date'], or full card text (for "From X to Y" range)
                date_el = card.find("time") or card.select_one("[class*='date']")
                date_str = ""
                if date_el:
                    raw = date_el.get("datetime") or date_el.get_text(strip=True)
                    date_str = _parse_date(raw)
                if not date_str:
                    # Fall back to full card text (handles "From DD Month YYYY to DD Month YYYY")
                    date_str = _parse_date(card.get_text(" ", strip=True))
                if not date_str:
                    continue

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
