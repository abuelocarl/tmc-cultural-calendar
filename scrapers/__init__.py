"""
TMC Cultural Calendar - Scrapers Package
Consolidates all event sources into a unified event format.
"""

from .nyc_gov_scraper import scrape_nyc_gov_events
from .eventbrite_scraper import scrape_eventbrite_nyc
from .timeout_scraper import scrape_timeout_nyc
from .amnh_scraper import scrape_amnh_events
from .moma_scraper import scrape_moma_events
from .whitney_scraper import scrape_whitney_events
from .mcny_scraper import scrape_mcny_events
from .newmuseum_scraper import scrape_newmuseum_events
from .nyhistory_scraper import scrape_nyhistory_events

__all__ = [
    "scrape_nyc_gov_events",
    "scrape_eventbrite_nyc",
    "scrape_timeout_nyc",
    "scrape_amnh_events",
    "scrape_moma_events",
    "scrape_whitney_events",
    "scrape_mcny_events",
    "scrape_newmuseum_events",
    "scrape_nyhistory_events",
]
