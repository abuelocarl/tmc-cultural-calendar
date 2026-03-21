"""
National Air and Space Museum (NASM) — Washington DC / Chantilly VA
Events: https://airandspace.si.edu/whats-on/events

Actual HTML structure (Drupal CMS, server-rendered, 10 cards/page):
<article class="c-image-teaser">
  <div class="l-media">
    <div class="l-media__object"><img src="/sites/default/files/styles/..." /></div>
    <div class="l-media__content">
      <p class="text-fluid-sm font-semibold font-accent">Story Time</p>
      <h4 class="c-image-teaser__title"><a href="/whats-on/events/...">Title</a></h4>
      <ul class="c-list">
        <li>📍 National Air and Space Museum in Washington, DC</li>
        <li><time datetime="2026-03-21T10:30:00-04:00">March 21, 2026 | 10:30</time>
            - <time datetime="2026-03-21T11:00:00-04:00">11am</time></li>
      </ul>
    </div>
  </div>
</article>

Pagination: ?page=1, ?page=2, ... — follow a.c-pager__link--next until absent.
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

NASM_BASE = "https://airandspace.si.edu"
NASM_URL  = f"{NASM_BASE}/whats-on/events"

LOCATION_MALL  = "National Air and Space Museum, Independence Ave SW & 6th St SW, Washington, DC 20560"
LOCATION_UDVAR = "Steven F. Udvar-Hazy Center, 14390 Air and Space Museum Pkwy, Chantilly, VA 20151"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_MAP = {
    "film":          "Arts & Culture",
    "lecture":       "Heritage & History",
    "talk":          "Heritage & History",
    "discussion":    "Heritage & History",
    "tour":          "Heritage & History",
    "exhibition":    "Arts & Culture",
    "concert":       "Music",
    "music":         "Music",
    "performance":   "Arts & Culture",
    "workshop":      "Community",
    "family":        "Community",
    "kids":          "Community",
    "children":      "Community",
    "story time":    "Community",
    "festival":      "Festivals",
    "celebration":   "Festivals",
    "demonstration": "Heritage & History",
    "history":       "Heritage & History",
    "symposium":     "Heritage & History",
    "conference":    "Heritage & History",
    "astronomy":     "Heritage & History",
    "space":         "Heritage & History",
    "aviation":      "Heritage & History",
    "planetarium":   "Heritage & History",
    "science":       "Heritage & History",
    "imax":          "Arts & Culture",
    "screening":     "Arts & Culture",
}


def _infer_category(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Heritage & History"


def _parse_datetime_attr(dt_attr: str):
    """
    Parse ISO 8601 datetime attribute like '2026-03-21T10:30:00-04:00'.
    Returns (date_iso, time_str) or ("", "") if past/invalid.
    """
    if not dt_attr:
        return "", ""
    try:
        # Strip timezone offset before fromisoformat (Python < 3.11 compat)
        dt_clean = re.sub(r"[+-]\d{2}:\d{2}$|Z$", "", dt_attr)
        dt = datetime.fromisoformat(dt_clean)
        if dt.date() < date.today() or dt.date() > date.today() + timedelta(days=183):
            return "", ""
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except Exception:
        return "", ""


def _to_24h(time_raw: str) -> str:
    """Convert '7:00pm', '11am', '12:00pm' → '19:00', '11:00', '12:00'."""
    time_raw = time_raw.strip()
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", time_raw, re.I)
    if not m:
        return ""
    hour     = int(m.group(1))
    minute   = m.group(2) or "00"
    meridiem = m.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def scrape_nasm_events() -> List[Dict]:
    """Scrape events from the National Air and Space Museum calendar."""
    events    = []
    seen_urls = set()
    page      = 0

    while True:
        url = NASM_URL if page == 0 else f"{NASM_URL}?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"NASM: failed to fetch page {page}: {e}")
            break

        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article.c-image-teaser")
        logger.info(f"NASM: page {page} — {len(cards)} cards")

        if not cards:
            break

        for card in cards:
            try:
                # ── Title + URL ──────────────────────────────────────────
                title_a = card.select_one(
                    "h4.c-image-teaser__title a, h3.c-image-teaser__title a, "
                    ".c-image-teaser__title a"
                )
                if not title_a:
                    continue
                title = title_a.get_text(strip=True)
                if not title:
                    continue
                href      = title_a.get("href", "")
                event_url = href if href.startswith("http") else NASM_BASE + href
                if event_url in seen_urls:
                    continue
                seen_urls.add(event_url)

                # ── Date + time — prefer <time datetime="..."> ───────────
                time_els     = card.select("time[datetime]")
                date_iso     = ""
                time_str     = ""
                end_time_str = ""

                if time_els:
                    date_iso, time_str   = _parse_datetime_attr(time_els[0].get("datetime", ""))
                    if len(time_els) >= 2:
                        _, end_time_str  = _parse_datetime_attr(time_els[1].get("datetime", ""))
                else:
                    # Recurring / text-only — scan list items for a month name
                    for li in card.select("li"):
                        text = li.get_text(separator=" ", strip=True)
                        date_m = re.search(
                            r"(January|February|March|April|May|June|July|August|"
                            r"September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
                            text, re.I
                        )
                        if date_m:
                            try:
                                raw = date_m.group(0).replace(",", "")
                                dt  = datetime.strptime(raw, "%B %d %Y")
                                if date.today() <= dt.date() <= date.today() + timedelta(days=183):
                                    date_iso = dt.strftime("%Y-%m-%d")
                            except ValueError:
                                pass
                            # Grab a time from the same text
                            time_m = re.search(r"(\d{1,2}(?::\d{2})?\s*[ap]m)", text, re.I)
                            if time_m:
                                time_str = _to_24h(time_m.group(1))
                            break

                # Skip undated / past events
                if not date_iso:
                    continue

                # ── Image ────────────────────────────────────────────────
                img_el    = card.select_one(".l-media__object img, img")
                image_url = ""
                if img_el:
                    src       = img_el.get("src", "")
                    image_url = src if src.startswith("http") else NASM_BASE + src

                # ── Event type label (short description) ─────────────────
                type_el     = card.select_one(
                    "p.font-semibold, p.font-accent, .c-image-teaser__type, "
                    "p.text-fluid-sm"
                )
                description = type_el.get_text(strip=True) if type_el else ""

                # ── Location — first list item ───────────────────────────
                loc_el   = card.select_one("ul.c-list li, .c-list li")
                loc_text = loc_el.get_text(separator=" ", strip=True) if loc_el else ""
                loc_lower = loc_text.lower()

                if "udvar" in loc_lower or "chantilly" in loc_lower:
                    location         = LOCATION_UDVAR
                    location_name    = "Steven F. Udvar-Hazy Center"
                    location_address = "14390 Air and Space Museum Pkwy, Chantilly, VA 20151"
                    borough          = "Chantilly, VA"
                elif "online" in loc_lower:
                    location         = "Online"
                    location_name    = "Online"
                    location_address = ""
                    borough          = "Online"
                else:
                    location         = LOCATION_MALL
                    location_name    = "National Air and Space Museum"
                    location_address = "Independence Ave SW & 6th St SW, Washington, DC 20560"
                    borough          = "National Mall"

                # ── Flags ────────────────────────────────────────────────
                combined_text = (title + " " + description + " " + loc_text).lower()
                is_family  = any(w in combined_text for w in
                                 ["family", "kids", "children", "all ages", "story time"])
                is_outdoor = any(w in combined_text for w in
                                 ["outdoor", "garden", "plaza", "open air", "rooftop"])

                events.append({
                    "title":            title,
                    "date":             date_iso,
                    "end_date":         "",
                    "time":             time_str,
                    "end_time":         end_time_str,
                    "location":         location,
                    "location_name":    location_name,
                    "location_address": location_address,
                    "neighborhood":     "National Mall",
                    "description":      description[:400],
                    "url":              event_url,
                    "category":         _infer_category(title, description),
                    "source":           "National Air and Space Museum",
                    "borough":          borough,
                    "image_url":        image_url,
                    "price":            "Free",
                    "is_free":          True,
                    "is_family_friendly": is_family,
                    "is_outdoor":       is_outdoor,
                    "city":             "Washington DC",
                })

            except Exception as e:
                logger.debug(f"NASM: error parsing card: {e}")

        # Follow pagination — cap at 80 events (~8 pages)
        next_link = soup.select_one("a.c-pager__link--next")
        if not next_link or len(events) >= 80:
            break
        page += 1

    logger.info(f"NASM: scraped {len(events)} events")
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_nasm_events()
    print(f"\nFound {len(results)} NASM events:")
    for ev in results:
        end = f" → {ev['end_time']}" if ev.get("end_time") else ""
        print(f"  [{ev['date']}] {ev['title']}")
        print(f"           {ev['time']}{end} | {ev['category']} | {ev.get('location_name', '')}")
