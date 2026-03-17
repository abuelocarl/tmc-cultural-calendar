"""
Jeu de Paume — Paris, France (8th Arrondissement)
Agenda: https://jeudepaume.org/agenda/

Real HTML structure:
<section class="agenda-grouped-events wrapper" id="agenda-events-container">
  <div class="agenda-date-group">
    <div class="agenda-date-header"><h3>17 mars 2026</h3></div>
    <ul class="agenda-events-grid-3cols">
      <li class="grid-item to-animate">
        <a class="tease e item" href="https://jeudepaume.org/evenement/...">
          <figure class="e__figure"><img src="..." /></figure>
          <div class="group-tags"><p class="e__tag">Rencontre librairie</p></div>
          <h3 class="e__title">Avec Florence Chevallier</h3>
          <p class="e__text">Mardi 17 mars 2026 • 18:00<br><span class="--place">Jeu de Paume - Paris</span></p>
        </a>
      </li>
    </ul>
  </div>
</section>
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

JEUDEPAUME_URL = "https://jeudepaume.org/agenda/"
LOCATION = "Jeu de Paume, 1 Place de la Concorde, 75008 Paris, France"
ARRONDISSEMENT = "8th Arrondissement"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

MONTHS_FR = {
    "janvier": 1, "janv": 1, "jan": 1,
    "février": 2, "févr": 2, "fév": 2,
    "mars": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "août": 8, "aout": 8,
    "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "décembre": 12, "déc": 12, "dec": 12,
}

CATEGORY_MAP = {
    "exposition": "Arts & Culture",
    "exhibition": "Arts & Culture",
    "conférence": "Heritage & History",
    "rencontre": "Heritage & History",
    "lecture": "Heritage & History",
    "performance": "Arts & Culture",
    "spectacle": "Arts & Culture",
    "concert": "Music",
    "film": "Arts & Culture",
    "atelier": "Community",
    "workshop": "Community",
    "festival": "Festivals",
    "événement": "Arts & Culture",
}


def _parse_fr_date(text: str):
    """Parse 'Mardi 17 mars 2026 • 18:00' → ('2026-03-17', '18:00')."""
    if not text:
        return "", ""
    # Time
    time_m = re.search(r"•\s*(\d{1,2}:\d{2})", text)
    time_str = time_m.group(1) if time_m else ""
    # Date
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
            for k in MONTHS_FR:
                if month_key.startswith(k):
                    month_num = MONTHS_FR[k]
                    break
        year_m = re.search(r"\b(20\d{2})\b", text)
        year = int(year_m.group(1)) if year_m else datetime.now().year
        if month_num:
            try:
                return datetime(year, month_num, day).strftime("%Y-%m-%d"), time_str
            except ValueError:
                pass
    return "", time_str


def _infer_category(tag_text: str, title: str) -> str:
    combined = (tag_text + " " + title).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_palaisdetokyo_events() -> List[Dict]:
    """Scrape events from Jeu de Paume (replaces the JS-blocked Palais de Tokyo)."""
    events = []
    seen_urls = set()

    try:
        resp = requests.get(JEUDEPAUME_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Cards are <a class="tease e item"> inside the agenda container
        cards = soup.select("a.tease.e.item, a[class*='tease'][class*='item']")
        logger.info(f"Jeu de Paume: found {len(cards)} event cards")

        for card in cards[:40]:
            try:
                title_el = card.select_one("h3.e__title, h2.e__title, [class*='title']")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                url = card.get("href", "")
                if not url.startswith("http"):
                    url = "https://jeudepaume.org" + url
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                # Date + time from p.e__text
                text_el = card.select_one("p.e__text, [class*='e__text']")
                date_str, time_str = _parse_fr_date(text_el.get_text(strip=True)) if text_el else ("", "")

                # Category from p.e__tag
                tags = [t.get_text(strip=True) for t in card.select("p.e__tag")]
                tag_text = " ".join(tags)

                # Description from p.e__subtitle
                desc_el = card.select_one("p.e__subtitle, p.e__desc, [class*='subtitle']")
                description = desc_el.get_text(strip=True) if desc_el else tag_text

                # Image
                img = card.find("img")
                image_url = img.get("src", "") if img else ""

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "end_time": "",
                    "location": LOCATION,
                    "location_name": "Jeu de Paume",
                    "location_address": "1 Place de la Concorde, 75008 Paris, France",
                    "neighborhood": "8th Arrondissement",
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(tag_text, title),
                    "source": "Jeu de Paume",
                    "borough": ARRONDISSEMENT,
                    "image_url": image_url,
                    "price": "See website",
                    "is_free": False,
                    "is_family_friendly": any(w in (title).lower() for w in ["famille","family","enfant","kids","jeune"]),
                    "is_outdoor": False,
                    "city": "Paris",
                })
            except Exception as e:
                logger.debug(f"Jeu de Paume: error parsing card: {e}")

    except Exception as e:
        logger.error(f"Jeu de Paume scraper failed: {e}")

    logger.info(f"Jeu de Paume: scraped {len(events)} events")
    return events
