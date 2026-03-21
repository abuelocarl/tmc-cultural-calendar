"""
Musée du Louvre — Paris, France
Events:  https://www.louvre.fr/expositions-et-evenements/evenements-activites
Expos:   https://www.louvre.fr/expositions-et-evenements/expositions

Real HTML structure:
<div class="Events_Event flux">
  <div class="Events_Event_time"><h3 class="...">9 mars – 1 juillet 2026</h3></div>
  <div class="Events_Event_imageratio"><picture><img ...></picture></div>
  <h4 class="Events_Event_title">
    <a href="/expositions-et-evenements/...">C'est le bouquet !</a>
  </h4>
  <p class="EventTagsList Events_Event_tags">AteliersDès 6 ansFamilles</p>
  <div class="Wysiwyg Events_Event_description ...">Description text...</div>
  <div class="Events_Event_button">Découvrir</div>
</div>
"""

import logging
import re
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

LOUVRE_URLS = [
    "https://www.louvre.fr/expositions-et-evenements/evenements-activites",
    "https://www.louvre.fr/expositions-et-evenements/expositions",
]
LOUVRE_BASE = "https://www.louvre.fr"
LOCATION = "Musée du Louvre, Rue de Rivoli, 75001 Paris, France"
ARRONDISSEMENT = "1st Arrondissement"

MONTHS_FR = {
    "janv": 1, "jan": 1, "janvier": 1,
    "fév": 2, "févr": 2, "février": 2,
    "mars": 3, "mar": 3,
    "avr": 4, "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7, "juillet": 7,
    "août": 8, "aout": 8,
    "sept": 9, "sep": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "déc": 12, "dec": 12, "décembre": 12,
}

CATEGORY_MAP = {
    "concert": "Music",
    "musique": "Music",
    "atelier": "Community",
    "famille": "Community",
    "enfant": "Community",
    "conférence": "Heritage & History",
    "visite": "Heritage & History",
    "nocturne": "Heritage & History",
    "exposition": "Arts & Culture",
    "film": "Arts & Culture",
    "spectacle": "Arts & Culture",
    "performance": "Arts & Culture",
}


def _parse_fr_date(text: str) -> str:
    """Parse French date like '9 mars – 1 juillet 2026' → start date."""
    if not text:
        return ""
    # Extract the first date occurrence
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
        # If no year in first match, look for year anywhere
        year_m = re.search(r"\b(20\d{2})\b", text)
        year = int(year_m.group(1)) if year_m else datetime.now().year
        if month_num:
            try:
                dt = datetime(year, month_num, day)
                if dt.date() < date.today() or dt.date() > date.today() + timedelta(days=183):
                    return ""
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
    return ""


def _infer_category(title: str, desc: str, tags: str) -> str:
    combined = (title + " " + desc + " " + tags).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_louvre_events() -> List[Dict]:
    """Scrape events from the Musée du Louvre (French pages)."""
    events = []
    seen_urls = set()

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )

        for page_url in LOUVRE_URLS:
            try:
                resp = scraper.get(page_url, timeout=20)
                if resp.status_code != 200:
                    logger.warning(f"Louvre: {page_url} → HTTP {resp.status_code}")
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                # Cards: div with both Events_Event and flux in class list
                cards = [
                    c for c in soup.select("[class*='Events_Event']")
                    if any("flux" in cls for cls in c.get("class", []))
                ]
                logger.info(f"Louvre: {page_url} → {len(cards)} cards")

                for card in cards[:30]:
                    try:
                        # Title is in h4.Events_Event_title
                        title_el = card.select_one("h4[class*='Events_Event_title'], h3[class*='Events_Event_title']")
                        if not title_el:
                            title_el = card.find(["h3", "h4"])
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 3:
                            continue

                        # Link (inside the h4)
                        link = title_el.find("a", href=True) or card.find("a", href=True)
                        url = ""
                        if link:
                            href = link["href"]
                            url = href if href.startswith("http") else LOUVRE_BASE + href
                        if url in seen_urls:
                            continue
                        if url:
                            seen_urls.add(url)

                        # Date: Events_Event_time div
                        date_el = card.select_one("[class*='Events_Event_time']")
                        date_str = _parse_fr_date(date_el.get_text(strip=True)) if date_el else ""
                        if not date_str:
                            continue

                        # Tags / category
                        tags_el = card.select_one("[class*='EventTagsList'], [class*='Event_tags']")
                        tags_text = tags_el.get_text(strip=True) if tags_el else ""

                        # Description
                        desc_el = card.select_one("[class*='Events_Event_description'], [class*='Wysiwyg']")
                        description = desc_el.get_text(strip=True) if desc_el else ""

                        # Image: from <picture> inside the card
                        img = card.find("img")
                        image_url = ""
                        if img:
                            src = img.get("src") or img.get("data-src") or ""
                            image_url = src if src.startswith("http") else (LOUVRE_BASE + src if src else "")

                        events.append({
                    "title": title,
                    "date": date_str,
                    "time": "",
                    "end_time": "",
                    "location": LOCATION,
                    "location_name": "Musée du Louvre",
                    "location_address": "Rue de Rivoli, 75001 Paris, France",
                    "neighborhood": "1st Arrondissement",
                    "description": description[:400],
                    "url": url,
                    "category": _infer_category(title, description, tags_text),
                    "source": "Musée du Louvre",
                    "borough": ARRONDISSEMENT,
                    "image_url": image_url,
                    "price": "See website",
                    "is_free": False,
                    "is_family_friendly": any(w in (title).lower() for w in ["famille","family","enfant","kids","jeune"]),
                    "is_outdoor": False,
                    "city": "Paris",
                })
                    except Exception as e:
                        logger.debug(f"Louvre: error parsing card: {e}")

            except Exception as e:
                logger.warning(f"Louvre: failed to scrape {page_url}: {e}")

    except Exception as e:
        logger.error(f"Louvre scraper failed: {e}")

    logger.info(f"Louvre: scraped {len(events)} events")
    return events
