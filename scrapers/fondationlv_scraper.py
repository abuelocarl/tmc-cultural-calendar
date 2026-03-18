"""
Musée de l'Orangerie — Paris, France (1st Arrondissement)
Agenda: https://www.musee-orangerie.fr/fr/agenda

Real HTML structure:
<article class="node node--type-mediation-event ... node-agenda-list">
  <div class="image-container">
    <a href="/fr/programme/agenda/..."><figure><img src="..." /></figure></a>
  </div>
  <div class="event-content">
    <div class="event-type">
      <div class="field__item">Visites et activités adultes</div>
    </div>
    <h4>
      <a href="/fr/programme/agenda/...">
        <span class="field--name-title">English Guided Tour • ...</span>
      </a>
    </h4>
    <div class="event-informations">
      <div class="hours">à 11h00</div>
    </div>
  </div>
</article>

Note: fondationlv_scraper.py file now scrapes Musée de l'Orangerie.
Fondation Louis Vuitton blocks all automated requests (403).
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

ORANGERIE_URL = "https://www.musee-orangerie.fr/fr/agenda"
ORANGERIE_BASE = "https://www.musee-orangerie.fr"
LOCATION = "Musée de l'Orangerie, Jardin des Tuileries, 75001 Paris, France"
ARRONDISSEMENT = "1st Arrondissement"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

CATEGORY_MAP = {
    "visite": "Heritage & History",
    "tour": "Heritage & History",
    "conférence": "Heritage & History",
    "lecture": "Heritage & History",
    "atelier": "Community",
    "workshop": "Community",
    "famille": "Community",
    "enfant": "Community",
    "exposition": "Arts & Culture",
    "concert": "Music",
    "film": "Arts & Culture",
    "spectacle": "Arts & Culture",
}


def _infer_category(type_text: str, title: str) -> str:
    combined = (type_text + " " + title).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_fondationlv_events() -> List[Dict]:
    """Scrape events from Musée de l'Orangerie (French agenda page)."""
    events = []
    seen_urls = set()

    try:
        resp = requests.get(ORANGERIE_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        cards = soup.select("article[class*='node']")
        logger.info(f"Orangerie: found {len(cards)} article cards")

        for card in cards[:40]:
            try:
                # Title
                title_el = (
                    card.select_one("span[class*='field--name-title']")
                    or card.find(["h4", "h3", "h2"])
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                # Link
                link = card.select_one("h4 a, h3 a, .image-container a")
                url = ""
                if link:
                    href = link.get("href", "")
                    url = href if href.startswith("http") else ORANGERIE_BASE + href
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                # Date (often not shown individually — extract from hours if available)
                date_str = ""
                hours_el = card.select_one(".hours, .event-informations")
                time_str = ""
                if hours_el:
                    raw = hours_el.get_text(strip=True)
                    # "à 11h00" → time only
                    t_m = re.search(r"(\d{1,2})h(\d{2})?", raw, re.I)
                    if t_m:
                        h = int(t_m.group(1))
                        mins = t_m.group(2) or "00"
                        time_str = f"{h:02d}:{mins}"

                if not date_str:
                    continue

                # Category from event-type
                type_el = card.select_one(".field__item, .event-type")
                type_text = type_el.get_text(strip=True) if type_el else ""

                # Image
                img = card.find("img")
                image_url = ""
                if img:
                    src = img.get("src") or img.get("data-src") or ""
                    image_url = src if src.startswith("http") else (ORANGERIE_BASE + src if src else "")

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "end_time": "",
                    "location": LOCATION,
                    "location_name": "Musée de l'Orangerie",
                    "location_address": "Jardin des Tuileries, 75001 Paris, France",
                    "neighborhood": "1st Arrondissement",
                    "description": type_text[:400],
                    "url": url,
                    "category": _infer_category(type_text, title),
                    "source": "Musée de l'Orangerie",
                    "borough": ARRONDISSEMENT,
                    "image_url": image_url,
                    "price": "See website",
                    "is_free": False,
                    "is_family_friendly": any(w in (title).lower() for w in ["famille","family","enfant","kids","jeune"]),
                    "is_outdoor": False,
                    "city": "Paris",
                })
            except Exception as e:
                logger.debug(f"Orangerie: error parsing card: {e}")

    except Exception as e:
        logger.error(f"Orangerie scraper failed: {e}")

    logger.info(f"Orangerie: scraped {len(events)} events")
    return events
