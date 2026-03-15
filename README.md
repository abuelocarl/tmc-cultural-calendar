# 🎭 TMC Cultural Calendar

A full-stack web application that scrapes and aggregates cultural events across New York City from multiple sources, presenting them in a beautiful editorial-style calendar and management interface.

![TMC Cultural Calendar](https://img.shields.io/badge/TMC-Cultural%20Calendar-gold?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square)
![Flask](https://img.shields.io/badge/Flask-3.0-green?style=flat-square)

---

## 📡 Data Sources

| Source | Description |
|--------|-------------|
| **NYC.gov Parks** | Free events from NYC Parks & Cultural Affairs |
| **Eventbrite NYC** | Arts, music, festivals, and community events |
| **TimeOut New York** | Curated picks — art shows, concerts, theater, dance |

---

## ✨ Features

- **Multi-source scraper** — pulls events from NYC.gov, Eventbrite, and TimeOut NY
- **Interactive calendar** — month-by-month view with click-to-expand event popovers
- **Smart consolidation** — deduplication, normalization, borough detection, tag generation
- **Event management** — add, edit, delete, and feature events via admin UI
- **Advanced filtering** — by category, source, borough, date range, free-only
- **REST API** — JSON endpoints for events, stats, and scrape triggers
- **Beautiful design** — editorial aesthetic with Playfair Display + Space Mono typography

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/abuelocarl/tmc-cultural-calendar.git
cd tmc-cultural-calendar
pip install -r requirements.txt
```

### 2. Run the scraper

```bash
python scrape.py                    # Scrape all sources
python scrape.py --source nyc       # Only NYC.gov
python scrape.py --source eventbrite
python scrape.py --source timeout
```

### 3. Start the web app

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) 🎉

---

## 📁 Project Structure

```
tmc-cultural-calendar/
├── scrape.py               # Main scraper runner (CLI)
├── app.py                  # Flask web application
├── consolidator.py         # Event normalization & data management
├── requirements.txt
├── scrapers/
│   ├── __init__.py
│   ├── nyc_gov_scraper.py  # NYC.gov Parks & Cultural Affairs
│   ├── eventbrite_scraper.py
│   └── timeout_scraper.py
├── templates/
│   ├── base.html           # Shared layout
│   ├── index.html          # Homepage with featured events
│   ├── events.html         # Filterable event list
│   ├── calendar.html       # Interactive monthly calendar
│   ├── event_detail.html   # Single event detail page
│   ├── admin.html          # Event management dashboard
│   └── event_form.html     # Add/edit event form
├── static/
│   ├── css/style.css       # Editorial design system
│   └── js/app.js           # Calendar logic & interactions
└── data/
    └── events.json         # Consolidated events (auto-generated)
```

---

## 🌐 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/events` | All events (supports filters: `q`, `category`, `source`, `borough`, `date_from`, `date_to`, `free_only`) |
| `GET /api/events/<id>` | Single event by ID |
| `GET /api/stats` | Counts by source, category, borough |
| `POST /api/scrape` | Trigger scrape run `{"source": "all"}` |

---

## 🔄 Automating Scrapes

To keep events fresh, schedule `scrape.py` with cron:

```bash
# Scrape every morning at 7am
0 7 * * * cd /path/to/tmc-cultural-calendar && python scrape.py >> logs/cron.log 2>&1
```

---

## 🛠 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | dev secret | Flask session secret |
| `PORT` | `5000` | Web server port |
| `FLASK_DEBUG` | `1` | Debug mode (set `0` in production) |

---

## 📄 License

MIT — built for TMC Cultural Calendar, New York City.
