"""
Centre Pompidou — Paris, France
Agenda: https://www.centrepompidou.fr/fr/programme/agenda

Real HTML structure (French site):
<div class="item event-card" data-place="...">
  <a class="card-link" href="/fr/programme/agenda/evenement/...">
    <div class="event-place"><span title="...">Grand Palais, Paris</span></div>
    <div class="card-img-wrapper event-image"><img src="..." /></div>
    <div class="card-content event-description">
      <div class="event-description-header">
        <div class="card-type event-type">Exposition</div>
        <p class="card-title event-title">Matisse, 1941 – 1954</p>
      </div>
      <div class="event-description-footer">
        <div class="card-date event-date">
          <span class="dateEvenement">À partir du 24 mars 2026</span>
        </div>
      </div>
    </div>
  </a>
</div>
"""

import logging
import re
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

POMPIDOU_URL = "https://www.centrepompidou.fr/fr/programme/agenda"
POMPIDOU_BASE = "https://www.centrepompidou.fr"
LOCATION = "Centre Pompidou, Place Georges-Pompidou, 75004 Paris, France"
ARRONDISSEMENT = "4th Arrondissement"

MONTHS_FR = {
    "janv": 1, "jan": 1, "janvier": 1,
    "fév": 2, "févr": 2, "feb": 2, "février": 2,
    "mars": 3, "mar": 3,
    "avr": 4, "avril": 4,
    "mai": 5,
    "juin": 6, "jun": 6,
    "juil": 7, "juillet": 7, "jul": 7,
    "août": 8, "aout": 8, "aug": 8,
    "sept": 9, "sep": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "déc": 12, "dec": 12, "décembre": 12,
}

CATEGORY_MAP = {
    "exposition": "Arts & Culture",
    "exhibition": "Arts & Culture",
    "concert": "Music",
    "musique": "Music",
    "spectacle": "Arts & Culture",
    "performance": "Arts & Culture",
    "cinéma": "Arts & Culture",
    "cinema": "Arts & Culture",
    "film": "Arts & Culture",
    "conférence": "Heritage & History",
    "conference": "Heritage & History",
    "atelier": "Community",
    "workshop": "Community",
    "danse": "Dance",
    "dance": "Dance",
    "festival": "Festivals",
}


def _parse_fr_date(text: str) -> str:
    """Parse French date strings like 'À partir du 24 mars 2026' or '14 juin 2026'."""
    if not text:
        return ""
    text = text.strip()
    # Extract the day + month (+ optional year)
    m = re.search(
        r"(\d{1,2})\s+(janv?(?:ier)?|f[eé]v(?:r(?:ier)?)?|mars?|avr(?:il)?|mai|juin?|"
        r"juil(?:let)?|ao[uû]t?|sept?(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[eé]c(?:embre)?)"
        r"(?:\s+(\d{4}))?",
        text, re.I
    )
    if m:
        day = int(m.group(1))
        month_key = m.group(2).lower().rstrip(".")
        month_num = MONTHS_FR.get(month_key, 0)
        if not month_num:
            # try first 3-4 chars
            for k in MONTHS_FR:
                if month_key.startswith(k):
                    month_num = MONTHS_FR[k]
                    break
        year = int(m.group(3)) if m.group(3) else datetime.now().year
        if month_num:
            try:
                return datetime(year, month_num, day).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return ""


def _infer_category(type_text: str, title: str) -> str:
    combined = (type_text + " " + title).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_pompidou_events() -> List[Dict]:
    """Scrape events from Centre Pompidou (French agenda page)."""
    events = []
    seen_urls = set()

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        resp = scraper.get(POMPIDOU_URL, timeout=20)
        if resp.status_code != 200:
            logger.warning(f"Pompidou: HTTP {resp.status_code}")
            return events

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".item.event-card")
        logger.info(f"Pompidou: found {len(cards)} .item.event-card elements")

        for card in cards[:40]:
            try:
                # Title
                title_el = card.select_one(".card-title, .event-title, p[class*='title']")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                # Link
                link = card.select_one("a.card-link") or card.find("a", href=True)
                url = ""
                if link:
                    href = link.get("href", "")
                    url = href if href.startswith("http") else POMPIDOU_BASE + href
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                # Date
                date_el = card.select_one(".dateEvenement, [class*='date']")
                date_str = _parse_fr_date(date_el.get_text(strip=True)) if date_el else ""

                # Category
                type_el = card.select_one(".card-type, .event-type, [class*='type']")
                type_text = type_el.get_text(strip=True) if type_el else ""

                # Description (from subtitle or type)
                desc_el = card.select_one(".card-teaser, .event-subtitle, [class*='teaser']")
                description = desc_el.get_text(strip=True) if desc_el else type_text

                # Image
                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or ""
                    image_url = src if src.startswith("http") else (POMPIDOU_BASE + src if src else "")

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": "",
                    "location": LOCATION,
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(type_text, title),
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
