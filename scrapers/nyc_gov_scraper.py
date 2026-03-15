"""
NYC.gov Events Scraper
Scrapes cultural events from NYC.gov
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)


def scrape_nyc_gov_events() -> List[Dict]:
    """Scrape events from NYC.gov events page."""
    events = []
    
    urls = [
        "https://www.nyc.gov/events/index.page",
        "https://www.nyc.gov/site/events/index.page",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    # Try NYC Parks events API (publicly accessible)
    try:
        parks_url = "https://www.nycgovparks.org/events/json"
        response = requests.get(parks_url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            for item in data[:50]:  # Limit to 50 events
                event = {
                    "title": item.get("EventName", "NYC Parks Event"),
                    "date": item.get("StartDate", ""),
                    "end_date": item.get("EndDate", ""),
                    "time": item.get("StartTime", ""),
                    "location": item.get("Location", "NYC Parks"),
                    "description": item.get("Description", ""),
                    "url": f"https://www.nycgovparks.org{item.get('EventDetailURL', '')}",
                    "category": "Parks & Recreation",
                    "source": "NYC.gov Parks",
                    "borough": item.get("Borough", ""),
                    "image_url": "",
                    "price": "Free",
                }
                if event["title"] and event["date"]:
                    events.append(event)
    except Exception as e:
        logger.warning(f"NYC Parks JSON API failed: {e}")
    
    # Fallback: NYC Parks HTML scraper
    if not events:
        try:
            parks_html_url = "https://www.nycgovparks.org/events/free-events-listing"
            response = requests.get(parks_html_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")
            
            event_items = soup.find_all("div", class_=re.compile(r"event|listing", re.I))
            for item in event_items[:30]:
                title_el = item.find(["h2", "h3", "h4", "a"])
                date_el = item.find(class_=re.compile(r"date|time", re.I))
                location_el = item.find(class_=re.compile(r"location|venue", re.I))
                
                if title_el:
                    event = {
                        "title": title_el.get_text(strip=True),
                        "date": date_el.get_text(strip=True) if date_el else "",
                        "end_date": "",
                        "time": "",
                        "location": location_el.get_text(strip=True) if location_el else "New York City",
                        "description": "",
                        "url": parks_html_url,
                        "category": "Parks & Recreation",
                        "source": "NYC.gov Parks",
                        "borough": "",
                        "image_url": "",
                        "price": "Free",
                    }
                    if event["title"]:
                        events.append(event)
        except Exception as e:
            logger.warning(f"NYC Parks HTML scraper failed: {e}")

    # NYC Cultural Affairs events
    try:
        culture_url = "https://www.nyc.gov/site/dcla/events/events.page"
        response = requests.get(culture_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")
        
        event_cards = soup.find_all(["article", "div"], class_=re.compile(r"event|card|listing", re.I))
        for card in event_cards[:20]:
            title_el = card.find(["h2", "h3", "h4"])
            date_el = card.find(class_=re.compile(r"date", re.I))
            link_el = card.find("a", href=True)
            
            if title_el:
                event = {
                    "title": title_el.get_text(strip=True),
                    "date": date_el.get_text(strip=True) if date_el else "",
                    "end_date": "",
                    "time": "",
                    "location": "New York City",
                    "description": "",
                    "url": link_el["href"] if link_el else culture_url,
                    "category": "Arts & Culture",
                    "source": "NYC Cultural Affairs",
                    "borough": "",
                    "image_url": "",
                    "price": "Varies",
                }
                if event["title"]:
                    events.append(event)
    except Exception as e:
        logger.warning(f"NYC Cultural Affairs scraper failed: {e}")

    logger.info(f"NYC.gov scraper found {len(events)} events")
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    events = scrape_nyc_gov_events()
    print(f"Found {len(events)} NYC.gov events")
    for e in events[:3]:
        print(f"  - {e['title']} | {e['date']} | {e['location']}")
