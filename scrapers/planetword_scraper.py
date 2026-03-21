"""
Planet Word Museum — Washington, DC (Downtown)
Events: https://planetwordmuseum.org/calendar/

Two-phase approach:
  1. WordPress REST API (/wp-json/wp/v2/event) returns event post list.
     The API's `after` filter uses the post publication date, not the actual
     event date (stored in _acme_startTime meta, not exposed via REST).
     We cast a 90-day net from 60 days ago so recently-published posts with
     future event dates are included.

  2. Each event's permalink is fetched individually to scrape:
       <h4 class="event-time">Sunday, March 29, 2026 | 4:00 p.m. - 6:00 p.m.</h4>
       <h4 class="event-meta">
         <span class="price-range">$0.00</span> |
         <span class="event-location">Friedman Family Auditorium</span>
       </h4>
       <div class="aucoyote-module hero" style="background-image:url('...')">
       <a class="btn mb-3 checkout" href="https://planetwordmuseum.org/checkout/event/...">

  3. Events whose parsed date is in the past are dropped.
"""

import html
import logging
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

PLANETWORD_BASE     = "https://planetwordmuseum.org"
PLANETWORD_API      = "https://planetwordmuseum.org/wp-json/wp/v2/event"
PLANETWORD_CALENDAR = "https://planetwordmuseum.org/calendar/"

LOCATION_FULL    = "Planet Word Museum, 925 13th St NW, Washington, DC 20005"
LOCATION_NAME    = "Planet Word Museum"
NEIGHBORHOOD     = "Downtown"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_MAP = {
    "series":      "Arts & Culture",
    "talk":        "Arts & Culture",
    "lecture":     "Arts & Culture",
    "discussion":  "Arts & Culture",
    "poetry":      "Arts & Culture",
    "reading":     "Arts & Culture",
    "book":        "Arts & Culture",
    "film":        "Arts & Culture",
    "music":       "Music",
    "concert":     "Music",
    "hip-hop":     "Music",
    "workshop":    "Community",
    "family":      "Community",
    "storytime":   "Community",
    "kids":        "Community",
    "trivia":      "Community",
    "scrabble":    "Community",
    "wordplay":    "Community",
    "calligraphy": "Community",
    "festival":    "Festivals",
    "sensory":     "Community",
    "discovery":   "Community",
    "science":     "Community",
    "education":   "Community",
    "teacher":     "Community",
    "practitioner": "Community",
}


# ── Date / time helpers ───────────────────────────────────────────────────────

def _parse_event_time(text: str) -> Tuple[str, str, str]:
    """
    Parse 'Sunday, March 29, 2026 | 4:00 p.m. - 6:00 p.m.'
    Returns (date_str 'YYYY-MM-DD', start_time 'HH:MM', end_time 'HH:MM').
    Returns ('', '', '') if past or unparseable.
    """
    if not text:
        return "", "", ""

    # Extract date: "March 29, 2026"
    date_m = re.search(
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
        text, re.I,
    )
    if not date_m:
        return "", "", ""
    try:
        dt_date = datetime.strptime(
            f"{date_m.group(2)} {date_m.group(1)} {date_m.group(3)}", "%d %B %Y"
        ).date()
        if dt_date < date.today():
            return "", "", ""
        date_str = dt_date.strftime("%Y-%m-%d")
    except ValueError:
        return "", "", ""

    # Extract time part after the "|" separator
    time_part = text[date_m.end():]

    def _to_24h(h: int, m: int, meridiem: str) -> str:
        mer = meridiem.lower().replace(".", "")
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

    # "4:00 p.m. - 6:00 p.m."  or  "5:00 p.m. - 7:00 p.m."
    range_m = re.search(
        r"(\d{1,2}(?::\d{2})?)\s*(a\.?m\.?|p\.?m\.?)\s*[-–]\s*"
        r"(\d{1,2}(?::\d{2})?)\s*(a\.?m\.?|p\.?m\.?)",
        time_part, re.I,
    )
    if range_m:
        h1, m1 = _parse_hm(range_m.group(1))
        h2, m2 = _parse_hm(range_m.group(3))
        mer1 = re.sub(r"\.", "", range_m.group(2))
        mer2 = re.sub(r"\.", "", range_m.group(4))
        return date_str, _to_24h(h1, m1, mer1), _to_24h(h2, m2, mer2)

    # Single time: "5:00 p.m."
    single_m = re.search(r"(\d{1,2}(?::\d{2})?)\s*(a\.?m\.?|p\.?m\.?)", time_part, re.I)
    if single_m:
        h, m = _parse_hm(single_m.group(1))
        mer = re.sub(r"\.", "", single_m.group(2))
        return date_str, _to_24h(h, m, mer), ""

    return date_str, "", ""


