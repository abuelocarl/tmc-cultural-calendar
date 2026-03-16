"""
TMC Cultural Calendar - Main Scraper Runner
Run this script to scrape all sources and consolidate events.

Usage:
    python scrape.py                    # Scrape all sources
    python scrape.py --source nyc       # Scrape only NYC.gov
    python scrape.py --source eventbrite
    python scrape.py --source timeout
    python scrape.py --no-save          # Scrape but don't save
"""

import argparse
import logging
import sys
import time
from datetime import datetime

from scrapers.nyc_gov_scraper import scrape_nyc_gov_events
from scrapers.eventbrite_scraper import scrape_eventbrite_nyc
from scrapers.timeout_scraper import scrape_timeout_nyc
from scrapers.amnh_scraper import scrape_amnh_events
from consolidator import consolidate_events, save_events

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", mode="a"),
    ],
)

logger = logging.getLogger("tmc-scraper")


def run_scraper(source: str = "all", save: bool = True) -> dict:
    """Run scrapers and consolidate events."""
    start_time = time.time()
    results = {
        "started_at": datetime.utcnow().isoformat(),
        "source": source,
        "nyc_gov": 0,
        "eventbrite": 0,
        "timeout": 0,
        "amnh": 0,
        "total": 0,
        "errors": [],
    }

    nyc_events = []
    eventbrite_events = []
    timeout_events = []
    amnh_events = []
    
    # ── NYC.gov ─────────────────────────────────────────────────
    if source in ("all", "nyc"):
        logger.info("🏛  Scraping NYC.gov events...")
        try:
            nyc_events = scrape_nyc_gov_events()
            results["nyc_gov"] = len(nyc_events)
            logger.info(f"  ✓ NYC.gov: {len(nyc_events)} events found")
        except Exception as e:
            msg = f"NYC.gov scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)
    
    # ── Eventbrite ──────────────────────────────────────────────
    if source in ("all", "eventbrite"):
        logger.info("🎟  Scraping Eventbrite NYC events...")
        try:
            eventbrite_events = scrape_eventbrite_nyc()
            results["eventbrite"] = len(eventbrite_events)
            logger.info(f"  ✓ Eventbrite: {len(eventbrite_events)} events found")
        except Exception as e:
            msg = f"Eventbrite scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)
    
    # ── TimeOut NY ──────────────────────────────────────────────
    if source in ("all", "timeout"):
        logger.info("⏱  Scraping TimeOut New York events...")
        try:
            timeout_events = scrape_timeout_nyc()
            results["timeout"] = len(timeout_events)
            logger.info(f"  ✓ TimeOut NY: {len(timeout_events)} events found")
        except Exception as e:
            msg = f"TimeOut scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)
    
    # ── AMNH ────────────────────────────────────────────────────
    if source in ("all", "amnh"):
        logger.info("🦕  Scraping AMNH events...")
        try:
            amnh_events = scrape_amnh_events()
            results["amnh"] = len(amnh_events)
            logger.info(f"  ✓ AMNH: {len(amnh_events)} events found")
        except Exception as e:
            msg = f"AMNH scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Consolidate ─────────────────────────────────────────────
    logger.info("🔄  Consolidating events...")
    all_events = consolidate_events(
        nyc_events=nyc_events,
        eventbrite_events=eventbrite_events,
        timeout_events=timeout_events,
        amnh_events=amnh_events,
    )
    results["total"] = len(all_events)
    
    # ── Save ────────────────────────────────────────────────────
    if save and all_events:
        save_events(all_events, "data/events.json")
        logger.info(f"💾  Saved {len(all_events)} events to data/events.json")
    elif save and not all_events:
        logger.warning("⚠️  No events found — data/events.json not updated")
    
    elapsed = time.time() - start_time
    results["elapsed_seconds"] = round(elapsed, 2)
    results["completed_at"] = datetime.utcnow().isoformat()
    
    logger.info(
        f"\n{'='*50}\n"
        f"  TMC Cultural Calendar - Scrape Complete\n"
        f"  NYC.gov:    {results['nyc_gov']:>4} events\n"
        f"  Eventbrite: {results['eventbrite']:>4} events\n"
        f"  TimeOut NY: {results['timeout']:>4} events\n"
        f"  AMNH:       {results['amnh']:>4} events\n"
        f"  Total:      {results['total']:>4} unique events\n"
        f"  Duration:   {elapsed:.1f}s\n"
        f"{'='*50}"
    )
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="TMC Cultural Calendar - Event Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape.py                      Scrape all sources
  python scrape.py --source nyc         Only NYC.gov
  python scrape.py --source eventbrite  Only Eventbrite
  python scrape.py --source timeout     Only TimeOut NY
  python scrape.py --no-save            Dry run (no file written)
        """,
    )
    parser.add_argument(
        "--source",
        choices=["all", "nyc", "eventbrite", "timeout", "amnh"],
        default="all",
        help="Which source to scrape (default: all)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save results to file",
    )
    
    args = parser.parse_args()
    results = run_scraper(source=args.source, save=not args.no_save)
    
    if results["errors"]:
        print(f"\n⚠️  {len(results['errors'])} error(s) occurred:")
        for err in results["errors"]:
            print(f"  - {err}")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
