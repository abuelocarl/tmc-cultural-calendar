"""
TMC Cultural Calendar - Admin Console
Flask app providing a web-based admin interface for managing scrapers.
Runs on port 5002.
"""

import json
import os
import subprocess
import sys
import time
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, redirect, url_for, flash

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_FILE = PROJECT_ROOT / "scraper.log"
RUNS_FILE = DATA_DIR / "admin_runs.json"
CONFIG_FILE = DATA_DIR / "admin_config.json"
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "audit_scrapers.py"

# ---------------------------------------------------------------------------
# Scraper registry
# ---------------------------------------------------------------------------

SCRAPERS = {
    "nyc": [
        {"key": "nyc",       "name": "NYC.gov Parks",       "emoji": "🏙"},
        {"key": "eventbrite","name": "Eventbrite NYC",       "emoji": "🎟"},
        {"key": "timeout",   "name": "TimeOut NY",           "emoji": "⏱"},
        {"key": "amnh",      "name": "AMNH",                 "emoji": "🦕"},
        {"key": "moma",      "name": "MoMA",                 "emoji": "🖼"},
        {"key": "whitney",   "name": "Whitney",              "emoji": "🎨"},
        {"key": "mcny",      "name": "MCNY",                 "emoji": "🗽"},
        {"key": "newmuseum", "name": "New Museum",           "emoji": "🏢"},
        {"key": "nyhistory", "name": "NY Historical Society","emoji": "📜"},
    ],
    "dc": [
        {"key": "nga",      "name": "NGA",                           "emoji": "🖼"},
        {"key": "hirshhorn","name": "Hirshhorn",                     "emoji": "🎨"},
        {"key": "nmnh",     "name": "NMNH",                          "emoji": "🦴"},
        {"key": "nmah",     "name": "NMAH",                          "emoji": "🇺🇸"},
        {"key": "nasm",     "name": "Air & Space",                   "emoji": "🚀"},
        {"key": "nmai",     "name": "American Indian",               "emoji": "🪶"},
        {"key": "nmaa",     "name": "Asian Art",                     "emoji": "🏯"},
        {"key": "nmaahc",   "name": "NMAAHC",                        "emoji": "✊"},
        {"key": "nbm",      "name": "Natl Building Museum",          "emoji": "🏗"},
        {"key": "spymuseum","name": "Spy Museum",                    "emoji": "🕵"},
        {"key": "saam",     "name": "SAAM",                          "emoji": "🎨"},
        {"key": "npm",      "name": "Postal Museum",                 "emoji": "📬"},
        {"key": "ushmm",    "name": "USHMM",                         "emoji": "🕯"},
        {"key": "nmwa",     "name": "Women in the Arts",             "emoji": "🎨"},
        {"key": "planetword","name": "Planet Word",                  "emoji": "📚"},
        {"key": "phillips", "name": "Phillips Collection",           "emoji": "🖼"},
        {"key": "nama",     "name": "Natl Mall & Memorial Parks",    "emoji": "🏛"},
    ],
    "paris": [
        {"key": "louvre",        "name": "Louvre",          "emoji": "🏛"},
        {"key": "orsay",         "name": "Orsay",           "emoji": "🖼"},
        {"key": "pompidou",      "name": "Pompidou",        "emoji": "🎨"},
        {"key": "fondationlv",   "name": "Fondation LV",    "emoji": "🌸"},
        {"key": "palaisdetokyo", "name": "Palais de Tokyo", "emoji": "🎞"},
        {"key": "museepicasso",  "name": "Musée Picasso",   "emoji": "🎭"},
    ],
}

# Flat lookup by key
SCRAPER_BY_KEY = {}
for city_scrapers in SCRAPERS.values():
    for s in city_scrapers:
        SCRAPER_BY_KEY[s["key"]] = s

