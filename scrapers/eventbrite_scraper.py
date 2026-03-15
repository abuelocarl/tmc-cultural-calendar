"""
Eventbrite NYC Cultural Events Scraper
Scrapes cultural events from Eventbrite NYC listings
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import re
import json
from typing import List, Dict

logger = logging.getLogger(__name__)


def scrape_eventbrite_nyc() -> List[Dict]:
    """Scrape cultural events from Eventbrite NYC."""
    events = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    
    # Cultural category searches on Eventbrite
    search_queries = [
        ("arts", "Arts & Culture"),
        ("music", "Music"),
        ("festival", "Festivals"),
        ("community", "Community"),
        ("heritage", "Heritage & History"),
    ]
    
    for query, category in search_queries:
        try:
            url = f"https://www.eventbrite.com/d/ny--new-york/{query}--events/"
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Eventbrite returned {response.status_code} for {query}")
                continue
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Try to find JSON-LD structured data
            json_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = data.get("@graph", [data])
                    else:
                        continue
                    
                    for item in items:
                        if item.get("@type") in ["Event", "MusicEvent", "ExhibitionEvent"]:
                            location = item.get("location", {})
                            if isinstance(location, dict):
                                venue_name = location.get("name", "")
                                address = location.get("address", {})
                                if isinstance(address, dict):
                                    venue_address = f"{address.get('streetAddress', '')}, {address.get('addressLocality', 'New York')}"
                                else:
                                    venue_address = str(address)
                                full_location = f"{venue_name} - {venue_address}".strip(" -")
                            else:
                                full_location = str(location)
                            
                            offers = item.get("offers", {})
                            if isinstance(offers, list) and offers:
                                offers = offers[0]
                            price = "Free" if isinstance(offers, dict) and offers.get("price") == "0" else "See website"
                            
                            event = {
                                "title": item.get("name", ""),
                                "date": item.get("startDate", ""),
                                "end_date": item.get("endDate", ""),
                                "time": "",
                                "location": full_location or "New York, NY",
                                "description": item.get("description", "")[:300],
                                "url": item.get("url", url),
                                "category": category,
                                "source": "Eventbrite",
                                "borough": "Manhattan",
                                "image_url": item.get("image", ""),
                                "price": price,
                            }
                            if event["title"]:
                                events.append(event)
                except Exception as e:
                    logger.debug(f"JSON-LD parse error: {e}")
                    continue
            
            # Fallback: HTML scraping
            if not events:
                event_cards = soup.find_all(
                    ["article", "div", "li"],
                    attrs={"data-testid": re.compile(r"event|card", re.I)}
                )
                
                # Also try class-based selection
                if not event_cards:
                    event_cards = soup.find_all(
                        ["article", "div"],
                        class_=re.compile(r"search-event-card|event-card|eds-event-card", re.I)
                    )
                
                for card in event_cards[:15]:
                    title_el = card.find(["h2", "h3", "h4", "h1"])
                    date_el = card.find(class_=re.compile(r"date|time", re.I))
                    location_el = card.find(class_=re.compile(r"location|venue|place", re.I))
                    link_el = card.find("a", href=re.compile(r"/e/"))
                    
                    if title_el:
                        event = {
                            "title": title_el.get_text(strip=True),
                            "date": date_el.get_text(strip=True) if date_el else "",
                            "end_date": "",
                            "time": "",
                            "location": location_el.get_text(strip=True) if location_el else "New York, NY",
                            "description": "",
                            "url": f"https://www.eventbrite.com{link_el['href']}" if link_el else url,
                            "category": category,
                            "source": "Eventbrite",
                            "borough": "",
                            "image_url": "",
                            "price": "See website",
                        }
                        if event["title"] and len(event["title"]) > 3:
                            events.append(event)
                            
        except Exception as e:
            logger.warning(f"Eventbrite scraper failed for {query}: {e}")
    
    # Deduplicate by title
    seen = set()
    unique_events = []
    for event in events:
        key = event["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique_events.append(event)
    
    logger.info(f"Eventbrite scraper found {len(unique_events)} unique events")
    return unique_events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    events = scrape_eventbrite_nyc()
    print(f"Found {len(events)} Eventbrite events")
    for e in events[:3]:
        print(f"  - {e['title']} | {e['date']} | {e['location']}")
