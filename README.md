# 🎭 TMC Cultural Calendar

A full-stack web application that scrapes and aggregates cultural events from world-class museums and institutions across **New York City**, **Washington DC**, and **Paris** — presented in an editorial-style calendar.

![TMC Cultural Calendar](https://img.shields.io/badge/TMC-Cultural%20Calendar-gold?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square)
![Flask](https://img.shields.io/badge/Flask-3.0-green?style=flat-square)

---

## 📡 Data Sources

### 🗽 New York City
| Source | Description |
|--------|-------------|
| **NYC.gov Parks** | Free events from NYC Parks & Cultural Affairs |
| **Eventbrite NYC** | Arts, music, festivals, and community events |
| **TimeOut New York** | Curated picks — art shows, concerts, theater, dance |
| **The Met** | Metropolitan Museum of Art |
| **MoMA** | Museum of Modern Art |
| **Whitney Museum** | Whitney Museum of American Art |
| **AMNH** | American Museum of Natural History |
| **Museum of the City of NY** | MCNY |
| **New Museum** | Contemporary art |
| **NY Historical Society** | New-York Historical Society |

### 🏛 Washington DC
| Source | Description |
|--------|-------------|
| **National Gallery of Art** | NGA |
| **Hirshhorn Museum** | Hirshhorn Museum and Sculpture Garden |
| **Smithsonian NMNH** | National Museum of Natural History |
| **Smithsonian NMAH** | National Museum of American History |
| **Air and Space Museum** | National Air and Space Museum |
| **American Indian Museum** | National Museum of the American Indian |
| **National Museum of Asian Art** | Freer \| Sackler |
| **NMAAHC** | National Museum of African American History and Culture |
| **National Building Museum** | NBM |
| **International Spy Museum** | SpyMuseum.org |
| **Smithsonian American Art Museum** | SAAM |
| **National Postal Museum** | NPM |
| **US Holocaust Memorial Museum** | USHMM |
| **National Museum of Women in the Arts** | NMWA |
| **Planet Word Museum** | Planet Word |

### 🗼 Paris
| Source | Description |
|--------|-------------|
| **Louvre** | Musée du Louvre |
| **Musée d'Orsay** | Orsay |
| **Centre Pompidou** | Pompidou |
| **Fondation Louis Vuitton** | FLV |
| **Palais de Tokyo** | Palais de Tokyo |
| **Musée Picasso** | Musée Picasso Paris |

---

## ✨ Features

- **Multi-city, multi-source scraper** — 31 institutions across 3 cities
- **Smart consolidation** — deduplication, normalization, tag generation
- **Interactive calendar** — month-by-month view with click-to-expand popovers
- **Event management** — add, edit, delete, and feature events via admin UI
- **Advanced filtering** — by category, source, neighborhood, date range, free-only
- **Audit tool** — `scripts/audit_scrapers.py` validates each scraper's output
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
python scrape.py                    # Scrape all sources (all cities)
python scrape.py --city nyc         # Only NYC sources
python scrape.py --city dc          # Only DC sources
python scrape.py --city paris       # Only Paris sources
python scrape.py --source nga       # Single institution
python scrape.py --source planetword
python scrape.py --source nmwa
```

### 3. Audit scrapers

```bash
python scripts/audit_scrapers.py            # Audit all
python scripts/audit_scrapers.py --group dc # Audit DC only
```

### 4. Start the web app

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
│   ├── # NYC
│   ├── nyc_gov_scraper.py
│   ├── eventbrite_scraper.py
│   ├── timeout_scraper.py
│   ├── amnh_scraper.py
│   ├── moma_scraper.py
│   ├── whitney_scraper.py
│   ├── mcny_scraper.py
│   ├── newmuseum_scraper.py
│   ├── nyhistory_scraper.py
│   ├── # DC
│   ├── nga_scraper.py
│   ├── hirshhorn_scraper.py
│   ├── nmnh_scraper.py
│   ├── nmah_scraper.py
│   ├── nasm_scraper.py
│   ├── nmai_scraper.py
│   ├── nmaa_scraper.py
│   ├── nmaahc_scraper.py
│   ├── nbm_scraper.py
│   ├── spymuseum_scraper.py
│   ├── saam_scraper.py
│   ├── npm_scraper.py
│   ├── ushmm_scraper.py
│   ├── nmwa_scraper.py
│   ├── planetword_scraper.py
│   ├── # Paris
│   ├── louvre_scraper.py
│   ├── orsay_scraper.py
│   ├── pompidou_scraper.py
│   ├── fondationlv_scraper.py
│   ├── palaisdetokyo_scraper.py
│   └── museepicasso_scraper.py
├── scripts/
│   └── audit_scrapers.py   # Scraper health audit tool
├── templates/
│   ├── base.html           # Shared layout
│   ├── index.html          # Homepage
│   ├── dc.html             # Washington DC city page
│   ├── paris.html          # Paris city page
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

MIT — built for TMC Cultural Calendar.