# Source name → scraper key mapping (for event counting)
SOURCE_TO_KEY = {
    "NYC.gov Parks":                                         "nyc",
    "Eventbrite":                                            "eventbrite",
    "Museum of Modern Art":                                  "moma",
    "National Gallery of Art":                               "nga",
    "National Museum of the American Indian":                "nmai",
    "National Postal Museum":                                "npm",
    "US Holocaust Memorial Museum":                          "ushmm",
    "Musée Picasso Paris":                                   "museepicasso",
    "The Phillips Collection":                               "phillips",
    "Whitney Museum of American Art":                        "whitney",
    "Hirshhorn Museum":                                      "hirshhorn",
    "National Air and Space Museum":                         "nasm",
    "National Museum of African American History and Culture":"nmaahc",
    "National Museum of Asian Art":                          "nmaa",
    "National Museum of Women in the Arts":                  "nmwa",
    "Centre Pompidou":                                       "pompidou",
    "Jeu de Paume":                                          "palaisdetokyo",
    "National Mall & Memorial Parks":                        "nama",
    "National Museum of Natural History":                    "nmnh",
    "National Building Museum":                              "nbm",
    "Planet Word Museum":                                    "planetword",
    "American Museum of Natural History":                    "amnh",
    "International Spy Museum":                              "spymuseum",
    "National Museum of American History":                   "nmah",
    "Musée du Louvre":                                       "louvre",
    "Smithsonian American Art Museum":                       "saam",
    "Museum of the City of New York":                        "mcny",
    "New Museum":                                            "newmuseum",
    "New-York Historical Society":                           "nyhistory",
    "TimeOut NY":                                            "timeout",
    "Orsay":                                                 "orsay",
    "Fondation Louis Vuitton":                               "fondationlv",
}

# ---------------------------------------------------------------------------
# Global run state
# ---------------------------------------------------------------------------

_run_state = {
    "running": False,
    "source": None,
    "run_id": None,
    "start_time": None,
    "log_buffer": [],      # list of str lines — SSE clients read by offset
    "returncode": None,
    "_proc": None,
    "_lock": threading.Lock(),
}

_audit_state = {
    "running": False,
    "group": None,
    "log_buffer": [],
    "returncode": None,
    "_proc": None,
    "_lock": threading.Lock(),
}

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder=str(PROJECT_ROOT / "templates"))
app.secret_key = "tmc-admin-dev"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {"nps_api_key": "", "date_cap_days": 183}


def save_config(cfg):
    DATA_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def load_runs():
    if RUNS_FILE.exists():
        try:
            return json.loads(RUNS_FILE.read_text())
        except Exception:
            pass
    return []


def save_run(run_record):
    DATA_DIR.mkdir(exist_ok=True)
    runs = load_runs()
    runs.insert(0, run_record)
    runs = runs[:50]
    RUNS_FILE.write_text(json.dumps(runs, indent=2))


def time_ago(iso_str):
    if not iso_str:
        return "never"
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return iso_str


def get_event_counts():
    events_file = DATA_DIR / "events.json"
    counts = {}
    if events_file.exists():
        try:
            data = json.loads(events_file.read_text())
            events = data.get("events", [])
            for ev in events:
                src = ev.get("source", "")
                key = SOURCE_TO_KEY.get(src)
                if key:
                    counts[key] = counts.get(key, 0) + 1
        except Exception:
            pass
    return counts


def build_proc_env():
    cfg = load_config()
    env = os.environ.copy()
    api_key = cfg.get("nps_api_key", "")
    if api_key:
        env["NPS_API_KEY"] = api_key
    date_cap = cfg.get("date_cap_days", 183)
    env["DATE_CAP_DAYS"] = str(date_cap)
    return env


def _stream_proc(proc, state):
    """Read subprocess stdout/stderr into state['log_buffer'] and record returncode."""
    try:
        for line in iter(proc.stdout.readline, ""):
            stripped = line.rstrip("\n")
            if stripped:
                state["log_buffer"].append(stripped)
        proc.wait()
    except Exception as e:
        state["log_buffer"].append(f"[admin] stream error: {e}")
    finally:
        state["returncode"] = proc.returncode if proc.returncode is not None else proc.wait()


