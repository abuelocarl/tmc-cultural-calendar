"""
TMC Cultural Calendar - Main Scraper Runner
Run this script to scrape all sources and consolidate events.

Usage:
    python scrape.py                    # Scrape all sources (NYC + DC + Paris)
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
    python scrape.py --source nmah
    python scrape.py --source nasm
    python scrape.py --source nmai
    python scrape.py --source nmaahc
    python scrape.py --source nbm
    python scrape.py --source spymuseum
    python scrape.py --source nmaa
    python scrape.py --source paris     # All Paris museum scrapers
    python scrape.py --source pompidou
    python scrape.py --source louvre
    python scrape.py --source orsay
    python scrape.py --source palaisdetokyo
    python scrape.py --source fondationlv
    python scrape.py --source museepicasso
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
from scrapers.nmah_scraper import scrape_nmah_events
from scrapers.nasm_scraper import scrape_nasm_events
from scrapers.nmai_scraper import scrape_nmai_events
from scrapers.nmaahc_scraper import scrape_nmaahc_events
from scrapers.nbm_scraper import scrape_nbm_events
from scrapers.spymuseum_scraper import scrape_spymuseum_events
from scrapers.nmaa_scraper import scrape_nmaa_events
# Paris scrapers
from scrapers.pompidou_scraper import scrape_pompidou_events
from scrapers.louvre_scraper import scrape_louvre_events
from scrapers.orsay_scraper import scrape_orsay_events
from scrapers.palaisdetokyo_scraper import scrape_palaisdetokyo_events
from scrapers.fondationlv_scraper import scrape_fondationlv_events
from scrapers.museepicasso_scraper import scrape_museepicasso_events
from scrapers.saam_scraper import scrape_saam_events
from scrapers.npm_scraper import scrape_npm_events
from scrapers.ushmm_scraper import scrape_ushmm_events
from scrapers.nmwa_scraper import scrape_nmwa_events
from scrapers.planetword_scraper import scrape_planetword_events
from scrapers.phillips_scraper import scrape_phillips_events
from scrapers.nps_nama_scraper import scrape_nps_nama_events
from consolidator import consolidate_events, save_events, save_events_csv, load_events

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
DC_SOURCES = {"nga", "hirshhorn", "nmnh", "nmah", "nasm", "nmai", "nmaahc", "nbm", "spymuseum", "nmaa", "saam", "npm", "ushmm", "nmwa", "planetword", "phillips", "nama"}
PARIS_SOURCES = {"pompidou", "louvre", "orsay", "palaisdetokyo", "fondationlv", "museepicasso"}


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
        "nmah": 0,
        "nasm": 0,
        "nmai": 0,
        "nmaahc": 0,
        "nbm": 0,
        "spymuseum": 0,
        "nmaa": 0,
        "saam": 0,
        "npm": 0,
        "ushmm": 0,
        "nmwa": 0,
        "planetword": 0,
        "phillips": 0,
        "nama": 0,
        # Paris
        "pompidou": 0,
        "louvre": 0,
        "orsay": 0,
        "palaisdetokyo": 0,
        "fondationlv": 0,
        "museepicasso": 0,
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
    nmah_events = []
    nasm_events = []
    nmai_events = []
    nmaahc_events = []
    nbm_events = []
    spymuseum_events = []
    nmaa_events = []
    saam_events = []
    npm_events = []
    ushmm_events = []
    nmwa_events = []
    planetword_events = []
    phillips_events = []
    nama_events = []
    pompidou_events = []
    louvre_events = []
    orsay_events = []
    palaisdetokyo_events = []
    fondationlv_events = []
    museepicasso_events = []

    is_all = source == "all"
    is_museums = source == "museums"
    is_dc = source == "dc"
    is_paris = source == "paris"

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

    # ── NMAH ─────────────────────────────────────────────────────
    if is_all or is_dc or source == "nmah":
        logger.info("🇺🇸  Scraping NMAH events...")
        try:
            nmah_events = scrape_nmah_events()
            results["nmah"] = len(nmah_events)
            logger.info(f"  ✓ NMAH: {len(nmah_events)} events found")
        except Exception as e:
            msg = f"NMAH scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── NASM ─────────────────────────────────────────────────────
    if is_all or is_dc or source == "nasm":
        logger.info("🚀  Scraping National Air and Space Museum events...")
        try:
            nasm_events = scrape_nasm_events()
            results["nasm"] = len(nasm_events)
            logger.info(f"  ✓ NASM: {len(nasm_events)} events found")
        except Exception as e:
            msg = f"NASM scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── NMAI ─────────────────────────────────────────────────────
    if is_all or is_dc or source == "nmai":
        logger.info("🪶  Scraping National Museum of the American Indian events...")
        try:
            nmai_events = scrape_nmai_events()
            results["nmai"] = len(nmai_events)
            logger.info(f"  ✓ NMAI: {len(nmai_events)} events found")
        except Exception as e:
            msg = f"NMAI scraper failed: {e}"
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

    # ── National Museum of Asian Art ─────────────────────────────
    if is_all or is_dc or source == "nmaa":
        logger.info("🏯  Scraping National Museum of Asian Art events...")
        try:
            nmaa_events = scrape_nmaa_events()
            results["nmaa"] = len(nmaa_events)
            logger.info(f"  ✓ NMAA: {len(nmaa_events)} events found")
        except Exception as e:
            msg = f"NMAA scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Smithsonian American Art Museum ─────────────────────────
    if is_all or is_dc or source == "saam":
        logger.info("🎨  Scraping Smithsonian American Art Museum events...")
        try:
            saam_events = scrape_saam_events()
            results["saam"] = len(saam_events)
            logger.info(f"  ✓ SAAM: {len(saam_events)} events found")
        except Exception as e:
            msg = f"SAAM scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── National Postal Museum ───────────────────────────────────
    if is_all or is_dc or source == "npm":
        logger.info("📬  Scraping National Postal Museum events...")
        try:
            npm_events = scrape_npm_events()
            results["npm"] = len(npm_events)
            logger.info(f"  ✓ NPM: {len(npm_events)} events found")
        except Exception as e:
            msg = f"NPM scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── US Holocaust Memorial Museum ─────────────────────────────
    if is_all or is_dc or source == "ushmm":
        logger.info("🕯  Scraping US Holocaust Memorial Museum events...")
        try:
            ushmm_events = scrape_ushmm_events()
            results["ushmm"] = len(ushmm_events)
            logger.info(f"  ✓ USHMM: {len(ushmm_events)} events found")
        except Exception as e:
            msg = f"USHMM scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── National Museum of Women in the Arts ─────────────────────
    if is_all or is_dc or source == "nmwa":
        logger.info("🎨  Scraping National Museum of Women in the Arts events...")
        try:
            nmwa_events = scrape_nmwa_events()
            results["nmwa"] = len(nmwa_events)
            logger.info(f"  ✓ NMWA: {len(nmwa_events)} events found")
        except Exception as e:
            msg = f"NMWA scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Planet Word Museum ────────────────────────────────────────
    if is_all or is_dc or source == "planetword":
        logger.info("📚  Scraping Planet Word Museum events...")
        try:
            planetword_events = scrape_planetword_events()
            results["planetword"] = len(planetword_events)
            logger.info(f"  ✓ Planet Word: {len(planetword_events)} events found")
        except Exception as e:
            msg = f"Planet Word scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── The Phillips Collection ──────────────────────────────────
    if is_all or is_dc or source == "phillips":
        logger.info("🖼  Scraping The Phillips Collection events...")
        try:
            phillips_events = scrape_phillips_events()
            results["phillips"] = len(phillips_events)
            logger.info(f"  ✓ Phillips Collection: {len(phillips_events)} events found")
        except Exception as e:
            msg = f"Phillips scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── National Mall & Memorial Parks ───────────────────────────
    if is_all or is_dc or source == "nama":
        logger.info("🏛  Scraping National Mall & Memorial Parks events...")
        try:
            nama_events = scrape_nps_nama_events()
            results["nama"] = len(nama_events)
            logger.info(f"  ✓ National Mall: {len(nama_events)} events found")
        except Exception as e:
            msg = f"NPS NAMA scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Centre Pompidou ──────────────────────────────────────────
    if is_all or is_paris or source == "pompidou":
        logger.info("🎨  Scraping Centre Pompidou events...")
        try:
            pompidou_events = scrape_pompidou_events()
            results["pompidou"] = len(pompidou_events)
            logger.info(f"  ✓ Pompidou: {len(pompidou_events)} events found")
        except Exception as e:
            msg = f"Pompidou scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Louvre ───────────────────────────────────────────────────
    if is_all or is_paris or source == "louvre":
        logger.info("🏛  Scraping Louvre events...")
        try:
            louvre_events = scrape_louvre_events()
            results["louvre"] = len(louvre_events)
            logger.info(f"  ✓ Louvre: {len(louvre_events)} events found")
        except Exception as e:
            msg = f"Louvre scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Musée d'Orsay ────────────────────────────────────────────
    if is_all or is_paris or source == "orsay":
        logger.info("🖼  Scraping Musée d'Orsay events...")
        try:
            orsay_events = scrape_orsay_events()
            results["orsay"] = len(orsay_events)
            logger.info(f"  ✓ Orsay: {len(orsay_events)} events found")
        except Exception as e:
            msg = f"Orsay scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Palais de Tokyo ──────────────────────────────────────────
    if is_all or is_paris or source == "palaisdetokyo":
        logger.info("🎞  Scraping Jeu de Paume events...")
        try:
            palaisdetokyo_events = scrape_palaisdetokyo_events()
            results["palaisdetokyo"] = len(palaisdetokyo_events)
            logger.info(f"  ✓ Jeu de Paume: {len(palaisdetokyo_events)} events found")
        except Exception as e:
            msg = f"Jeu de Paume scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Fondation Louis Vuitton ──────────────────────────────────
    if is_all or is_paris or source == "fondationlv":
        logger.info("🌸  Scraping Musée de l'Orangerie events...")
        try:
            fondationlv_events = scrape_fondationlv_events()
            results["fondationlv"] = len(fondationlv_events)
            logger.info(f"  ✓ Orangerie: {len(fondationlv_events)} events found")
        except Exception as e:
            msg = f"Orangerie scraper failed: {e}"
            logger.error(msg)
            results["errors"].append(msg)

    # ── Musée Picasso ────────────────────────────────────────────
    if is_all or is_paris or source == "museepicasso":
        logger.info("🎭  Scraping Musée Picasso events...")
        try:
            museepicasso_events = scrape_museepicasso_events()
            results["museepicasso"] = len(museepicasso_events)
            logger.info(f"  ✓ Musée Picasso: {len(museepicasso_events)} events found")
        except Exception as e:
            msg = f"Musée Picasso scraper failed: {e}"
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
        nmah_events=nmah_events,
        nasm_events=nasm_events,
        nmai_events=nmai_events,
        nmaahc_events=nmaahc_events,
        nbm_events=nbm_events,
        spymuseum_events=spymuseum_events,
        nmaa_events=nmaa_events,
        saam_events=saam_events,
        npm_events=npm_events,
        ushmm_events=ushmm_events,
        nmwa_events=nmwa_events,
        planetword_events=planetword_events,
        phillips_events=phillips_events,
        nama_events=nama_events,
        pompidou_events=pompidou_events,
        louvre_events=louvre_events,
        orsay_events=orsay_events,
        palaisdetokyo_events=palaisdetokyo_events,
        fondationlv_events=fondationlv_events,
        museepicasso_events=museepicasso_events,
    )
    results["total"] = len(all_events)

    # ── Save ────────────────────────────────────────────────────
    if save and all_events:
        # When running a targeted source (not "all"), merge with the existing
        # store so other sources' events are preserved.
        if source != "all":
            existing = load_events("data/events.json")
            # Determine which source names the current run may have produced
            new_sources = {e.get("source", "") for e in all_events}
            # Keep existing events whose source wasn't touched by this run
            kept = [e for e in existing if e.get("source", "") not in new_sources]
            merged = kept + all_events
            merged.sort(key=lambda e: e.get("date", "9999-99-99"))
            save_events(merged, "data/events.json")
            save_events_csv(merged, "data/events.csv")
            logger.info(
                f"💾  Merged {len(all_events)} new + {len(kept)} existing "
                f"= {len(merged)} total events saved"
            )
            results["total"] = len(merged)
        else:
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
        f"  NMAH:                 {results['nmah']:>4} events\n"
        f"  NASM:                 {results['nasm']:>4} events\n"
        f"  NMAI:                 {results['nmai']:>4} events\n"
        f"  NMAAHC:               {results['nmaahc']:>4} events\n"
        f"  Natl Building Museum: {results['nbm']:>4} events\n"
        f"  Spy Museum:           {results['spymuseum']:>4} events\n"
        f"  Natl Museum Asian Art:{results['nmaa']:>4} events\n"
        f"  SAAM:                 {results['saam']:>4} events\n"
        f"  Natl Postal Museum:   {results['npm']:>4} events\n"
        f"  Holocaust Mem Museum: {results['ushmm']:>4} events\n"
        f"  Natl Museum Women Arts:{results['nmwa']:>4} events\n"
        f"  Planet Word Museum:   {results['planetword']:>4} events\n"
        f"  Phillips Collection:  {results['phillips']:>4} events\n"
        f"  Natl Mall & Mem Parks:{results['nama']:>4} events\n"
        f"  ── Paris ──────────────────────────────\n"
        f"  Pompidou:             {results['pompidou']:>4} events\n"
        f"  Louvre:               {results['louvre']:>4} events\n"
        f"  Musée d'Orsay:        {results['orsay']:>4} events\n"
        f"  Palais de Tokyo:      {results['palaisdetokyo']:>4} events\n"
        f"  Fondation LV:         {results['fondationlv']:>4} events\n"
        f"  Musée Picasso:        {results['museepicasso']:>4} events\n"
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
            "all", "museums", "dc", "paris",
            "nyc", "eventbrite", "timeout",
            "amnh", "moma", "whitney", "mcny", "newmuseum", "nyhistory",
            "nga", "hirshhorn", "nmnh", "nmah", "nasm", "nmai", "nmaahc", "nbm", "spymuseum", "nmaa",
            "saam", "npm", "ushmm", "nmwa", "planetword", "phillips", "nama",
            "pompidou", "louvre", "orsay", "palaisdetokyo", "fondationlv", "museepicasso",
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
