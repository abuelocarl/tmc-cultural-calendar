"""
TimeOut New York Cultural Events Scraper
Scrapes cultural events from TimeOut New York
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import json
import re
from typing import List, Dict

logger = logging.getLogger(__name__)


def scrape_timeout_nyc() -> List[Dict]:
    """Scrape cultural events from TimeOut New York."""
    events = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.timeout.com/",
    }
    
    # TimeOut NYC section URLs for cultural events
    sections = [
        ("https://www.timeout.com/newyork/things-to-do/best-things-to-do-in-nyc-this-weekend", "Weekend Picks"),
        ("https://www.timeout.com/newyork/art/best-art-shows-in-nyc-right-now", "Art"),
        ("https://www.timeout.com/newyork/music/best-concerts-in-nyc-this-week", "Music"),
        ("https://www.timeout.com/newyork/theater/best-shows-on-broadway-and-off-broadway", "Theater"),
        ("https://www.timeout.com/newyork/festivals-and-events/best-festivals-and-events-in-nyc", "Festivals"),
        ("https://www.timeout.com/newyork/dance/best-dance-performances-in-nyc", "Dance"),
    ]
    
    for url, category in sections:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.warning(f"TimeOut returned {response.status_code} for {url}")
                continue
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Extract JSON-LD structured data
            json_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_scripts:
                try:
                    data = json.loads(script.string or "")
                    items = []
                    if isinstance(data, dict) and data.get("@type") == "ItemList":
                        items = data.get("itemListElement", [])
                    elif isinstance(data, list):
                        items = data
                    
                    for item in items:
                        thing = item.get("item", item)
                        if not isinstance(thing, dict):
                            continue
                        
                        location = thing.get("location", {})
                        if isinstance(location, dict):
                            loc_str = location.get("name", "New York, NY")
                        else:
                            loc_str = "New York, NY"
                        
                        event = {
                            "title": thing.get("name", ""),
                            "date": thing.get("startDate", ""),
                            "end_date": thing.get("endDate", ""),
                            "time": "",
                            "location": loc_str,
                            "description": thing.get("description", "")[:300],
                            "url": thing.get("url", url),
                            "category": category,
                            "source": "TimeOut NY",
                            "borough": "",
                            "image_url": thing.get("image", ""),
                            "price": "See website",
                        }
                        if event["title"]:
                            events.append(event)
                except Exception as e:
                    logger.debug(f"JSON-LD parse error: {e}")
                    continue
            
            # HTML-based scraping fallback
            # TimeOut uses various article/card patterns
            article_selectors = [
                soup.find_all("article"),
                soup.find_all("div", class_=re.compile(r"tile|card|listing|feature", re.I)),
                soup.find_all("li", class_=re.compile(r"item|result|event", re.I)),
            ]
            
            article_list = []
            for selector_results in article_selectors:
                if selector_results:
                    article_list = selector_results
                    break
            
            for article in article_list[:20]:
                # Skip navigation / sidebar elements
                if article.find_parent(["nav", "aside", "header", "footer"]):
                    continue
                
                title_el = article.find(["h2", "h3", "h4", "h1"])
                if not title_el:
                    continue
                
                title_text = title_el.get_text(strip=True)
                if len(title_text) < 5 or len(title_text) > 200:
                    continue
                
                link_el = article.find("a", href=re.compile(r"/newyork/"))
                date_el = article.find(["time", "span"], class_=re.compile(r"date|time|when", re.I))
                venue_el = article.find(class_=re.compile(r"venue|location|place|where", re.I))
                desc_el = article.find(["p", "div"], class_=re.compile(r"desc|summary|teaser|copy", re.I))
                img_el = article.find("img")
                
                event = {
                    "title": title_text,
                    "date": date_el.get_text(strip=True) if date_el else "",
                    "end_date": "",
                    "time": "",
                    "location": venue_el.get_text(strip=True) if venue_el else "New York, NY",
                    "description": desc_el.get_text(strip=True)[:300] if desc_el else "",
                    "url": f"https://www.timeout.com{link_el['href']}" if link_el and link_el.get("href", "").startswith("/") else (link_el["href"] if link_el else url),
                    "category": category,
                    "source": "TimeOut NY",
                    "borough": "",
                    "image_url": img_el.get("src", img_el.get("data-src", "")) if img_el else "",
                    "price": "See website",
                }
                events.append(event)
                
        except Exception as e:
            logger.warning(f"TimeOut scraper failed for {url}: {e}")
    
    # Deduplicate by title
    seen = set()
    unique_events = []
    for event in events:
        key = event["title"].lower().strip()
        if key not in seen and len(key) > 3:
            seen.add(key)
            unique_events.append(event)
    
    logger.info(f"TimeOut NY scraper found {len(unique_events)} unique events")
    return unique_events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    events = scrape_timeout_nyc()
    print(f"Found {len(events)} TimeOut NY events")
    for e in events[:3]:
        print(f"  - {e['title']} | {e['date']} | {e['location']}")