def _finish_run(run_id, source, start_time):
    """Called in background after run completes to persist run record."""
    # Wait briefly for returncode to be set
    for _ in range(60):
        if _run_state["returncode"] is not None:
            break
        time.sleep(0.5)
    rc = _run_state.get("returncode", -1)
    status = "success" if rc == 0 else "error"
    duration = time.time() - start_time
    save_run({
        "run_id": run_id,
        "source": source,
        "status": status,
        "returncode": rc,
        "started_at": datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
        "duration_secs": round(duration, 1),
        "log_lines": len(_run_state["log_buffer"]),
    })
    with _run_state["_lock"]:
        _run_state["running"] = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    counts = get_event_counts()
    runs = load_runs()
    last_run = runs[0] if runs else None
    total_events = sum(counts.values())
    active_scrapers = len([k for k, v in counts.items() if v > 0])
    last_run_ago = time_ago(last_run["started_at"]) if last_run else "never"
    last_run_status = last_run["status"] if last_run else "none"
    return render_template(
        "admin/dashboard.html",
        scrapers=SCRAPERS,
        scraper_by_key=SCRAPER_BY_KEY,
        counts=counts,
        runs=runs[:10],
        total_events=total_events,
        active_scrapers=active_scrapers,
        last_run_ago=last_run_ago,
        last_run_status=last_run_status,
        time_ago=time_ago,
    )


@app.route("/run")
def run_page():
    return render_template("admin/run.html", scrapers=SCRAPERS)


@app.route("/audit")
def audit_page():
    return render_template("admin/audit.html")


@app.route("/logs")
def logs_page():
    return render_template("admin/logs.html", log_file=str(LOG_FILE))


@app.route("/config", methods=["GET", "POST"])
def config_page():
    if request.method == "POST":
        cfg = load_config()
        cfg["nps_api_key"] = request.form.get("nps_api_key", "").strip()
        try:
            cfg["date_cap_days"] = int(request.form.get("date_cap_days", 183))
        except ValueError:
            cfg["date_cap_days"] = 183
        save_config(cfg)
        flash("Configuration saved.", "success")
        return redirect(url_for("config_page"))
    cfg = load_config()
    return render_template("admin/config.html", config=cfg)


# ---------------------------------------------------------------------------
# API: Run
# ---------------------------------------------------------------------------

@app.route("/api/run", methods=["POST"])
def api_run():
    with _run_state["_lock"]:
        if _run_state["running"]:
            return jsonify({"error": "already running"}), 409
        _run_state["running"] = True
        _run_state["returncode"] = None
        _run_state["log_buffer"] = []

    data = request.get_json(silent=True) or request.form
    source = data.get("source", "all")
    dry_run = str(data.get("dry_run", "false")).lower() in ("true", "1", "yes", "on")

    cmd = [sys.executable, str(PROJECT_ROOT / "scrape.py")]
    if source and source != "all":
        cmd += ["--source", source]
    if dry_run:
        cmd += ["--dry-run"]

    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    with _run_state["_lock"]:
        _run_state["source"] = source
        _run_state["run_id"] = run_id
        _run_state["start_time"] = start_time

    env = build_proc_env()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
    except Exception as e:
        with _run_state["_lock"]:
            _run_state["running"] = False
        return jsonify({"error": str(e)}), 500

    _run_state["_proc"] = proc

    def reader():
        _stream_proc(proc, _run_state)
        _finish_run(run_id, source, start_time)

    threading.Thread(target=reader, daemon=True).start()

    return jsonify({"run_id": run_id, "status": "started", "source": source})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    proc = _run_state.get("_proc")
    if proc and proc.poll() is None:
        proc.terminate()
        return jsonify({"status": "terminated"})
    return jsonify({"status": "not running"})


@app.route("/api/status")
def api_status():
    return jsonify({
        "running": _run_state["running"],
        "source": _run_state["source"],
        "run_id": _run_state["run_id"],
        "log_length": len(_run_state["log_buffer"]),
        "returncode": _run_state["returncode"],
    })


@app.route("/api/stream")
def api_stream():
    target = request.args.get("target", "run")
    offset = int(request.args.get("offset", 0))
    state = _run_state if target == "run" else _audit_state

    def generate():
        idx = offset
        while True:
            buf = state["log_buffer"]
            if idx < len(buf):
                chunk = buf[idx:]
                for line in chunk:
                    ts = datetime.now().strftime("%H:%M:%S")
                    payload = json.dumps({"ts": ts, "line": line})
                    yield f"data: {payload}\n\n"
                idx += len(chunk)
            # Check if done
            if not state["running"] and state["returncode"] is not None and idx >= len(state["log_buffer"]):
                yield f"data: {json.dumps({'__end__': True, 'returncode': state['returncode']})}\n\n"
                break
            time.sleep(0.15)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# API: Audit