def _parse_price(h4_meta) -> Tuple[str, bool]:
    """
    Parse <h4 class="event-meta"> → (price_str, is_free).
    e.g. '$0.00' → ('Free', True), '$15.00' → ('$15.00', False).
    """
    if not h4_meta:
        return "See website", False
    price_span = h4_meta.find("span", class_="price-range")
    if not price_span:
        raw = h4_meta.get_text(" ", strip=True)
        is_free = "$0" in raw or "free" in raw.lower()
        return "Free" if is_free else "See website", is_free
    raw_price = price_span.get_text(strip=True)
    try:
        amount = float(raw_price.replace("$", "").replace(",", "").strip())
        is_free = amount == 0.0
        return "Free" if is_free else raw_price, is_free
    except ValueError:
        is_free = "free" in raw_price.lower() or raw_price in ("$0", "$0.00")
        return "Free" if is_free else raw_price, is_free


def _extract_image(soup) -> str:
    """Extract background-image URL from the hero div."""
    hero = soup.find("div", class_=lambda c: c and "hero" in c.split())
    if hero:
        style = hero.get("style", "")
        m = re.search(r"background-image\s*:\s*url\(['\"]?(https?://[^'\")\s]+)", style)
        if m:
            return m.group(1)
    # Fallback: og:image meta tag
    og = soup.find("meta", property="og:image")
    if og and og.get("content", "").startswith("http"):
        return og["content"]
    return ""


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_planetword_events() -> List[Dict]:
    """Scrape upcoming events from Planet Word Museum."""
    events: List[Dict] = []
    seen_urls: set = set()

    # Cast a 90-day net: posts published from 60 days ago through to today
    after_date = (date.today() - timedelta(days=60)).isoformat() + "T00:00:00"

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        # ── Step 1: get event list from REST API ──────────────────────────────
        resp = session.get(
            PLANETWORD_API,
            params={
                "per_page": 100,
                "after": after_date,
                "_fields": "id,title,link",
                "orderby": "date",
                "order": "asc",
            },
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning(f"Planet Word: REST API returned HTTP {resp.status_code}")
            return events

        raw_list = resp.json()
        if not isinstance(raw_list, list):
            logger.warning("Planet Word: unexpected API response format")
            return events

        logger.info(f"Planet Word: {len(raw_list)} candidate posts from REST API")

        # ── Step 2: scrape each event page ────────────────────────────────────
        for item in raw_list:
            try:
                title = (item.get("title") or {}).get("rendered", "").strip()
                title = html.unescape(re.sub(r"<[^>]+>", "", title))
                if not title or len(title) < 3:
                    continue

                url = item.get("link", "")
                if not url or url in seen_urls:
                    continue

                # Polite delay between page fetches
                time.sleep(0.3)

                page_resp = session.get(url, timeout=20)
                if page_resp.status_code != 200:
                    logger.debug(f"Planet Word: {url} returned HTTP {page_resp.status_code}")
                    continue

                soup = BeautifulSoup(page_resp.text, "html.parser")

                # ── Date / time ───────────────────────────────────────────────
                time_h4 = soup.find("h4", class_="event-time")
                raw_time = time_h4.get_text(" ", strip=True) if time_h4 else ""
                date_str, start_time, end_time = _parse_event_time(raw_time)
                if not date_str:
                    continue  # past or unparseable

                seen_urls.add(url)

                # ── Price ─────────────────────────────────────────────────────
                meta_h4 = soup.find("h4", class_="event-meta")
                price, is_free = _parse_price(meta_h4)

                # ── Description (first paragraph of content) ──────────────────
                content_div = soup.find("div", class_=lambda c: c and "entry-content" in c.split())
                if not content_div:
                    content_div = soup.find("article")
                description = ""
                if content_div:
                    first_p = content_div.find("p")
                    if first_p:
                        description = re.sub(r"<[^>]+>", "", str(first_p)).strip()[:400]

                # ── Image ──────────────────────────────────────────────────────
                image_url = _extract_image(soup)

                # ── Family friendly ───────────────────────────────────────────
                family_keywords = ["family", "kids", "children", "storytime", "youth", "sensory"]
                is_family = any(w in title.lower() for w in family_keywords)

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": start_time,
                    "end_time": end_time,
                    "location": LOCATION_FULL,
                    "location_name": LOCATION_NAME,
                    "location_address": "925 13th St NW, Washington, DC 20005",
                    "neighborhood": NEIGHBORHOOD,
                    "description": description,
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "Planet Word Museum",
                    "borough": NEIGHBORHOOD,
                    "image_url": image_url,
                    "price": price,
                    "is_free": is_free,
                    "is_family_friendly": is_family,
                    "is_outdoor": False,
                    "city": "Washington DC",
                })

            except Exception as e:
                logger.debug(f"Planet Word: error parsing event: {e}")

    except Exception as e:
        logger.error(f"Planet Word scraper failed: {e}")

    logger.info(f"Planet Word: scraped {len(events)} events")
    return events
