"""
TMC Cultural Calendar - Flask Web Application
"""

import json
import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
)
from consolidator import (
    load_events,
    save_events,
    add_manual_event,
    delete_event,
    update_event,
    normalize_event,
    CATEGORIES,
    BOROUGHS,
    DC_NEIGHBORHOODS,
)

# ── App Setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tmc-cultural-calendar-dev-secret")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = "data/events.json"


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_events_metadata() -> Dict:
    """Load events and compute metadata for the UI."""
    events = load_events(DATA_FILE)
    
    # Load last_updated from JSON file
    last_updated = ""
    try:
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)
            last_updated = raw.get("last_updated", "")
    except Exception:
        pass
    
    sources = sorted(set(e.get("source", "Unknown") for e in events))
    categories = sorted(set(e.get("category", "Other") for e in events))
    boroughs = sorted(set(e.get("borough", "") for e in events if e.get("borough")))
    
    return {
        "events": events,
        "total": len(events),
        "sources": sources,
        "categories": categories,
        "boroughs": boroughs,
        "last_updated": last_updated,
        "all_categories": CATEGORIES,
        "all_boroughs": BOROUGHS,
    }


def filter_events(events: List[Dict], params: Dict) -> List[Dict]:
    """Filter events by query params."""
    q = params.get("q", "").lower().strip()
    category = params.get("category", "")
    source = params.get("source", "")
    borough = params.get("borough", "")
    city = params.get("city", "")
    date_from = params.get("date_from", "")
    date_to = params.get("date_to", "")
    free_only = params.get("free_only") == "1"
    tag = params.get("tag", "")

    result = events

    if q:
        result = [
            e for e in result
            if q in e.get("title", "").lower()
            or q in e.get("description", "").lower()
            or q in e.get("location", "").lower()
        ]
    if category:
        result = [e for e in result if e.get("category") == category]
    if source:
        result = [e for e in result if e.get("source") == source]
    if borough:
        result = [e for e in result if e.get("borough") == borough]
    if city:
        result = [e for e in result if e.get("city", "New York") == city]
    if date_from:
        result = [e for e in result if e.get("date", "") >= date_from]
    if date_to:
        result = [e for e in result if e.get("date", "") <= date_to]
    if free_only:
        result = [e for e in result if e.get("is_free")]
    if tag:
        result = [e for e in result if tag in e.get("tags", [])]

    return result


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    meta = get_events_metadata()
    params = request.args.to_dict()
    # Homepage is NYC-specific; DC has its own page
    nyc_params = dict(params, city="New York")
    filtered = filter_events(meta["events"], nyc_params)

    # Upcoming events (today onwards)
    today = date.today().isoformat()
    upcoming = [e for e in filtered if e.get("date", "") >= today or not e.get("date")]
    
    # Featured / highlight events
    featured = [e for e in upcoming if e.get("is_featured")][:6]
    if len(featured) < 3:
        featured = upcoming[:6]
    
    return render_template(
        "index.html",
        events=upcoming[:50],
        featured=featured,
        params=params,
        meta=meta,
        today=today,
        title="TMC Cultural Calendar",
    )


@app.route("/calendar")
def calendar_view():
    meta = get_events_metadata()
    params = request.args.to_dict()
    filtered = filter_events(meta["events"], params)
    
    # Group events by date for calendar view
    events_by_date = {}
    for event in filtered:
        d = event.get("date", "")
        if d:
            events_by_date.setdefault(d, []).append(event)
    
    return render_template(
        "calendar.html",
        events_by_date=events_by_date,
        events_json=json.dumps(filtered),
        params=params,
        meta=meta,
        title="Calendar View | TMC Cultural Calendar",
    )


@app.route("/events")
def event_list():
    meta = get_events_metadata()
    params = request.args.to_dict()
    filtered = filter_events(meta["events"], params)
    
    # Pagination
    page = int(params.get("page", 1))
    per_page = 24
    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = filtered[start:end]
    
    return render_template(
        "events.html",
        events=paginated,
        params=params,
        meta=meta,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=(total + per_page - 1) // per_page,
        title="All Events | TMC Cultural Calendar",
    )


@app.route("/dc")
def dc_events():
    meta = get_events_metadata()
    params = request.args.to_dict()
    params["city"] = "Washington DC"   # always pin to DC
    filtered = filter_events(meta["events"], params)

    today = date.today().isoformat()
    upcoming = [e for e in filtered if e.get("date", "") >= today or not e.get("date")]

    featured = [e for e in upcoming if e.get("is_featured")][:6]
    if len(featured) < 3:
        featured = upcoming[:6]

    dc_sources = sorted(set(e.get("source", "") for e in filtered))
    dc_neighborhoods = sorted(set(e.get("borough", "") for e in filtered if e.get("borough")))

    # Pagination
    page = int(params.get("page", 1))
    per_page = 24
    total = len(upcoming)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = upcoming[start:end]

    return render_template(
        "dc.html",
        events=paginated,
        featured=featured,
        params={k: v for k, v in params.items() if k != "city"},
        meta=meta,
        dc_sources=dc_sources,
        dc_neighborhoods=dc_neighborhoods,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=(total + per_page - 1) // per_page,
        today=today,
        title="Washington DC Events | TMC Cultural Calendar",
    )


