"""
Smithsonian American Art Museum (SAAM) — Washington, DC (Downtown)
Events: https://americanart.si.edu/events

The site uses htmx + Alpine.js for dynamic rendering.
Events are loaded via a POST to /services/wire/search/results with
content_type=event in the request body. A Drupal session token obtained
from /session/token is required as the X-CSRF-Token header.

HTML structure of each result card:
  <div class="azalea-event-teaser ...">
    <div ...>  ← date display (day-of-week, day number, month abbreviation)
    <div ...>  ← thumbnail image
    <div col-span-4 ...>
      <header>
        <a class="azalea-heading-level-4 text-black" href="/events/slug">Title</a>
        <div class="azalea-heading-level-6 mt-4 ...">
          Wednesday, March 18, 2026, 6:30 – 7:30pm EDT
        </div>
      </header>
      <div>
        <a class="text-black hover:no-underline" href="/visit/renwick ">Renwick Gallery</a>
      </div>
    </div>
    <div col-span-2 ...>
      <div class="azalea-text-sm text-tertiary-500">Free | Meet in G Street Lobby</div>
    </div>
  </div>
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

SAAM_BASE = "https://americanart.si.edu"
SAAM_EVENTS_URL = "https://americanart.si.edu/search/events"
SAAM_TOKEN_URL = "https://americanart.si.edu/session/token"
SAAM_SEARCH_URL = "https://americanart.si.edu/services/wire/search/results"

LOCATION_SAAM = "Smithsonian American Art Museum, 8th and F Streets NW, Washington, DC 20004"
LOCATION_RENWICK = "Renwick Gallery, 1661 Pennsylvania Ave NW, Washington, DC 20006"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_MAP = {
    "gallery talk": "Heritage & History",
    "tour": "Heritage & History",
    "lecture": "Heritage & History",
    "discussion": "Heritage & History",
    "symposia": "Heritage & History",
    "symposium": "Heritage & History",
    "film": "Arts & Culture",
    "performance": "Arts & Culture",
    "exhibition": "Arts & Culture",
    "concert": "Music",
    "classical": "Music",
    "jazz": "Music",
    "workshop": "Community",
    "family": "Community",
    "kids": "Community",
    "children": "Community",
    "yoga": "Community",
    "after five": "Arts & Culture",
    "celebration": "Festivals",
    "festival": "Festivals",
    "webcast": "Arts & Culture",
    "online": "Arts & Culture",
    "culinary": "Community",
    "demonstration": "Heritage & History",
    "education": "Community",
}


# ── Date / time helpers ───────────────────────────────────────────────────────

def _to_24h(hour: int, minute: int, meridiem: str) -> str:
    """Convert hour/minute/meridiem to HH:MM."""
    h = hour
    mer = meridiem.lower()
    if mer == "pm" and h != 12:
        h += 12
    elif mer == "am" and h == 12:
        h = 0
    return f"{h:02d}:{minute:02d}"


def _parse_time_part(raw: str) -> Tuple[int, int]:
    """Parse '6:30' or '6' or '12:45' → (hour, minute)."""
    m = re.match(r"(\d{1,2})(?::(\d{2}))?", raw.strip())
    if m:
        return int(m.group(1)), int(m.group(2) or 0)
    return 0, 0


def _parse_datetime(text: str) -> Tuple[str, str, str]:
    """
    Parse 'Wednesday, March 18, 2026, 6:30 – 7:30pm EDT'
    → (date_str '2026-03-18', start_time '18:30', end_time '19:30').
    Returns ('', '', '') for past dates or unparseable input.
    """
    if not text:
        return "", "", ""

    # Extract date: "March 18, 2026"
    date_m = re.search(
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{1,2}),\s+(\d{4})",
        text, re.I
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

    # Case 1: both endpoints have explicit meridiem — "11:30am – 3pm"
    both_m = re.search(
        r"(\d{1,2}(?::\d{2})?)\s*(am|pm)\s*[–\-]\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)",
        time_part, re.I
    )
    if both_m:
        h1, m1 = _parse_time_part(both_m.group(1))
        h2, m2 = _parse_time_part(both_m.group(3))
        return (
            date_str,
            _to_24h(h1, m1, both_m.group(2)),
            _to_24h(h2, m2, both_m.group(4)),
        )

    # Case 2: range with meridiem only at end — "6:30 – 7:30pm" / "1 – 3pm"
    range_m = re.search(
        r"(\d{1,2}(?::\d{2})?)\s*[–\-]\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)",
        time_part, re.I
    )
    if range_m:
        h1, m1 = _parse_time_part(range_m.group(1))
        h2, m2 = _parse_time_part(range_m.group(2))
        meridiem = range_m.group(3)
        return (
            date_str,
            _to_24h(h1, m1, meridiem),
            _to_24h(h2, m2, meridiem),
        )

    # Case 3: single time — "9am EDT" / "5:30pm EDT"
    single_m = re.search(r"(\d{1,2}(?::\d{2})?)\s*(am|pm)", time_part, re.I)
    if single_m:
        h, m = _parse_time_part(single_m.group(1))
        return date_str, _to_24h(h, m, single_m.group(2)), ""

    return date_str, "", ""


def _infer_category(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def _infer_location(teaser) -> Tuple[str, str, str]:
    """
    Return (location_full, location_name, neighborhood).
    Checks for a Renwick link, otherwise defaults to main SAAM.
    """
    for a in teaser.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if "renwick" in href.lower() or "renwick" in text.lower():
            return LOCATION_RENWICK, "Renwick Gallery", "Downtown"
    return LOCATION_SAAM, "Smithsonian American Art Museum", "Downtown"


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_saam_events() -> List[Dict]:
    """Scrape upcoming events from the Smithsonian American Art Museum."""
    events = []
    seen_urls: set = set()

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        # Warm up the session and get cookies
        session.get(SAAM_EVENTS_URL, timeout=20)

        # Obtain Drupal CSRF token (required for the htmx POST)
        token_resp = session.get(SAAM_TOKEN_URL, timeout=10)
        csrf_token = token_resp.text.strip() if token_resp.status_code == 200 else ""

        post_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "HX-Request": "true",
            "HX-Current-URL": SAAM_EVENTS_URL,
            "HX-Target": "results",
            "Referer": SAAM_EVENTS_URL,
        }
        if csrf_token:
            post_headers["X-CSRF-Token"] = csrf_token

        resp = session.post(
            SAAM_SEARCH_URL,
            data="content_type=event",
            headers=post_headers,
            timeout=25,
        )
        if resp.status_code != 200:
            logger.warning(f"SAAM: search POST returned HTTP {resp.status_code}")
            return events

        soup = BeautifulSoup(resp.text, "html.parser")
        teasers = soup.select(".azalea-event-teaser")
        logger.info(f"SAAM: found {len(teasers)} event teasers")

        for teaser in teasers:
            try:
                # ── Title + URL ──────────────────────────────────────────
                title_el = teaser.select_one("a.azalea-heading-level-4, header a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = title_el.get("href", "")
                url = href if href.startswith("http") else SAAM_BASE + href
                if url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                # ── Date + time ──────────────────────────────────────────
                # "Wednesday, March 18, 2026, 6:30 – 7:30pm EDT"
                dt_el = teaser.select_one(
                    ".azalea-heading-level-6, [class*='heading-level-6']"
                )
                raw_dt = dt_el.get_text(strip=True) if dt_el else ""
                date_str, start_time, end_time = _parse_datetime(raw_dt)
                if not date_str:
                    continue

                # ── Location ─────────────────────────────────────────────
                location, location_name, neighborhood = _infer_location(teaser)

                # ── Description / price ──────────────────────────────────
                price_el = teaser.select_one(
                    ".azalea-text-sm.text-tertiary-500, [class*='text-tertiary-500']"
                )
                price_text = price_el.get_text(strip=True) if price_el else ""
                is_free = bool(re.search(r"\bfree\b", price_text, re.I))
                price = "Free" if is_free else ("See website" if not price_text else price_text.split("|")[0].strip())

                # Description: short blurb from price line or empty
                description = price_text[:400] if price_text else ""

                # ── Image ────────────────────────────────────────────────
                img = teaser.find("img")
                image_url = ""
                if img:
                    src = img.get("src", "") or img.get("data-src", "") or ""
                    if src.startswith("//"):
                        src = "https:" + src
                    image_url = src if src.startswith("http") else ""

                # ── Family friendly ──────────────────────────────────────
                family_keywords = ["family", "kids", "children", "families", "youth"]
                is_family = any(w in title.lower() for w in family_keywords)

                events.append({
                    "title": title,
                    "date": date_str,
                    "time": start_time,
                    "end_time": end_time,
                    "location": location,
                    "location_name": location_name,
                    "location_address": location.split(", ", 1)[1] if ", " in location else location,
                    "neighborhood": neighborhood,
                    "description": description,
                    "url": url,
                    "category": _infer_category(title, description),
                    "source": "Smithsonian American Art Museum",
                    "borough": neighborhood,
                    "image_url": image_url,
                    "price": price,
                    "is_free": is_free,
                    "is_family_friendly": is_family,
                    "is_outdoor": False,
                    "city": "Washington DC",
                })

            except Exception as e:
                logger.debug(f"SAAM: error parsing teaser: {e}")

    except Exception as e:
        logger.error(f"SAAM scraper failed: {e}")

    logger.info(f"SAAM: scraped {len(events)} events")
    return events
