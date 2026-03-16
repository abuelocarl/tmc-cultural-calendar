"""
TMC Cultural Calendar - Main Scraper Runner
Run this script to scrape all sources and consolidate events.

Usage:
    python scrape.py                    # Scrape all sources (NYC + DC)
    python scrape.py --source nyc       # Scrape only NYC.gov
    python scrape.py --source eventbrite
    python scrape.py --source timeout
    python scrape.py --source amnh
    python scrape.py --source moma
    python scrape.py --source whitney
    python scrape.py --source mcny
    python scrape.py --source newmuseum
    python scrape.py --source nyhistory
    python scrape.py --source museums   # All NYC museum scrapers
    python scrape.py --source dc        # All DC museum scrapers
    python scrape.py --source nga
    python scrape.py --source hirshhorn
    python scrape.py --source nmnh
    python scrape.py --source nmaahc
    python scrape.py --source nbm
    python scrape.py --source spymuseum
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
from scrapers.moma_scraper import scrape_moma_events
from scrapers.whitney_scraper import scrape_whitney_events
from scrapers.mcny_scraper import scrape_mcny_events
from scrapers.newmuseum_scraper import scrape_newmuseum_events
from scrapers.nyhistory_scraper import scrape_nyhistory_events
# DC scrapers
from scrapers.nga_scraper import scrape_nga_events
from scrapers.hirshhorn_scraper import scrape_hirshhorn_events
from scrapers.nmnh_scraper import scrape_nmnh_events
from scrapers.nmaahc_scraper import scrape_nmaahc_events
from scrapers.nbm_scraper import scrape_nbm_events
from scrapers.spymuseum_scraper import scrape_spymuseum_events
from consolidator import consolidate_events, save_events, save_events_csv

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

MUSEUM_SOURCES = {"amnh", "moma", "whitney", "mcny", "newmuseum", "nyhistory"}
DC_SOURCES = {"nga", "hirshhorn", "nmnh", "nmaahc", "nbm", "spymuseum"}


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
        "moma": 0,
        "whitney": 0,
        "mcny": 0,
        "newmuseum": 0,
        "nyhistory": 0,
        # DC
        "nga": 0,
        "hirshhorn": 0,
        "nmnh": 0,
        "nmaahc": 0,
        "nbm": 0,
        "spymuseum": 0,
        "total": 0,
        "errors": [],
    }

    nyc_events = []
    eventbrite_events = []
    timeout_events = []
    amnh_events = []
    moma_events = []
    whitney_events = []
    mcny_events = []
    newmuseum_events = []
    nyhistory_events = []
    nga_events = []
    hirshhorn_events = []
    nmnh_events = []
    nmaahc_events = []
    nbm_events = []
    spymuseum_events = []

    is_all = source == "all"
    is_museums = source == "museums"
    is_dc = source == "dc"

    # ── NYC.gov ─────────────────────────────────────────────────
    if is_all or source == "nyc":
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
    if is_all or source == "eventbrite":
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
    if is_all or source == "timeout":
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
    if is_all or is_museums or source == "amnh":
        logger.info("🦕  Scraping AMNH events...")
        try:
            amnh_events = scrape_amnh_events()
            results["amnh"] = len(amnh_events)
            logger.info(f"  ✓ AMNH: {len(amnh_events)} events found")
        except Exception as e:
            msg = f"AMNH scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── MoMA ────────────────────────────────────────────────────
    if is_all or is_museums or source == "moma":
        logger.info("🖼  Scraping MoMA events...")
        try:
            moma_events = scrape_moma_events()
            results["moma"] = len(moma_events)
            logger.info(f"  ✓ MoMA: {len(moma_events)} events found")
        except Exception as e:
            msg = f"MoMA scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Whitney ─────────────────────────────────────────────────
    if is_all or is_museums or source == "whitney":
        logger.info("🎨  Scraping Whitney Museum events...")
        try:
            whitney_events = scrape_whitney_events()
            results["whitney"] = len(whitney_events)
            logger.info(f"  ✓ Whitney: {len(whitney_events)} events found")
        except Exception as e:
            msg = f"Whitney scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── MCNY ────────────────────────────────────────────────────
    if is_all or is_museums or source == "mcny":
        logger.info("🗽  Scraping MCNY events...")
        try:
            mcny_events = scrape_mcny_events()
            results["mcny"] = len(mcny_events)
            logger.info(f"  ✓ MCNY: {len(mcny_events)} events found")
        except Exception as e:
            msg = f"MCNY scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── New Museum ──────────────────────────────────────────────
    if is_all or is_museums or source == "newmuseum":
        logger.info("🏢  Scraping New Museum events...")
        try:
            newmuseum_events = scrape_newmuseum_events()
            results["newmuseum"] = len(newmuseum_events)
            logger.info(f"  ✓ New Museum: {len(newmuseum_events)} events found")
        except Exception as e:
            msg = f"New Museum scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── NY Historical Society ────────────────────────────────────
    if is_all or is_museums or source == "nyhistory":
        logger.info("📜  Scraping NY Historical Society events...")
        try:
            nyhistory_events = scrape_nyhistory_events()
            results["nyhistory"] = len(nyhistory_events)
            logger.info(f"  ✓ NY Historical: {len(nyhistory_events)} events found")
        except Exception as e:
            msg = f"NY Historical scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── NGA ─────────────────────────────────────────────────────
    if is_all or is_dc or source == "nga":
        logger.info("🖼  Scraping National Gallery of Art events...")
        try:
            nga_events = scrape_nga_events()
            results["nga"] = len(nga_events)
            logger.info(f"  ✓ NGA: {len(nga_events)} events found")
        except Exception as e:
            msg = f"NGA scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Hirshhorn ────────────────────────────────────────────────
    if is_all or is_dc or source == "hirshhorn":
        logger.info("🎨  Scraping Hirshhorn Museum events...")
        try:
            hirshhorn_events = scrape_hirshhorn_events()
            results["hirshhorn"] = len(hirshhorn_events)
            logger.info(f"  ✓ Hirshhorn: {len(hirshhorn_events)} events found")
        except Exception as e:
            msg = f"Hirshhorn scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── NMNH ─────────────────────────────────────────────────────
    if is_all or is_dc or source == "nmnh":
        logger.info("🦴  Scraping NMNH events...")
        try:
            nmnh_events = scrape_nmnh_events()
            results["nmnh"] = len(nmnh_events)
            logger.info(f"  ✓ NMNH: {len(nmnh_events)} events found")
        except Exception as e:
            msg = f"NMNH scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── NMAAHC ───────────────────────────────────────────────────
    if is_all or is_dc or source == "nmaahc":
        logger.info("🏛  Scraping NMAAHC events...")
        try:
            nmaahc_events = scrape_nmaahc_events()
            results["nmaahc"] = len(nmaahc_events)
            logger.info(f"  ✓ NMAAHC: {len(nmaahc_events)} events found")
        except Exception as e:
            msg = f"NMAAHC scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── National Building Museum ─────────────────────────────────
    if is_all or is_dc or source == "nbm":
        logger.info("🏗  Scraping National Building Museum events...")
        try:
            nbm_events = scrape_nbm_events()
            results["nbm"] = len(nbm_events)
            logger.info(f"  ✓ National Building Museum: {len(nbm_events)} events found")
        except Exception as e:
            msg = f"NBM scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Spy Museum ───────────────────────────────────────────────
    if is_all or is_dc or source == "spymuseum":
        logger.info("🕵  Scraping International Spy Museum events...")
        try:
            spymuseum_events = scrape_spymuseum_events()
            results["spymuseum"] = len(spymuseum_events)
            logger.info(f"  ✓ Spy Museum: {len(spymuseum_events)} events found")
        except Exception as e:
            msg = f"Spy Museum scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Consolidate ─────────────────────────────────────────────
    logger.info("🔄  Consolidating events...")
    all_events = consolidate_events(
        nyc_events=nyc_events,
        eventbrite_events=eventbrite_events,
        timeout_events=timeout_events,
        amnh_events=amnh_events,
        moma_events=moma_events,
        whitney_events=whitney_events,
        mcny_events=mcny_events,
        newmuseum_events=newmuseum_events,
        nyhistory_events=nyhistory_events,
        nga_events=nga_events,
        hirshhorn_events=hirshhorn_events,
        nmnh_events=nmnh_events,
        nmaahc_events=nmaahc_events,
        nbm_events=nbm_events,
        spymuseum_events=spymuseum_events,
    )
    results["total"] = len(all_events)

    # ── Save ────────────────────────────────────────────────────
    if save and all_events:
        save_events(all_events, "data/events.json")
        save_events_csv(all_events, "data/events.csv")
        logger.info(f"💾  Saved {len(all_events)} events to data/events.json + data/events.csv")
    elif save and not all_events:
        logger.warning("⚠️  No events found — data files not updated")

    elapsed = time.time() - start_time
    results["elapsed_seconds"] = round(elapsed, 2)
    results["completed_at"] = datetime.utcnow().isoformat()

    logger.info(
        f"\n{'='*50}\n"
        f"  TMC Cultural Calendar - Scrape Complete\n"
        f"  ── New York City ──────────────────────\n"
        f"  NYC.gov:              {results['nyc_gov']:>4} events\n"
        f"  Eventbrite:           {results['eventbrite']:>4} events\n"
        f"  TimeOut NY:           {results['timeout']:>4} events\n"
        f"  AMNH:                 {results['amnh']:>4} events\n"
        f"  MoMA:                 {results['moma']:>4} events\n"
        f"  Whitney:              {results['whitney']:>4} events\n"
        f"  MCNY:                 {results['mcny']:>4} events\n"
        f"  New Museum:           {results['newmuseum']:>4} events\n"
        f"  NY Historical:        {results['nyhistory']:>4} events\n"
        f"  ── Washington DC ──────────────────────\n"
        f"  NGA:                  {results['nga']:>4} events\n"
        f"  Hirshhorn:            {results['hirshhorn']:>4} events\n"
        f"  NMNH:                 {results['nmnh']:>4} events\n"
        f"  NMAAHC:               {results['nmaahc']:>4} events\n"
        f"  Natl Building Museum: {results['nbm']:>4} events\n"
        f"  Spy Museum:           {results['spymuseum']:>4} events\n"
        f"  ───────────────────────────────────────\n"
        f"  Total:                {results['total']:>4} unique events\n"
        f"  Duration:             {elapsed:.1f}s\n"
        f"{'='*50}"
    )

    return results


def main():
    parser = argparse.ArgumentParser(
        description="TMC Cultural Calendar - Event Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape.py                       Scrape all sources
  python scrape.py --source museums      All museum scrapers only
  python scrape.py --source amnh         AMNH only
  python scrape.py --source moma         MoMA only
  python scrape.py --source whitney      Whitney only
  python scrape.py --source mcny         MCNY only
  python scrape.py --source newmuseum    New Museum only
  python scrape.py --source nyhistory    NY Historical only
  python scrape.py --source nyc          NYC.gov only
  python scrape.py --source eventbrite   Eventbrite only
  python scrape.py --source timeout      TimeOut NY only
  python scrape.py --no-save             Dry run (no file written)
        """,
    )
    parser.add_argument(
        "--source",
        choices=[
            "all", "museums", "dc",
            "nyc", "eventbrite", "timeout",
            "amnh", "moma", "whitney", "mcny", "newmuseum", "nyhistory",
            "nga", "hirshhorn", "nmnh", "nmaahc", "nbm", "spymuseum",
        ],
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
