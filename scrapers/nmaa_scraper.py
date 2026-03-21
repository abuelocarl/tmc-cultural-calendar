"""
National Museum of Asian Art — Washington DC (Freer Gallery | Sackler Gallery)
Events: https://asia.si.edu/whats-on/events/search/

Server-rendered WordPress/PHP, 12 cards per page.
Pagination via ?listStart=N — follow a.next.page-numbers href directly.

Card structure:
  li > .card > .card__content > .card__title > a.secondary-link  → title + href
                              > .card__body  > p.event-search__date  → "Wednesday, March 18, 2026<br>1:00 pm–2:00 pm"
                                             > p.event-search__topic → "Gallery Talks & Tours"
             > .card__media  > .card__media-inner > img              → image (Trumba CDN)
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

NMAA_BASE = "https://asia.si.edu"
NMAA_URL  = f"{NMAA_BASE}/whats-on/events/search/"

LOCATION = (
    "National Museum of Asian Art, "
    "1050 Independence Ave SW, Washington, DC 20560"
)

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
    "screening":     "Arts & Culture",
    "exhibition":    "Arts & Culture",
    "performance":   "Arts & Culture",
    "demonstration": "Arts & Culture",
    "concert":       "Music",
    "music":         "Music",
    "lecture":       "Heritage & History",
    "talk":          "Heritage & History",
    "tour":          "Heritage & History",
    "gallery":       "Heritage & History",
    "discussion":    "Heritage & History",
    "symposium":     "Heritage & History",
    "workshop":      "Community",
    "family":        "Community",
    "kids":          "Community",
    "children":      "Community",
    "festival":      "Festivals",
    "celebration":   "Festivals",
}


def _infer_category(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def _parse_date_time(date_el):
    """
    Parse a p.event-search__date element containing HTML like:
      Wednesday, March 18, 2026<br>1:00 pm–2:00 pm
    Returns (date_iso, time_str, end_time_str).
    """
    if not date_el:
        return "", "", ""

    # Split on <br> to separate date line from time line
    raw_html = str(date_el)
    parts    = re.split(r"<br\s*/?>", raw_html, flags=re.I)

    date_text = BeautifulSoup(parts[0], "html.parser").get_text(strip=True) if parts else ""
    time_text = (
        BeautifulSoup(parts[1], "html.parser").get_text(strip=True)
        if len(parts) > 1 else ""
    )

    # Parse date — strip leading weekday, grab "Month DD, YYYY"
    date_iso = ""
    date_m   = re.search(
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{1,2}),\s+(\d{4})",
        date_text, re.I,
    )
    if date_m:
        try:
            dt = datetime.strptime(date_m.group(0), "%B %d, %Y")
            if date.today() <= dt.date() <= date.today() + timedelta(days=183):
                date_iso = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    if not date_iso:
        return "", "", ""

    # Parse time range — separator is en-dash (–) or hyphen
    time_str     = ""
    end_time_str = ""
    time_m       = re.search(
        r"(\d{1,2}(?::\d{2})?\s*[ap]m)\s*[–\-]\s*(\d{1,2}(?::\d{2})?\s*[ap]m)",
        time_text, re.I,
    )
    if time_m:
        time_str     = _to_24h(time_m.group(1))
        end_time_str = _to_24h(time_m.group(2))
    else:
        single_m = re.search(r"(\d{1,2}(?::\d{2})?\s*[ap]m)", time_text, re.I)
        if single_m:
            time_str = _to_24h(single_m.group(1))

    return date_iso, time_str, end_time_str


def _to_24h(time_raw: str) -> str:
    """Convert '1:00 pm', '11am', '12:00 pm' → '13:00', '11:00', '12:00'."""
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


def scrape_nmaa_events() -> List[Dict]:
    """Scrape events from the National Museum of Asian Art calendar."""
    events    = []
    seen_urls = set()
    url       = NMAA_URL

    while url:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"NMAA: failed to fetch {url}: {e}")
            break

        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".card-set li")
        logger.info(f"NMAA: {url} — {len(cards)} cards")

        if not cards:
            break

        for card in cards:
            try:
                # ── Title + URL ──────────────────────────────────────────
                title_a = card.select_one(".card__title a, a.secondary-link")
                if not title_a:
                    continue
                # Remove decorative arrow span before extracting text
                for span in title_a.select("span"):
                    span.decompose()
                title = title_a.get_text(strip=True)
                if not title:
                    continue
                # Skip cancelled events
                if re.match(r"cancell?ed", title, re.I):
                    continue

                href      = title_a.get("href", "")
                event_url = href if href.startswith("http") else NMAA_BASE + href
                if event_url in seen_urls:
                    continue
                seen_urls.add(event_url)

                # ── Date + time ──────────────────────────────────────────
                date_el                        = card.select_one("p.event-search__date")
                date_iso, time_str, end_time_str = _parse_date_time(date_el)
                if not date_iso:
                    continue

                # ── Image ────────────────────────────────────────────────
                img_el    = card.select_one(".card__media-inner img, .card__media img")
                image_url = ""
                if img_el:
                    src       = img_el.get("src", "")
                    image_url = src if src.startswith("http") else NMAA_BASE + src

                # ── Topic / description ──────────────────────────────────
                topic_el    = card.select_one("p.event-search__topic")
                description = topic_el.get_text(strip=True) if topic_el else ""

                # ── Flags ────────────────────────────────────────────────
                combined_text = (title + " " + description).lower()
                is_family  = any(w in combined_text for w in
                                 ["family", "kids", "children", "all ages"])
                is_outdoor = any(w in combined_text for w in
                                 ["outdoor", "garden", "courtyard", "open air"])

                events.append({
                    "title":              title,
                    "date":               date_iso,
                    "end_date":           "",
                    "time":               time_str,
                    "end_time":           end_time_str,
                    "location":           LOCATION,
                    "location_name":      "National Museum of Asian Art",
                    "location_address":   "1050 Independence Ave SW, Washington, DC 20560",
                    "neighborhood":       "National Mall",
                    "description":        description[:400],
                    "url":                event_url,
                    "category":           _infer_category(title, description),
                    "source":             "National Museum of Asian Art",
                    "borough":            "National Mall",
                    "image_url":          image_url,
                    "price":              "Free",
                    "is_free":            True,
                    "is_family_friendly": is_family,
                    "is_outdoor":         is_outdoor,
                    "city":               "Washington DC",
                })

            except Exception as e:
                logger.debug(f"NMAA: error parsing card: {e}")

        # Pagination — follow next button; cap at 60 events (~5 pages)
        next_link = soup.select_one("a.next.page-numbers, .pagination a.next")
        if not next_link or len(events) >= 60:
            break
        next_href = next_link.get("href", "")
        url = next_href if next_href.startswith("http") else NMAA_BASE + next_href

    logger.info(f"NMAA: scraped {len(events)} events")
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_nmaa_events()
    print(f"\nFound {len(results)} NMAA events:")
    for ev in results:
        end = f" → {ev['end_time']}" if ev.get("end_time") else ""
        print(f"  [{ev['date']}] {ev['title']}")
        print(f"           {ev['time']}{end} | {ev['category']}")
