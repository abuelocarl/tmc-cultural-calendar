"""
The Phillips Collection — Washington, DC (Dupont Circle)
Events: https://www.phillipscollection.org/events

Drupal 10 site — fully server-rendered HTML, no public REST API.

HTML structure per event card:
  <div class="card flex-layout__item" id="card-NNNNN">
    <figure class="card__img">
      <a href="/event/YYYY-MM-DD-slug">
        <span class="card__banner">Member Preview Reception</span>
        <figure><img src="/sites/default/files/.../image.jpg" ...></figure>
      </a>
    </figure>
    <time class="card__date" datetime="March 20, 2026, 5:30-7:30 pm">
      March 20, 2026, 5:30-7:30 pm
    </time>
    <h3 class="card__title">
      <a class="card__title-link" href="/event/YYYY-MM-DD-slug">
        <p>Event Title</p>
      </a>
    </h3>
    <hr/>
    <p>Registration Open / Free / Members</p>
  </div>

Pagination: ?page=1, ?page=2, … until no new events appear.
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

PHILLIPS_BASE   = "https://www.phillipscollection.org"
PHILLIPS_EVENTS = "https://www.phillipscollection.org/events"

LOCATION_FULL    = "The Phillips Collection, 1600 21st St NW, Washington, DC 20009"
LOCATION_NAME    = "The Phillips Collection"
NEIGHBORHOOD     = "Dupont Circle"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_MAP = {
    "concert":    "Music",
    "music":      "Music",
    "jazz":       "Music",
    "sunday":     "Music",   # Sunday Concerts
    "performance": "Music",
    "lecture":    "Arts & Culture",
    "talk":       "Arts & Culture",
    "gallery":    "Arts & Culture",
    "exhibition": "Arts & Culture",
    "tour":       "Arts & Culture",
    "opening":    "Arts & Culture",
    "reception":  "Arts & Culture",
    "preview":    "Arts & Culture",
    "film":       "Arts & Culture",
    "screening":  "Arts & Culture",
    "panel":      "Arts & Culture",
    "workshop":   "Community",
    "family":     "Community",
    "kids":       "Community",
    "children":   "Community",
    "youth":      "Community",
    "wellness":   "Community",
    "community":  "Community",
    "living room": "Community",
    "festival":   "Festivals",
}


# ── Date / time helpers ───────────────────────────────────────────────────────

def _parse_date_time(text: str) -> Tuple[str, str, str]:
    """
    Parse strings like:
      "March 20, 2026, 5:30-7:30 pm"
      "March 22, 2026, 4-6 PM"
      "April 8, 2026, 6:30-8:30 pm"
      "April 11, 2026, 10 am-1 pm"
    Returns (date_str 'YYYY-MM-DD', start_time 'HH:MM', end_time 'HH:MM').
    Returns ('', '', '') if past or unparseable.
    """
    if not text:
        return "", "", ""

    text = re.sub(r"\s+", " ", text.strip())

    # Extract date
    date_m = re.search(
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{1,2}),\s+(\d{4})",
        text, re.I,
    )
    if not date_m:
        return "", "", ""

    try:
        dt_date = datetime.strptime(
            f"{date_m.group(2)} {date_m.group(1)} {date_m.group(3)}", "%d %B %Y"
        ).date()
        if dt_date < date.today() or dt_date > date.today() + timedelta(days=183):
            return "", "", ""
        date_str = dt_date.strftime("%Y-%m-%d")
    except ValueError:
        return "", "", ""

    time_part = text[date_m.end():]

    def _to_24h(h: int, m: int, meridiem: str) -> str:
        mer = re.sub(r"\.", "", meridiem).lower().strip()
        if mer == "pm" and h != 12:
            h += 12
        elif mer == "am" and h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"

    def _parse_hm(s: str) -> Tuple[int, int]:
        mm = re.match(r"(\d{1,2})(?::(\d{2}))?", s.strip())
        if mm:
            return int(mm.group(1)), int(mm.group(2) or 0)
        return 0, 0

    # Patterns like "4-6 PM", "5:30-7:30 pm", "10 am-1 pm", "6:30-8:30 pm"
    range_m = re.search(
        r"(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*[-–]\s*"
        r"(\d{1,2}(?::\d{2})?)\s*(am|pm)",
        time_part, re.I,
    )
    if range_m:
        h1, m1 = _parse_hm(range_m.group(1))
        h2, m2 = _parse_hm(range_m.group(3))
        mer2 = range_m.group(4)
        mer1 = range_m.group(2) or mer2  # inherit end meridiem if start lacks one
        return date_str, _to_24h(h1, m1, mer1), _to_24h(h2, m2, mer2)

    # Single time: "6:30 pm"
    single_m = re.search(r"(\d{1,2}(?::\d{2})?)\s*(am|pm)", time_part, re.I)
    if single_m:
        h, m = _parse_hm(single_m.group(1))
        return date_str, _to_24h(h, m, single_m.group(2)), ""

    return date_str, "", ""


def _parse_price(text: str) -> Tuple[str, bool]:
    """Infer price/free from registration paragraph text."""
    lower = text.lower()
    if "free" in lower:
        return "Free", True
    if "$" in text:
        m = re.search(r"\$[\d,.]+", text)
        if m:
            return m.group(0), False
    return "See website", False


def _infer_category(banner: str, title: str) -> str:
    combined = (banner + " " + title).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_phillips_events() -> List[Dict]:
    """Scrape upcoming events from The Phillips Collection."""
    events: List[Dict] = []
    seen_urls: set = set()

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        page_num = 0
        while True:
            url = PHILLIPS_EVENTS if page_num == 0 else f"{PHILLIPS_EVENTS}?page={page_num}"
            try:
                resp = session.get(url, timeout=20)
                if resp.status_code != 200:
                    logger.warning(f"Phillips: HTTP {resp.status_code} on page {page_num}")
                    break
            except Exception as e:
                logger.warning(f"Phillips: request failed on page {page_num}: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")

            # Cards are div.card elements with an /event/ link
            cards = soup.find_all("div", class_="card")

            if not cards:
                logger.debug(f"Phillips: no cards on page {page_num}, stopping")
                break

            new_on_page = 0
            for card in cards:
                try:
                    # ── URL ────────────────────────────────────────────────
                    link_tag = card.find("a", href=re.compile(r"/event/"))
                    if not link_tag:
                        continue
                    href = link_tag["href"]
                    event_url = PHILLIPS_BASE + href if href.startswith("/") else href
                    if event_url in seen_urls:
                        continue

                    # ── Date / time from <time class="card__date"> ─────────
                    time_tag = card.find("time", class_="card__date")
                    raw_time = time_tag.get_text(" ", strip=True) if time_tag else ""
                    date_str, start_time, end_time = _parse_date_time(raw_time)
                    if not date_str:
                        continue  # past or unparseable

                    seen_urls.add(event_url)
                    new_on_page += 1

                    # ── Title from <h3 class="card__title"> ───────────────
                    h3 = card.find("h3", class_="card__title")
                    title = h3.get_text(" ", strip=True) if h3 else ""
                    if not title:
                        title = link_tag.get_text(" ", strip=True)
                    if not title or len(title) < 3:
                        continue

                    # ── Event type / category ──────────────────────────────
                    banner_tag = card.find("span", class_="card__banner")
                    banner = banner_tag.get_text(strip=True) if banner_tag else ""

                    # ── Price from <p> after <hr> ──────────────────────────
                    hr = card.find("hr")
                    reg_text = ""
                    if hr and hr.find_next_sibling("p"):
                        reg_text = hr.find_next_sibling("p").get_text(" ", strip=True)
                    price, is_free = _parse_price(reg_text)

                    # ── Image ─────────────────────────────────────────────
                    img_tag = card.find("img")
                    image_url = ""
                    if img_tag:
                        src = img_tag.get("src") or img_tag.get("data-src", "")
                        if src.startswith("/"):
                            src = PHILLIPS_BASE + src
                        image_url = src if src.startswith("http") else ""

                    # ── Family friendly ────────────────────────────────────
                    family_keywords = ["family", "kids", "children", "youth"]
                    combined_lower = (title + " " + banner + " " + reg_text).lower()
                    is_family = any(w in combined_lower for w in family_keywords)

                    events.append({
                        "title": title,
                        "date": date_str,
                        "time": start_time,
                        "end_time": end_time,
                        "location": LOCATION_FULL,
                        "location_name": LOCATION_NAME,
                        "location_address": "1600 21st St NW, Washington, DC 20009",
                        "neighborhood": NEIGHBORHOOD,
                        "description": banner,
                        "url": event_url,
                        "category": _infer_category(banner, title),
                        "source": "The Phillips Collection",
                        "borough": NEIGHBORHOOD,
                        "image_url": image_url,
                        "price": price,
                        "is_free": is_free,
                        "is_family_friendly": is_family,
                        "is_outdoor": False,
                        "city": "Washington DC",
                    })

                except Exception as e:
                    logger.debug(f"Phillips: error parsing card: {e}")

            logger.info(f"Phillips: page {page_num} → {new_on_page} new events")

            if new_on_page == 0:
                break

            # Follow pagination only if there's a next page link
            next_link = soup.find("a", href=re.compile(rf"[?&]page={page_num + 1}"))
            if not next_link:
                break
            page_num += 1

    except Exception as e:
        logger.error(f"Phillips scraper failed: {e}")

    logger.info(f"Phillips Collection: scraped {len(events)} events")
    return events