@app.route("/event/<event_id>")
def event_detail(event_id):
    events = load_events(DATA_FILE)
    event = next((e for e in events if e.get("id") == event_id), None)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("index"))
    
    # Related events (same category)
    related = [
        e for e in events
        if e.get("category") == event.get("category")
        and e.get("id") != event_id
    ][:4]
    
    return render_template(
        "event_detail.html",
        event=event,
        related=related,
        title=f"{event['title']} | TMC Cultural Calendar",
    )


@app.route("/admin")
def admin():
    meta = get_events_metadata()
    return render_template(
        "admin.html",
        meta=meta,
        categories=CATEGORIES,
        boroughs=BOROUGHS,
        title="Admin | TMC Cultural Calendar",
    )


@app.route("/admin/add", methods=["GET", "POST"])
def add_event():
    if request.method == "POST":
        data = request.form.to_dict()
        try:
            event = add_manual_event(data, DATA_FILE)
            flash(f"Event '{event['title']}' added successfully!", "success")
            return redirect(url_for("admin"))
        except Exception as e:
            flash(f"Error adding event: {e}", "error")
    
    return render_template(
        "event_form.html",
        event={},
        categories=CATEGORIES,
        boroughs=BOROUGHS,
        action="Add",
        title="Add Event | TMC Cultural Calendar",
    )


@app.route("/admin/edit/<event_id>", methods=["GET", "POST"])
def edit_event(event_id):
    events = load_events(DATA_FILE)
    event = next((e for e in events if e.get("id") == event_id), None)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("admin"))
    
    if request.method == "POST":
        updates = request.form.to_dict()
        updated = update_event(event_id, updates, DATA_FILE)
        if updated:
            flash(f"Event updated successfully!", "success")
            return redirect(url_for("admin"))
        else:
            flash("Failed to update event.", "error")
    
    return render_template(
        "event_form.html",
        event=event,
        categories=CATEGORIES,
        boroughs=BOROUGHS,
        action="Edit",
        title="Edit Event | TMC Cultural Calendar",
    )


@app.route("/admin/delete/<event_id>", methods=["POST"])
def delete_event_route(event_id):
    success = delete_event(event_id, DATA_FILE)
    if success:
        flash("Event deleted.", "success")
    else:
        flash("Event not found.", "error")
    return redirect(url_for("admin"))


@app.route("/admin/feature/<event_id>", methods=["POST"])
def toggle_feature(event_id):
    events = load_events(DATA_FILE)
    event = next((e for e in events if e.get("id") == event_id), None)
    if event:
        current = event.get("is_featured", False)
        update_event(event_id, {"is_featured": not current}, DATA_FILE)
    return redirect(url_for("admin"))


# ── CORS (for Webflow / external frontends) ──────────────────────────────────

@app.after_request
def add_cors_headers(response):
    if request.path.startswith("/api/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/api/<path:path>", methods=["OPTIONS"])
def api_options(path):
    resp = app.make_default_options_response()
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


# ── API Routes ───────────────────────────────────────────────────────────────

@app.route("/api/events")
def api_events():
    meta = get_events_metadata()
    params = request.args.to_dict()
    filtered = filter_events(meta["events"], params)
    return jsonify({
        "total": len(filtered),
        "events": filtered,
        "last_updated": meta["last_updated"],
    })


@app.route("/api/events/<event_id>")
def api_event(event_id):
    events = load_events(DATA_FILE)
    event = next((e for e in events if e.get("id") == event_id), None)
    if not event:
        return jsonify({"error": "Not found"}), 404
    return jsonify(event)


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """Trigger a scrape run via API."""
    try:
        from scrape import run_scraper
        source = request.json.get("source", "all") if request.is_json else "all"
        results = run_scraper(source=source)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    meta = get_events_metadata()
    today = date.today().isoformat()
    events = meta["events"]
    
    stats = {
        "total_events": meta["total"],
        "upcoming_events": len([e for e in events if e.get("date", "") >= today]),
        "free_events": len([e for e in events if e.get("is_free")]),
        "sources": {s: len([e for e in events if e.get("source") == s]) for s in meta["sources"]},
        "categories": {c: len([e for e in events if e.get("category") == c]) for c in meta["categories"]},
        "boroughs": {b: len([e for e in events if e.get("borough") == b]) for b in meta["boroughs"]},
        "last_updated": meta["last_updated"],
    }
    return jsonify(stats)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    
    # Seed with sample data if no events file exists
    if not Path(DATA_FILE).exists():
        print("No events data found. Run 'python scrape.py' to populate events.")
        save_events([], DATA_FILE)
    
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    
    print(f"\n🎭 TMC Cultural Calendar running at http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
