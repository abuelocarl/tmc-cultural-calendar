"""
New Museum - Events Scraper
Scrapes upcoming events from https://newmuseum.org/events/ via __NEXT_DATA__ JSON
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import logging
import re
import json
from typing import List, Dict

logger = logging.getLogger(__name__)

BASE_URL = "https://www.newmuseum.org"
EVENTS_URL = "https://newmuseum.org/events/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_iso_date(date_str: str):
    """Parse ISO date string like '2026-03-21T00:00:00' into (date_iso, time_str)."""
    if not date_str:
        return "", ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.date() < date.today():
            return "", ""
        date_iso = dt.strftime("%Y-%m-%d")
        time_str = f"{dt.hour:02d}:{dt.minute:02d}" if (dt.hour or dt.minute) else ""
        return date_iso, time_str
    except (ValueError, AttributeError):
        # Try date-only
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            if dt.date() < date.today():
                return "", ""
            return dt.strftime("%Y-%m-%d"), ""
        except ValueError:
            return "", ""


def _extract_events_from_next_data(data: dict) -> List[Dict]:
    """Navigate the __NEXT_DATA__ structure to find event nodes."""
    # Try the known path from research
    try:
        nodes = (
            data["props"]["pageProps"]["__TEMPLATE_QUERY_DATA__"]["events"]["nodes"]
        )
        return nodes
    except (KeyError, TypeError):
        pass

    # Fallback: recursively search for a key "nodes" containing event-like objects
    def find_nodes(obj, depth=0):
        if depth > 8:
            return None
        if isinstance(obj, dict):
            if "nodes" in obj and isinstance(obj["nodes"], list):
                nodes = obj["nodes"]
                if nodes and isinstance(nodes[0], dict) and "title" in nodes[0]:
                    return nodes
            for v in obj.values():
                result = find_nodes(v, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = find_nodes(item, depth + 1)
                if result:
                    return result
        return None

    return find_nodes(data) or []


def scrape_newmuseum_events() -> List[Dict]:
    """Scrape upcoming events from the New Museum via __NEXT_DATA__ JSON."""
    events = []

    try:
        response = requests.get(EVENTS_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"New Museum: failed to fetch events page: {e}")
        return events

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract __NEXT_DATA__ JSON blob
    next_data_script = soup.find("script", id="__NEXT_DATA__")
    if not next_data_script:
        logger.warning("New Museum: __NEXT_DATA__ script not found")
        return events

    try:
        next_data = json.loads(next_data_script.string)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"New Museum: failed to parse __NEXT_DATA__: {e}")
        return events

    nodes = _extract_events_from_next_data(next_data)
    if not nodes:
        logger.warning("New Museum: no event nodes found in __NEXT_DATA__")
        return events

    for node in nodes:
        title = node.get("title", "").strip()
        if not title:
            continue

        start_date = node.get("startDate", "") or node.get("date", "")
        end_date = node.get("endDate", "")
        date_iso, time_str = _parse_iso_date(start_date)
        if not date_iso:
            continue
        end_date_iso, _ = _parse_iso_date(end_date)

        # URL
        url = node.get("link", "") or node.get("uri", "") or node.get("url", "")
        if url and not url.startswith("http"):
            url = BASE_URL + url
        if not url:
            url = EVENTS_URL

        # Image
        image_url = ""
        featured_image = node.get("featuredImage", {})
        if featured_image and isinstance(featured_image, dict):
            node_img = featured_image.get("node", {})
            image_url = node_img.get("sourceUrl", "") if isinstance(node_img, dict) else ""

        # Description
        description = node.get("excerpt", "") or node.get("description", "")
        if description:
            description = re.sub(r"<[^>]+>", "", description).strip()[:300]

        link_text = (title + " " + description).lower()
        is_free = any(w in link_text for w in ["free", "no cost", "complimentary"])
        is_family = any(w in link_text for w in ["family", "kids", "children", "all ages"])
        end_time = ""
        if time_str:
            import re as _re
            range_m = _re.search(r"[-–]\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*$", time_str, _re.I)
            if range_m:
                end_time = range_m.group(1).strip()
        events.append({
            "title": title,
            "date": date_iso,
            "end_date": end_date_iso,
            "time": time_str,
            "end_time": end_time,
            "location": "New Museum, 235 Bowery, New York, NY 10002",
            "location_name": "New Museum",
            "location_address": "235 Bowery, New York, NY 10002",
            "neighborhood": "Lower East Side",
            "description": description,
            "url": url,
            "category": "Arts & Culture",
            "source": "New Museum",
            "borough": "Manhattan",
            "image_url": image_url,
            "price": "Free" if is_free else "See website",
            "is_free": is_free,
            "is_family_friendly": is_family,
            "city": "New York",
        })

    # Deduplicate by URL
    seen = set()
    unique = []
    for e in events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)

    logger.info(f"New Museum scraper found {len(unique)} events")
    return unique


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_newmuseum_events()
    print(f"\nFound {len(results)} New Museum events:")
    for ev in results:
        print(f"  [{ev['date']}] {ev['title']}")