# ---------------------------------------------------------------------------

@app.route("/api/audit", methods=["POST"])
def api_audit():
    with _audit_state["_lock"]:
        if _audit_state["running"]:
            return jsonify({"error": "already running"}), 409
        _audit_state["running"] = True
        _audit_state["returncode"] = None
        _audit_state["log_buffer"] = []

    data = request.get_json(silent=True) or request.form
    group = data.get("group", "all")
    _audit_state["group"] = group

    cmd = [sys.executable, str(AUDIT_SCRIPT)]
    if group and group != "all":
        cmd += ["--group", group]

    env = build_proc_env()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
    except Exception as e:
        with _audit_state["_lock"]:
            _audit_state["running"] = False
        return jsonify({"error": str(e)}), 500

    _audit_state["_proc"] = proc

    def reader():
        _stream_proc(proc, _audit_state)
        with _audit_state["_lock"]:
            _audit_state["running"] = False

    threading.Thread(target=reader, daemon=True).start()
    return jsonify({"status": "started", "group": group})


@app.route("/api/audit/status")
def api_audit_status():
    return jsonify({
        "running": _audit_state["running"],
        "group": _audit_state["group"],
        "log_length": len(_audit_state["log_buffer"]),
        "returncode": _audit_state["returncode"],
    })


@app.route("/api/stop/audit", methods=["POST"])
def api_stop_audit():
    proc = _audit_state.get("_proc")
    if proc and proc.poll() is None:
        proc.terminate()
        return jsonify({"status": "terminated"})
    return jsonify({"status": "not running"})


# ---------------------------------------------------------------------------
# API: Runs history
# ---------------------------------------------------------------------------

@app.route("/api/runs")
def api_runs():
    runs = load_runs()[:20]
    return jsonify(runs)


# ---------------------------------------------------------------------------
# API: Logs
# ---------------------------------------------------------------------------

@app.route("/api/logs")
def api_logs():
    n = request.args.get("lines", "200")
    try:
        n = int(n)
    except ValueError:
        n = 200

    if not LOG_FILE.exists():
        return jsonify({"lines": [], "file": str(LOG_FILE), "size": 0, "exists": False})

    stat = LOG_FILE.stat()
    all_lines = LOG_FILE.read_text(errors="replace").splitlines()
    if n > 0:
        lines = all_lines[-n:]
    else:
        lines = all_lines

    return jsonify({
        "lines": lines,
        "total_lines": len(all_lines),
        "file": str(LOG_FILE),
        "size": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "exists": True,
    })


# ---------------------------------------------------------------------------
# API: Config danger zone
# ---------------------------------------------------------------------------

@app.route("/api/config/clear-history", methods=["POST"])
def api_clear_history():
    if RUNS_FILE.exists():
        RUNS_FILE.write_text("[]")
    return jsonify({"status": "cleared"})


@app.route("/api/config/clear-log", methods=["POST"])
def api_clear_log():
    if LOG_FILE.exists():
        LOG_FILE.write_text("")
    return jsonify({"status": "cleared"})


# ---------------------------------------------------------------------------
# API: Dashboard data
# ---------------------------------------------------------------------------

@app.route("/api/dashboard")
def api_dashboard():
    counts = get_event_counts()
    runs = load_runs()
    last_run = runs[0] if runs else None
    return jsonify({
        "counts": counts,
        "total_events": sum(counts.values()),
        "active_scrapers": len([k for k, v in counts.items() if v > 0]),
        "last_run": last_run,
        "running": _run_state["running"],
    })


# ---------------------------------------------------------------------------
# Template context processor
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    return {
        "is_running": _run_state["running"],
        "run_source": _run_state["source"],
    }


if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    app.run(host="0.0.0.0", port=5002, debug=False, threaded=True)
