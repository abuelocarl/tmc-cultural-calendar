#!/usr/bin/env python3
"""
TMC Scraper Audit Harness
=========================
Runs every scraper, validates event data quality, writes detailed logs.

Usage:
    python3 scripts/audit_scrapers.py                   # Audit all scrapers
    python3 scripts/audit_scrapers.py --source nmah     # Audit one scraper
    python3 scripts/audit_scrapers.py --source dc       # Audit DC group
    python3 scripts/audit_scrapers.py --source nyc      # Audit NYC group
    python3 scripts/audit_scrapers.py --source paris    # Audit Paris group
    python3 scripts/audit_scrapers.py --no-file         # Console only, no log file
    python3 scripts/audit_scrapers.py --json            # Also write JSON summary

Exit codes:  0 = all PASS   1 = any FAIL   2 = any ERROR
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Scraper imports ───────────────────────────────────────────────────────────
from scrapers.amnh_scraper       import scrape_amnh_events
from scrapers.moma_scraper       import scrape_moma_events
from scrapers.whitney_scraper    import scrape_whitney_events
from scrapers.mcny_scraper       import scrape_mcny_events
from scrapers.newmuseum_scraper  import scrape_newmuseum_events
from scrapers.nyhistory_scraper  import scrape_nyhistory_events
from scrapers.nga_scraper        import scrape_nga_events
from scrapers.hirshhorn_scraper  import scrape_hirshhorn_events
from scrapers.nmnh_scraper       import scrape_nmnh_events
from scrapers.nmah_scraper       import scrape_nmah_events
from scrapers.nasm_scraper       import scrape_nasm_events
from scrapers.nmai_scraper       import scrape_nmai_events
from scrapers.nmaahc_scraper     import scrape_nmaahc_events
from scrapers.nbm_scraper        import scrape_nbm_events
from scrapers.spymuseum_scraper  import scrape_spymuseum_events
from scrapers.nmaa_scraper       import scrape_nmaa_events
from scrapers.pompidou_scraper   import scrape_pompidou_events
from scrapers.louvre_scraper     import scrape_louvre_events
from scrapers.orsay_scraper      import scrape_orsay_events
from scrapers.palaisdetokyo_scraper import scrape_palaisdetokyo_events
from scrapers.fondationlv_scraper   import scrape_fondationlv_events
from scrapers.museepicasso_scraper  import scrape_museepicasso_events
from scrapers.saam_scraper          import scrape_saam_events
from scrapers.npm_scraper           import scrape_npm_events

# ── Validation patterns ───────────────────────────────────────────────────────
DATE_RE         = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE         = re.compile(r"^\d{2}:\d{2}$")
HTML_ENTITY_RE  = re.compile(r"&(?:[a-z]{2,6}|#\d{1,5});", re.I)
URL_RE          = re.compile(r"^https?://")
TODAY           = date.today()
FAR_FUTURE      = TODAY + timedelta(days=730)   # 2 years

VALID_CATEGORIES = {
    "Arts & Culture", "Music", "Theater", "Dance",
    "Festivals", "Parks & Recreation", "Heritage & History",
    "Community", "Weekend Picks", "Other",
}
VALID_CITIES = {"New York", "Washington DC", "Paris"}

# ── Scraper registry ──────────────────────────────────────────────────────────
# key: {
#   fn           – scraper function
#   source       – expected canonical source string (None = skip check)
#   cities       – set of valid city values for this scraper's events
#   min_events   – FAIL if fewer events returned
#   warn_below   – WARN if fewer events returned
#   group        – "nyc" | "dc" | "paris"
#   emoji        – display emoji
# }
SCRAPERS: Dict[str, Dict] = {
    # ── NYC ──────────────────────────────────────────────────────────────────
    "amnh": {
        "fn":          scrape_amnh_events,
        "source":      "American Museum of Natural History",
        "cities":      {"New York"},
        "min_events":  1,
        "warn_below":  5,
        "group":       "nyc",
        "emoji":       "🦕",
    },
    "moma": {
        "fn":          scrape_moma_events,
        "source":      "Museum of Modern Art",
        "cities":      {"New York"},
        "min_events":  1,
        "warn_below":  5,
        "group":       "nyc",
        "emoji":       "🖼",
    },
    "whitney": {
        "fn":          scrape_whitney_events,
        "source":      "Whitney Museum of American Art",
        "cities":      {"New York"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "nyc",
        "emoji":       "🎨",
    },
    "mcny": {
        "fn":          scrape_mcny_events,
        "source":      "Museum of the City of New York",
        "cities":      {"New York"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "nyc",
        "emoji":       "🗽",
    },
    "newmuseum": {
        "fn":          scrape_newmuseum_events,
        "source":      "New Museum",
        "cities":      {"New York"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "nyc",
        "emoji":       "🏢",
    },
    "nyhistory": {
        "fn":          scrape_nyhistory_events,
        "source":      "New-York Historical Society",
        "cities":      {"New York"},
        "min_events":  0,   # site may have no upcoming programs; 0 is acceptable
        "warn_below":  3,
        "group":       "nyc",
        "emoji":       "📜",
    },
    # ── DC ───────────────────────────────────────────────────────────────────
    "nga": {
        "fn":          scrape_nga_events,
        "source":      "National Gallery of Art",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  5,
        "group":       "dc",
        "emoji":       "🖼",
    },
    "hirshhorn": {
        "fn":          scrape_hirshhorn_events,
        "source":      "Hirshhorn Museum",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "dc",
        "emoji":       "🎨",
    },
    "nmnh": {
        "fn":          scrape_nmnh_events,
        "source":      "National Museum of Natural History",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "dc",
        "emoji":       "🦴",
    },
    "nmah": {
        "fn":          scrape_nmah_events,
        "source":      "National Museum of American History",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  5,
        "group":       "dc",
        "emoji":       "🇺🇸",
    },
    "nasm": {
        "fn":          scrape_nasm_events,
        "source":      "National Air and Space Museum",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  5,
        "group":       "dc",
        "emoji":       "🚀",
    },
    "nmai": {
        "fn":          scrape_nmai_events,
        "source":      "National Museum of the American Indian",
        "cities":      {"Washington DC", "New York"},   # dual-branch
        "min_events":  5,
        "warn_below":  20,
        "group":       "dc",
        "emoji":       "🪶",
    },
    "nmaahc": {
        "fn":          scrape_nmaahc_events,
        "source":      "National Museum of African American History and Culture",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "dc",
        "emoji":       "✊",
    },
    "nbm": {
        "fn":          scrape_nbm_events,
        "source":      "National Building Museum",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "dc",
        "emoji":       "🏗",
    },
    "spymuseum": {
        "fn":          scrape_spymuseum_events,
        "source":      "International Spy Museum",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "dc",
        "emoji":       "🕵",
    },
    "nmaa": {
        "fn":          scrape_nmaa_events,
        "source":      "National Museum of Asian Art",
        "cities":      {"Washington DC"},
        "min_events":  5,
        "warn_below":  20,
        "group":       "dc",
        "emoji":       "🏯",
    },
    "saam": {
        "fn":          scrape_saam_events,
        "source":      "Smithsonian American Art Museum",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  5,
        "group":       "dc",
        "emoji":       "🎨",
    },
    "npm": {
        "fn":          scrape_npm_events,
        "source":      "National Postal Museum",
        "cities":      {"Washington DC"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "dc",
        "emoji":       "📬",
    },
    # ── Paris ─────────────────────────────────────────────────────────────────
    "pompidou": {
        "fn":          scrape_pompidou_events,
        "source":      "Centre Pompidou",
        "cities":      {"Paris"},
        "min_events":  1,
        "warn_below":  5,
        "group":       "paris",
        "emoji":       "🎨",
    },
    "louvre": {
        "fn":          scrape_louvre_events,
        "source":      "Musée du Louvre",
        "cities":      {"Paris"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "paris",
        "emoji":       "🏛",
    },
    "orsay": {
        "fn":          scrape_orsay_events,
        "source":      "Musée d'Orsay",
        "cities":      {"Paris"},
        "min_events":  0,   # site uses JS rendering / blocks scrapers; 0 is acceptable
        "warn_below":  3,
        "group":       "paris",
        "emoji":       "🖼",
    },
    "palaisdetokyo": {
        "fn":          scrape_palaisdetokyo_events,
        "source":      "Jeu de Paume",
        "cities":      {"Paris"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "paris",
        "emoji":       "🎞",
    },
    "fondationlv": {
        "fn":          scrape_fondationlv_events,
        "source":      "Musée de l'Orangerie",
        "cities":      {"Paris"},
        "min_events":  0,   # listing page has no per-event dates; 0 is acceptable
        "warn_below":  3,
        "group":       "paris",
        "emoji":       "🌸",
    },
    "museepicasso": {
        "fn":          scrape_museepicasso_events,
        "source":      "Musée Picasso Paris",
        "cities":      {"Paris"},
        "min_events":  1,
        "warn_below":  3,
        "group":       "paris",
        "emoji":       "🎭",
    },
}

GROUP_KEYS = {
    "nyc":   [k for k, v in SCRAPERS.items() if v["group"] == "nyc"],
    "dc":    [k for k, v in SCRAPERS.items() if v["group"] == "dc"],
    "paris": [k for k, v in SCRAPERS.items() if v["group"] == "paris"],
}

# ── ANSI colours ──────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
DIM    = "\033[2m"


def _c(text: str, colour: str) -> str:
    """Apply colour if stdout is a TTY."""
    if sys.stdout.isatty():
        return f"{colour}{text}{RESET}"
    return text


# ── Issue dataclass ───────────────────────────────────────────────────────────
class Issue:
    __slots__ = ("level", "check", "message", "event_title", "event_date")

    def __init__(
        self,
        level: str,           # "ERROR" | "WARN" | "INFO"
        check: str,
        message: str,
        event_title: str = "",
        event_date: str  = "",
    ):
        self.level       = level
        self.check       = check
        self.message     = message
        self.event_title = event_title
        self.event_date  = event_date

    def __repr__(self):
        loc = f"[{self.event_date}] {self.event_title[:50]}" if self.event_title else ""
        return f"{self.level:<5} {self.check:<25} {self.message}  {loc}"


# ── Per-event quality checks ──────────────────────────────────────────────────
def _check_event(ev: Dict, spec: Dict) -> List[Issue]:
    issues: List[Issue] = []
    title = ev.get("title", "")
    dt    = ev.get("date",  "")

    def issue(level, check, msg):
        issues.append(Issue(level, check, msg, title, dt))

    # Title
    if not title:
        issue("ERROR", "HAS_TITLE",    "title is empty")
    elif HTML_ENTITY_RE.search(title):
        issue("WARN",  "TITLE_CLEAN",  f"HTML entities in title: {title[:80]}")

    # Description
    desc = ev.get("description", "")
    if desc and HTML_ENTITY_RE.search(desc):
        issue("WARN",  "DESC_CLEAN",   "HTML entities in description")

    # Date
    if not dt:
        issue("ERROR", "HAS_DATE",     "date is empty")
    elif not DATE_RE.match(dt):
        issue("ERROR", "DATE_FORMAT",  f"invalid date format: {dt!r}")
    else:
        try:
            d = date.fromisoformat(dt)
            if d < TODAY:
                issue("WARN",  "DATE_FUTURE", f"date is in the past: {dt}")
            elif d > FAR_FUTURE:
                issue("WARN",  "DATE_RANGE",  f"date is >2 years out: {dt}")
        except ValueError:
            issue("ERROR", "DATE_FORMAT",  f"unparseable date: {dt!r}")

    # Source
    expected_source = spec.get("source")
    actual_source   = ev.get("source", "")
    if not actual_source:
        issue("ERROR", "HAS_SOURCE",   "source is empty")
    elif expected_source and actual_source != expected_source:
        issue("ERROR", "SOURCE_MATCH", f"expected {expected_source!r}, got {actual_source!r}")

    # City
    city = ev.get("city", "")
    if not city:
        issue("ERROR", "HAS_CITY",     "city is empty")
    elif city not in VALID_CITIES:
        issue("ERROR", "CITY_KNOWN",   f"unknown city: {city!r}")
    elif city not in spec["cities"]:
        issue("WARN",  "CITY_EXPECTED", f"unexpected city {city!r} for this scraper")

    # URL
    url = ev.get("url", "")
    if not url:
        issue("WARN",  "HAS_URL",      "url is empty")
    elif not URL_RE.match(url):
        issue("WARN",  "URL_FORMAT",   f"url doesn't start with http: {url[:80]}")

    # Time formats
    for field in ("time", "end_time"):
        val = ev.get(field, "")
        if val and not TIME_RE.match(val):
            issue("WARN",  f"TIME_FORMAT_{field.upper()}", f"{field}={val!r} not HH:MM")

    # is_free
    is_free = ev.get("is_free")
    if not isinstance(is_free, bool):
        issue("WARN",  "IS_FREE_TYPE", f"is_free={is_free!r} is not bool")

    # Category
    cat = ev.get("category", "")
    if not cat:
        issue("WARN",  "HAS_CATEGORY", "category is empty")
    elif cat not in VALID_CATEGORIES:
        issue("WARN",  "CAT_KNOWN",    f"unknown category: {cat!r}")

    # Location
    if not ev.get("location", ""):
        issue("WARN",  "HAS_LOCATION", "location is empty")

    return issues


# ── Per-scraper audit ─────────────────────────────────────────────────────────
def _audit_scraper(key: str, spec: Dict) -> Dict:
    """Run one scraper and return a full audit report dict."""
    emoji   = spec["emoji"]
    label   = spec.get("source") or key
    report  = {
        "key":          key,
        "label":        label,
        "emoji":        emoji,
        "group":        spec["group"],
        "status":       "PASS",     # PASS | WARN | FAIL | ERROR
        "event_count":  0,
        "duration_s":   0.0,
        "issues":       [],         # list of Issue objects
        "issue_counts": {"ERROR": 0, "WARN": 0, "INFO": 0},
        "exception":    None,
        "events":       [],
    }

    t0 = time.time()
    try:
        events = spec["fn"]()
        report["duration_s"]  = round(time.time() - t0, 2)
        report["event_count"] = len(events)
        report["events"]      = events

        # ── Scraper-level checks ──────────────────────────────────────────────

        # Minimum event count
        if len(events) < spec["min_events"]:
            report["issues"].append(
                Issue("ERROR", "MIN_EVENTS",
                      f"returned {len(events)} events, below min={spec['min_events']}")
            )
        elif len(events) < spec["warn_below"]:
            report["issues"].append(
                Issue("WARN", "WARN_EVENTS",
                      f"only {len(events)} events — may be lower than expected (warn_below={spec['warn_below']})")
            )

        # Duplicate event IDs
        from consolidator import generate_event_id
        ids_seen: Dict[str, str] = {}
        for ev in events:
            eid = ev.get("id") or generate_event_id(ev)
            if eid in ids_seen:
                report["issues"].append(
                    Issue("WARN", "DUPLICATE_ID",
                          f"duplicate event ID: {eid}",
                          ev.get("title", ""), ev.get("date", ""))
                )
            else:
                ids_seen[eid] = ev.get("title", "")

        # Source consistency
        sources = {ev.get("source", "") for ev in events}
        if len(sources) > 1:
            report["issues"].append(
                Issue("WARN", "SOURCE_CONSISTENT",
                      f"multiple source values in one scraper: {sources}")
            )

        # ── Per-event checks ──────────────────────────────────────────────────
        for ev in events:
            report["issues"].extend(_check_event(ev, spec))

    except Exception as exc:
        report["duration_s"] = round(time.time() - t0, 2)
        report["exception"]  = traceback.format_exc()
        report["issues"].append(
            Issue("ERROR", "EXCEPTION", f"{type(exc).__name__}: {exc}")
        )

    # ── Tally and set status ──────────────────────────────────────────────────
    for iss in report["issues"]:
        report["issue_counts"][iss.level] = report["issue_counts"].get(iss.level, 0) + 1

    errors = report["issue_counts"]["ERROR"]
    warns  = report["issue_counts"]["WARN"]

    if report["exception"] or errors > 0:
        report["status"] = "FAIL" if not report["exception"] else "ERROR"
    elif warns > 0:
        report["status"] = "WARN"
    else:
        report["status"] = "PASS"

    return report


# ── Console rendering ─────────────────────────────────────────────────────────
STATUS_COLOUR = {
    "PASS":  GREEN,
    "WARN":  YELLOW,
    "FAIL":  RED,
    "ERROR": RED,
}
STATUS_ICON = {
    "PASS":  "✅",
    "WARN":  "⚠️ ",
    "FAIL":  "❌",
    "ERROR": "💥",
}


def _render_report(r: Dict, verbose: bool = False) -> str:
    lines = []
    col   = STATUS_COLOUR[r["status"]]
    icon  = STATUS_ICON[r["status"]]

    header = (
        f"\n{_c('─'*60, DIM)}\n"
        f"  {r['emoji']}  {_c(r['label'], BOLD)}  "
        f"[{r['key']}]  {icon} {_c(r['status'], col)}\n"
        f"{_c('─'*60, DIM)}"
    )
    lines.append(header)

    # Metrics row
    lines.append(
        f"  Events: {_c(str(r['event_count']), BOLD)}  "
        f"Duration: {r['duration_s']:.1f}s  "
        f"Errors: {_c(str(r['issue_counts']['ERROR']), RED if r['issue_counts']['ERROR'] else DIM)}  "
        f"Warnings: {_c(str(r['issue_counts']['WARN']), YELLOW if r['issue_counts']['WARN'] else DIM)}"
    )

    if r["exception"]:
        lines.append(f"\n  {_c('EXCEPTION:', RED)}")
        for ln in r["exception"].strip().splitlines():
            lines.append(f"    {ln}")

    # Show issues — always show ERRORs, show WARNs up to a cap
    errors = [i for i in r["issues"] if i.level == "ERROR"]
    warns  = [i for i in r["issues"] if i.level == "WARN"]

    if errors:
        lines.append(f"\n  {_c('Errors:', RED)}")
        for iss in errors:
            loc = f" [{iss.event_date}] {iss.event_title[:45]}" if iss.event_title else ""
            lines.append(f"    {_c('✗', RED)} {iss.check:<26} {iss.message}{_c(loc, DIM)}")

    warn_limit = 20 if verbose else 5
    if warns:
        shown   = warns[:warn_limit]
        omitted = len(warns) - len(shown)
        lines.append(f"\n  {_c('Warnings:', YELLOW)}")
        for iss in shown:
            loc = f" [{iss.event_date}] {iss.event_title[:45]}" if iss.event_title else ""
            lines.append(f"    {_c('⚠', YELLOW)} {iss.check:<26} {iss.message}{_c(loc, DIM)}")
        if omitted:
            lines.append(f"    {_c(f'… {omitted} more warnings (use --verbose to see all)', DIM)}")

    if r["status"] == "PASS":
        lines.append(f"\n  {_c('All checks passed.', GREEN)}")

    return "\n".join(lines)


def _render_summary(reports: List[Dict], elapsed: float) -> str:
    lines = []
    total   = len(reports)
    passed  = sum(1 for r in reports if r["status"] == "PASS")
    warned  = sum(1 for r in reports if r["status"] == "WARN")
    failed  = sum(1 for r in reports if r["status"] in ("FAIL", "ERROR"))
    ev_total = sum(r["event_count"] for r in reports)
    all_errors = sum(r["issue_counts"]["ERROR"] for r in reports)
    all_warns  = sum(r["issue_counts"]["WARN"]  for r in reports)

    lines.append(f"\n{'═'*60}")
    lines.append(f"  {_c('TMC Scraper Audit — Summary', BOLD)}")
    lines.append(f"{'═'*60}")
    lines.append(
        f"  Scrapers:  {total}   "
        f"{_c(f'✅ {passed} passed', GREEN)}  "
        f"{_c(f'⚠️  {warned} warned', YELLOW)}  "
        f"{_c(f'❌ {failed} failed', RED)}"
    )
    lines.append(
        f"  Events:    {ev_total} total  "
        f"Errors: {all_errors}  Warnings: {all_warns}"
    )
    lines.append(f"  Duration:  {elapsed:.1f}s")
    lines.append("")

    # Quick per-scraper status table
    for r in reports:
        col  = STATUS_COLOUR[r["status"]]
        icon = STATUS_ICON[r["status"]]
        line = (
            f"  {icon} {_c(r['status'].ljust(5), col)}  "
            f"{r['emoji']} {r['label']:<52}  "
            f"{r['event_count']:>4} events  "
            f"{r['duration_s']:>5.1f}s"
        )
        if r["issue_counts"]["ERROR"]:
            line += _c(f"  {r['issue_counts']['ERROR']}E", RED)
        if r["issue_counts"]["WARN"]:
            line += _c(f"  {r['issue_counts']['WARN']}W", YELLOW)
        lines.append(line)

    lines.append(f"{'═'*60}\n")
    return "\n".join(lines)


# ── File logging ──────────────────────────────────────────────────────────────
def _write_log(reports: List[Dict], elapsed: float, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"TMC Scraper Audit Log\n")
        f.write(f"Generated: {ts}\n")
        f.write(f"{'='*60}\n\n")

        for r in reports:
            f.write(f"[{r['group'].upper()}] {r['emoji']}  {r['label']}  [{r['key']}]\n")
            f.write(f"  Status:    {r['status']}\n")
            f.write(f"  Events:    {r['event_count']}\n")
            f.write(f"  Duration:  {r['duration_s']:.2f}s\n")
            f.write(f"  Errors:    {r['issue_counts']['ERROR']}\n")
            f.write(f"  Warnings:  {r['issue_counts']['WARN']}\n")

            if r["exception"]:
                f.write(f"\n  EXCEPTION:\n")
                for ln in r["exception"].strip().splitlines():
                    f.write(f"    {ln}\n")

            errors = [i for i in r["issues"] if i.level == "ERROR"]
            warns  = [i for i in r["issues"] if i.level == "WARN"]

            if errors:
                f.write(f"\n  ERRORS:\n")
                for iss in errors:
                    loc = f"  [{iss.event_date}] {iss.event_title[:60]}" if iss.event_title else ""
                    f.write(f"    ✗ {iss.check:<26} {iss.message}{loc}\n")

            if warns:
                f.write(f"\n  WARNINGS:\n")
                for iss in warns:
                    loc = f"  [{iss.event_date}] {iss.event_title[:60]}" if iss.event_title else ""
                    f.write(f"    ⚠ {iss.check:<26} {iss.message}{loc}\n")

            f.write("\n")

        # Summary
        total   = len(reports)
        passed  = sum(1 for r in reports if r["status"] == "PASS")
        warned  = sum(1 for r in reports if r["status"] == "WARN")
        failed  = sum(1 for r in reports if r["status"] in ("FAIL", "ERROR"))
        ev_total = sum(r["event_count"] for r in reports)

        f.write(f"{'='*60}\n")
        f.write(f"SUMMARY\n")
        f.write(f"  Scrapers:   {total} total / {passed} passed / {warned} warned / {failed} failed\n")
        f.write(f"  Events:     {ev_total} total\n")
        f.write(f"  Duration:   {elapsed:.1f}s\n")
        f.write(f"  Generated:  {ts}\n")

    print(f"  {_c('📄 Log written →', DIM)} {path}")


def _write_json(reports: List[Dict], elapsed: float, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "generated_at": datetime.now().isoformat(),
        "elapsed_s":    round(elapsed, 2),
        "summary": {
            "total":   len(reports),
            "passed":  sum(1 for r in reports if r["status"] == "PASS"),
            "warned":  sum(1 for r in reports if r["status"] == "WARN"),
            "failed":  sum(1 for r in reports if r["status"] in ("FAIL", "ERROR")),
            "events":  sum(r["event_count"] for r in reports),
        },
        "scrapers": [
            {
                "key":         r["key"],
                "label":       r["label"],
                "group":       r["group"],
                "status":      r["status"],
                "event_count": r["event_count"],
                "duration_s":  r["duration_s"],
                "errors":      r["issue_counts"]["ERROR"],
                "warnings":    r["issue_counts"]["WARN"],
                "exception":   r["exception"],
                "issues": [
                    {
                        "level":   i.level,
                        "check":   i.check,
                        "message": i.message,
                        "title":   i.event_title,
                        "date":    i.event_date,
                    }
                    for i in r["issues"]
                ],
            }
            for r in reports
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  {_c('📊 JSON written →', DIM)} {path}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="TMC Scraper Audit Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source", "-s",
        default="all",
        help="Scraper key, group (nyc|dc|paris), or 'all'",
    )
    parser.add_argument(
        "--no-file", action="store_true",
        help="Do not write log files",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Also write a JSON audit summary",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show all warnings (not just first 5 per scraper)",
    )
    args = parser.parse_args()

    # Resolve which scrapers to run
    source = args.source.lower()
    if source == "all":
        keys = list(SCRAPERS.keys())
    elif source in GROUP_KEYS:
        keys = GROUP_KEYS[source]
    elif source in SCRAPERS:
        keys = [source]
    else:
        print(f"Unknown source: {source!r}")
        print(f"Valid: all, nyc, dc, paris, {', '.join(SCRAPERS)}")
        sys.exit(2)

    ts_label = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir  = ROOT / "logs" / "audit"

    # Header
    print(f"\n{'═'*60}")
    print(f"  {_c('TMC Scraper Audit Harness', BOLD)}  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Scrapers to run: {len(keys)}")
    print(f"{'═'*60}")

    # Silence scraper loggers so our output stays clean
    logging.disable(logging.WARNING)

    global_t0 = time.time()
    reports: List[Dict] = []

    for key in keys:
        spec = SCRAPERS[key]
        print(f"\n  {spec['emoji']}  Running {_c(key, BOLD)} …", end="", flush=True)
        r = _audit_scraper(key, spec)
        reports.append(r)
        col  = STATUS_COLOUR[r["status"]]
        icon = STATUS_ICON[r["status"]]
        print(
            f"\r  {spec['emoji']}  {_c(key, BOLD):<30}  "
            f"{icon} {_c(r['status'].ljust(5), col)}  "
            f"{r['event_count']:>4} events  "
            f"{r['duration_s']:.1f}s"
        )

    elapsed = time.time() - global_t0
    logging.disable(logging.NOTSET)

    # Per-scraper detailed output
    for r in reports:
        print(_render_report(r, verbose=args.verbose))

    # Summary table
    print(_render_summary(reports, elapsed))

    # Log files
    if not args.no_file:
        log_path = log_dir / f"audit_{ts_label}.log"
        _write_log(reports, elapsed, log_path)

        if args.json:
            json_path = log_dir / f"audit_{ts_label}.json"
            _write_json(reports, elapsed, json_path)

    # Exit code
    any_fail = any(r["status"] in ("FAIL", "ERROR") for r in reports)
    any_warn = any(r["status"] == "WARN" for r in reports)
    sys.exit(1 if any_fail else (0))


if __name__ == "__main__":
    main()
