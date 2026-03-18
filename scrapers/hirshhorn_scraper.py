"""
Hirshhorn Museum and Sculpture Garden — Washington DC
Events: https://hirshhorn.si.edu/events/

Uses The Events Calendar (Tribe) plugin — same as NBM.
9 events/page; paginates via a.tribe-events-c-top-bar__nav-link--next href.

Card structure (article.tribe_events):
  time.datetime-day[datetime="YYYY-MM-DD"]     → date
  time[datetime="HH:MM"] (2nd occurrence)       → start time (24h)
  time[datetime="HH:MM"] (3rd occurrence)       → end time (24h)
  .list-item-title                              → title + link
  img                                           → thumbnail
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import List, Dict

logger = logging.getLogger(__name__)

HIRSHHORN_URL  = "https://hirshhorn.si.edu/events/"
HIRSHHORN_BASE = "https://hirshhorn.si.edu"
LOCATION = (
    "Hirshhorn Museum and Sculpture Garden, "
    "Independence Ave SW & 7th St SW, Washington, DC 20560"
)
BOROUGH = "National Mall"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_MAP = {
    "exhibition":   "Arts & Culture",
    "tour":         "Arts & Culture",
    "gallery":      "Arts & Culture",
    "studio":       "Arts & Culture",
    "art":          "Arts & Culture",
    "talk":         "Heritage & History",
    "lecture":      "Heritage & History",
    "conversation": "Heritage & History",
    "symposium":    "Heritage & History",
    "film":         "Arts & Culture",
    "screening":    "Arts & Culture",
    "performance":  "Arts & Culture",
    "concert":      "Music",
    "music":        "Music",
    "workshop":     "Community",
    "family":       "Community",
    "kids":         "Community",
    "storytime":    "Community",
    "teen":         "Community",
}


def _infer_category(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in combined:
            return cat
    return "Arts & Culture"


def scrape_hirshhorn_events() -> List[Dict]:
    """Scrape events from the Hirshhorn Museum and Sculpture Garden."""
    events    = []
    seen_urls = set()
    url       = HIRSHHORN_URL

    while url:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Hirshhorn: failed to fetch {url}: {e}")
            break

        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article.tribe_events, article[class*='tribe-events']")
        logger.info(f"Hirshhorn: {url} — {len(cards)} cards")

        if not cards:
            break

        for card in cards:
            try:
                # ── Title + URL ──────────────────────────────────────────
                title_el = (
                    card.select_one(".list-item-title")
                    or card.find(["h2", "h3", "h4"])
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                link = title_el.find("a", href=True) or card.find("a", href=True)
                event_url = ""
                if link:
                    href = link.get("href", "")
                    event_url = href if href.startswith("http") else HIRSHHORN_BASE + href
                if event_url in seen_urls:
                    continue
                if event_url:
                    seen_urls.add(event_url)

                # ── Date + times ─────────────────────────────────────────
                # time.datetime-day → date; subsequent time[datetime] → start, end
                all_time_els = card.select("time[datetime]")
                date_iso   = ""
                time_str   = ""
                end_time   = ""

                for t in all_time_els:
                    dt_val = t.get("datetime", "")
                    # Date: YYYY-MM-DD
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", dt_val):
                        try:
                            dt = datetime.strptime(dt_val, "%Y-%m-%d")
                            if dt.date() >= date.today():
                                date_iso = dt_val
                        except ValueError:
                            pass
                    # Time: HH:MM (already in 24h format from the site)
                    elif re.match(r"^\d{1,2}:\d{2}$", dt_val):
                        hour, minute = dt_val.split(":")
                        formatted = f"{int(hour):02d}:{minute}"
                        if not time_str:
                            time_str = formatted
                        elif not end_time:
                            end_time = formatted

                if not date_iso:
                    continue

                # ── Image ────────────────────────────────────────────────
                img_el    = card.find("img")
                image_url = ""
                if img_el:
                    src = img_el.get("src") or img_el.get("data-src") or ""
                    image_url = src if src.startswith("http") else (HIRSHHORN_BASE + src if src else "")

                # ── Description ──────────────────────────────────────────
                desc_el     = card.select_one(
                    ".tribe-events-calendar-list__event-description, "
                    ".list-item-excerpt, .tribe-common-b2, p"
                )
                description = desc_el.get_text(strip=True) if desc_el else ""

                # ── Flags ────────────────────────────────────────────────
                combined    = (title + " " + description).lower()
                is_family   = any(w in combined for w in ["family", "kids", "children", "all ages", "storytime"])
                is_outdoor  = any(w in combined for w in ["outdoor", "garden", "plaza", "sculpture garden"])

                events.append({
                    "title":              title,
                    "date":               date_iso,
                    "end_date":           "",
                    "time":               time_str,
                    "end_time":           end_time,
                    "location":           LOCATION,
                    "location_name":      "Hirshhorn Museum and Sculpture Garden",
                    "location_address":   "Independence Ave SW & 7th St SW, Washington, DC 20560",
                    "neighborhood":       "National Mall",
                    "description":        description[:400],
                    "url":                event_url,
                    "category":           _infer_category(title, description),
                    "source":             "Hirshhorn Museum",
                    "borough":            BOROUGH,
                    "image_url":          image_url,
                    "price":              "Free",
                    "is_free":            True,
                    "is_family_friendly": is_family,
                    "is_outdoor":         is_outdoor,
                    "city":               "Washington DC",
                })

            except Exception as e:
                logger.debug(f"Hirshhorn: error parsing card: {e}")

        # ── Pagination — cap at 60 events (~7 pages) ─────────────────────
        if len(events) >= 60:
            break
        next_link = soup.select_one(
            "a.tribe-events-c-top-bar__nav-link--next, "
            "a[aria-label='Next Events']"
        )
        if not next_link:
            break
        next_href = next_link.get("href", "")
        url = next_href if next_href.startswith("http") else HIRSHHORN_BASE + next_href

    logger.info(f"Hirshhorn: scraped {len(events)} events")
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_hirshhorn_events()
    print(f"\nFound {len(results)} Hirshhorn events:")
    for ev in results:
        end = f" → {ev['end_time']}" if ev.get("end_time") else ""
        print(f"  [{ev['date']}] {ev['title']}")
        print(f"           {ev['time']}{end} | {ev['category']}")
