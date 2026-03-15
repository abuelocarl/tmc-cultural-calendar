/**
 * TMC Cultural Calendar — Webflow / Static Client-Side App
 *
 * To use with a remote API, set window.TMC_API_URL before loading this script:
 *   <script>window.TMC_API_URL = 'https://your-flask-server.com';</script>
 *
 * Default: same origin (Flask app serves both API and static files).
 */

// ── Config ────────────────────────────────────────────────────────────────────
const TMC = {
  apiBase: (window.TMC_API_URL || '').replace(/\/$/, ''),

  catIcons: {
    'Arts & Culture': '🎨', 'Music': '🎵', 'Theater': '🎭', 'Dance': '💃',
    'Festivals': '🎉', 'Parks & Recreation': '🌿', 'Heritage & History': '🏛',
    'Community': '🤝', 'Weekend Picks': '⭐', 'Other': '📌',
  },

  catColors: {
    'Arts & Culture': '#e63946', 'Music': '#2a9d8f', 'Theater': '#9b59b6',
    'Dance': '#e76f51', 'Festivals': '#f4a261', 'Parks & Recreation': '#2d6a4f',
    'Heritage & History': '#8b6914', 'Community': '#457b9d',
    'Weekend Picks': '#c0392b', 'Other': '#666',
  },

  allCategories: [
    'Arts & Culture', 'Music', 'Theater', 'Dance', 'Festivals',
    'Parks & Recreation', 'Heritage & History', 'Community', 'Weekend Picks', 'Other',
  ],

  allBoroughs: ['Manhattan', 'Brooklyn', 'Queens', 'The Bronx', 'Staten Island'],

  // ── Helpers ──
  esc(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },

  eventUrl(id) {
    return `event.html?id=${encodeURIComponent(id)}`;
  },

  // ── API ──
  async fetch(path) {
    const res = await fetch(this.apiBase + path);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  // ── Card Templates ──
  tag(text, cls) {
    return `<span class="tag ${cls}">${this.esc(text)}</span>`;
  },

  eventCardHtml(ev) {
    return `
<article class="event-card">
  <div class="event-card-header">
    <div class="event-card-tags">
      ${this.tag(ev.source || 'Unknown', 'tag-source')}
      ${ev.is_free ? this.tag('FREE', 'tag-free') : ''}
    </div>
    ${ev.borough ? `<span class="event-borough">${this.esc(ev.borough)}</span>` : ''}
  </div>
  <h3 class="event-card-title">
    <a href="${this.eventUrl(ev.id)}">${this.esc(ev.title)}</a>
  </h3>
  <div class="event-card-meta">
    <span class="event-category">${this.esc(ev.category || '')}</span>
  </div>
  <div class="event-card-details">
    ${ev.date ? `<div class="event-detail-row"><span class="detail-icon">📅</span><span>${this.esc(ev.date)}${ev.time ? ' · ' + this.esc(ev.time) : ''}</span></div>` : ''}
    ${ev.location ? `<div class="event-detail-row"><span class="detail-icon">📍</span><span>${this.esc(ev.location.substring(0, 50))}</span></div>` : ''}
    ${ev.price ? `<div class="event-detail-row"><span class="detail-icon">🎟</span><span>${this.esc(ev.price)}</span></div>` : ''}
  </div>
  ${ev.description ? `<p class="event-card-desc">${this.esc(ev.description.substring(0, 120))}…</p>` : ''}
  <div class="event-card-footer">
    <a href="${this.eventUrl(ev.id)}" class="event-card-cta">Details →</a>
    ${ev.url ? `<a href="${this.esc(ev.url)}" target="_blank" rel="noopener" class="event-card-ext">↗</a>` : ''}
  </div>
</article>`;
  },

  featuredCardHtml(ev, isLarge) {
    const bgStyle = ev.image_url ? `background-image:url(${this.esc(ev.image_url)})` : '';
    return `
<article class="featured-card ${isLarge ? 'featured-card--large' : ''}">
  <div class="featured-card-bg" style="${bgStyle}"></div>
  <div class="featured-card-overlay"></div>
  <div class="featured-card-body">
    <div class="featured-card-meta">
      ${this.tag(ev.source || 'Unknown', 'tag-source')}
      ${this.tag(ev.category || 'Other', 'tag-category')}
      ${ev.is_free ? this.tag('FREE', 'tag-free') : ''}
    </div>
    <h3 class="featured-card-title">
      <a href="${this.eventUrl(ev.id)}">${this.esc(ev.title)}</a>
    </h3>
    <div class="featured-card-info">
      ${ev.date ? `<span class="event-date">📅 ${this.esc(ev.date)}</span>` : ''}
      ${ev.location ? `<span class="event-loc">📍 ${this.esc(ev.location.substring(0, 40))}</span>` : ''}
    </div>
  </div>
</article>`;
  },
};


// ── PAGE: Index ───────────────────────────────────────────────────────────────
async function initIndexPage() {
  // Hero stats
  TMC.fetch('/api/stats').then(stats => {
    const el = document.getElementById('stat-total');
    const el2 = document.getElementById('stat-sources');
    if (el) el.textContent = stats.total_events ?? '—';
    if (el2) el2.textContent = Object.keys(stats.sources || {}).length || '—';
  }).catch(() => {});

  try {
    const data = await TMC.fetch('/api/events');
    const events = data.events || [];
    const today = new Date().toISOString().split('T')[0];
    const upcoming = events.filter(e => !e.date || e.date >= today);

    // Featured
    let featured = upcoming.filter(e => e.is_featured).slice(0, 3);
    if (featured.length < 3) featured = upcoming.slice(0, 3);

    const featuredSection = document.getElementById('featured-section');
    const featuredGrid = document.getElementById('featured-grid');
    if (featuredGrid && featured.length) {
      featuredGrid.innerHTML = featured.map((ev, i) => TMC.featuredCardHtml(ev, i === 0)).join('');
      if (featuredSection) featuredSection.style.display = '';
    }

    // Upcoming grid
    const eventsGrid = document.getElementById('events-grid');
    if (eventsGrid) {
      const toShow = upcoming.slice(0, 24);
      eventsGrid.innerHTML = toShow.length
        ? toShow.map(ev => TMC.eventCardHtml(ev)).join('')
        : `<div class="empty-state"><div class="empty-icon">🎭</div><h3>No events found</h3><p>Run a scrape to pull the latest events.</p></div>`;
    }

    const countEl = document.getElementById('events-total-count');
    if (countEl) countEl.textContent = data.total;

    // Categories
    const categoryCounts = {};
    events.forEach(ev => {
      const c = ev.category || 'Other';
      categoryCounts[c] = (categoryCounts[c] || 0) + 1;
    });
    const catsGrid = document.getElementById('categories-grid');
    if (catsGrid) {
      const cats = Object.keys(categoryCounts).sort();
      catsGrid.innerHTML = cats.map(cat => `
<a href="events.html?category=${encodeURIComponent(cat)}" class="category-card">
  <span class="category-icon">${TMC.catIcons[cat] || '📌'}</span>
  <span class="category-name">${TMC.esc(cat)}</span>
  <span class="category-count">${categoryCounts[cat]}</span>
</a>`).join('');
    }

    // Boroughs
    const boroughCounts = {};
    events.forEach(ev => {
      if (ev.borough) boroughCounts[ev.borough] = (boroughCounts[ev.borough] || 0) + 1;
    });
    const boroughsGrid = document.getElementById('boroughs-grid');
    if (boroughsGrid) {
      boroughsGrid.innerHTML = TMC.allBoroughs.map(b => {
        const count = boroughCounts[b] || 0;
        return `
<a href="events.html?borough=${encodeURIComponent(b)}" class="borough-card">
  <span class="borough-name">${TMC.esc(b)}</span>
  <span class="borough-count">${count} event${count !== 1 ? 's' : ''}</span>
</a>`;
      }).join('');
    }

    animateCards();
  } catch (err) {
    console.error('Failed to load events:', err);
    const eventsGrid = document.getElementById('events-grid');
    if (eventsGrid) {
      eventsGrid.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><h3>Could not load events</h3><p>Make sure the API server is running.</p></div>`;
    }
  }
}


// ── PAGE: Events List ─────────────────────────────────────────────────────────
const PER_PAGE = 24;
let _eventsAll = [];
let _eventsPage = 1;

async function initEventsPage() {
  const params = new URLSearchParams(window.location.search);
  _eventsPage = parseInt(params.get('page') || '1');

  // Pre-fill filters from URL
  ['q', 'category', 'source', 'borough', 'date_from', 'date_to'].forEach(k => {
    const el = document.getElementById(`filter-${k}`);
    if (el && params.has(k)) el.value = params.get(k);
  });
  const freeEl = document.getElementById('filter-free_only');
  if (freeEl && params.get('free_only') === '1') freeEl.checked = true;

  // Build API query from URL params
  const apiQ = new URLSearchParams();
  ['q', 'category', 'source', 'borough', 'date_from', 'date_to', 'free_only'].forEach(k => {
    if (params.has(k)) apiQ.set(k, params.get(k));
  });

  const countEl = document.getElementById('results-count');
  if (countEl) countEl.textContent = 'Loading…';

  try {
    const data = await TMC.fetch('/api/events?' + apiQ.toString());
    _eventsAll = data.events || [];

    // Populate dynamic source options
    const sourceEl = document.getElementById('filter-source');
    if (sourceEl && sourceEl.options.length <= 1) {
      const sources = [...new Set(_eventsAll.map(e => e.source).filter(Boolean))].sort();
      sources.forEach(s => {
        const opt = new Option(s, s);
        if (params.get('source') === s) opt.selected = true;
        sourceEl.appendChild(opt);
      });
    }

    renderEventsPage();
    animateCards();
  } catch (err) {
    console.error('Failed to load events:', err);
    const grid = document.getElementById('events-grid');
    if (grid) grid.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><h3>Could not load events</h3><p>Make sure the API server is running.</p></div>`;
  }
}

function renderEventsPage() {
  const total = _eventsAll.length;
  const totalPages = Math.ceil(total / PER_PAGE);
  const start = (_eventsPage - 1) * PER_PAGE;
  const paginated = _eventsAll.slice(start, start + PER_PAGE);

  const countEl = document.getElementById('results-count');
  if (countEl) countEl.textContent = `${total} event${total !== 1 ? 's' : ''} found`;

  const grid = document.getElementById('events-grid');
  if (grid) {
    grid.innerHTML = paginated.length
      ? paginated.map(ev => TMC.eventCardHtml(ev)).join('')
      : `<div class="empty-state"><div class="empty-icon">🔍</div><h3>No events match your filters</h3><p>Try adjusting your search criteria.</p><a href="events.html" class="btn-primary">View All Events</a></div>`;
  }

  renderPagination(totalPages);
}

function renderPagination(totalPages) {
  const pag = document.getElementById('pagination');
  if (!pag) return;
  if (totalPages <= 1) { pag.innerHTML = ''; return; }

  const params = new URLSearchParams(window.location.search);
  const makeUrl = p => { const q = new URLSearchParams(params); q.set('page', p); return 'events.html?' + q.toString(); };

  let html = '';
  if (_eventsPage > 1) html += `<a href="${makeUrl(_eventsPage - 1)}" class="page-btn">← Prev</a>`;

  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || Math.abs(i - _eventsPage) <= 2) {
      html += `<a href="${makeUrl(i)}" class="page-btn ${i === _eventsPage ? 'page-btn-active' : ''}">${i}</a>`;
    } else if (Math.abs(i - _eventsPage) === 3) {
      html += `<span class="page-dots">…</span>`;
    }
  }

  if (_eventsPage < totalPages) html += `<a href="${makeUrl(_eventsPage + 1)}" class="page-btn">Next →</a>`;
  pag.innerHTML = html;
}

// Grid/List toggle (events page)
function setView(mode) {
  const container = document.getElementById('events-grid');
  const gridBtn = document.getElementById('grid-view-btn');
  const listBtn = document.getElementById('list-view-btn');
  if (!container) return;
  if (mode === 'list') {
    container.classList.remove('events-grid');
    container.classList.add('events-list-view');
    gridBtn?.classList.remove('active');
    listBtn?.classList.add('active');
  } else {
    container.classList.add('events-grid');
    container.classList.remove('events-list-view');
    gridBtn?.classList.add('active');
    listBtn?.classList.remove('active');
  }
  localStorage.setItem('tmc-view-mode', mode);
}


// ── PAGE: Calendar ────────────────────────────────────────────────────────────
async function initCalendarPage() {
  try {
    const params = new URLSearchParams(window.location.search);
    const apiQ = new URLSearchParams();
    ['q', 'category', 'source'].forEach(k => {
      if (params.has(k)) apiQ.set(k, params.get(k));
    });

    // Pre-fill filter form
    ['q', 'category', 'source'].forEach(k => {
      const el = document.getElementById(`cal-filter-${k}`);
      if (el && params.has(k)) el.value = params.get(k);
    });

    const data = await TMC.fetch('/api/events?' + apiQ.toString());
    window.TMC_EVENTS = data.events || [];

    initCalendar();
    renderUpcomingList(window.TMC_EVENTS);
    renderCalLegend(window.TMC_EVENTS);
  } catch (err) {
    console.error('Failed to load calendar events:', err);
  }
}

function renderUpcomingList(events) {
  const list = document.getElementById('upcoming-list');
  if (!list) return;
  const today = new Date().toISOString().split('T')[0];
  const upcoming = events
    .filter(e => !e.date || e.date >= today)
    .sort((a, b) => (a.date || '').localeCompare(b.date || ''))
    .slice(0, 30);

  if (!upcoming.length) {
    list.innerHTML = `<p class="empty-state-sm">No upcoming events. <a href="calendar.html">Clear filters</a></p>`;
    return;
  }

  list.innerHTML = `<div class="event-list-table">${upcoming.map(ev => `
<a href="${TMC.eventUrl(ev.id)}" class="event-row">
  <span class="event-row-date">${TMC.esc(ev.date || '')}</span>
  <span class="event-row-title">${TMC.esc(ev.title)}</span>
  <span class="event-row-cat">${TMC.esc(ev.category || '')}</span>
  <span class="event-row-loc">${TMC.esc((ev.location || '').substring(0, 35))}</span>
  ${ev.is_free ? TMC.tag('FREE', 'tag-free tag-sm') : ''}
</a>`).join('')}</div>`;
}

function renderCalLegend(events) {
  const legendEl = document.getElementById('cal-legend');
  if (!legendEl) return;
  const cats = [...new Set(events.map(e => e.category).filter(Boolean))].sort();
  legendEl.innerHTML = cats.map(cat => `
<div class="legend-item">
  <span class="legend-dot" style="background:${TMC.catColors[cat] || '#666'}"></span>
  <span>${TMC.esc(cat)}</span>
</div>`).join('');
}


// ── PAGE: Event Detail ────────────────────────────────────────────────────────
async function initEventDetailPage() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get('id');

  const section = document.getElementById('event-detail-section');
  if (!id || !section) {
    if (section) section.innerHTML = `<div class="empty-state"><div class="empty-icon">😕</div><h3>No event specified</h3><p><a href="index.html">← Back to Home</a></p></div>`;
    return;
  }

  try {
    const event = await TMC.fetch(`/api/events/${encodeURIComponent(id)}`);
    document.title = `${event.title} | TMC Cultural Calendar`;

    // Breadcrumb
    const crumb = document.getElementById('event-breadcrumb');
    if (crumb) {
      crumb.innerHTML = `<a href="index.html">Home</a> / <a href="events.html">Events</a> / <span>${TMC.esc(event.title.substring(0, 50))}</span>`;
    }

    // Tags
    const tags = [
      event.source ? TMC.tag(event.source, 'tag-source tag-lg') : '',
      event.category ? TMC.tag(event.category, 'tag-category tag-lg') : '',
      event.is_free ? TMC.tag('FREE', 'tag-free tag-lg') : '',
      event.is_featured ? TMC.tag('⭐ Featured', 'tag-featured tag-lg') : '',
    ].filter(Boolean).join('');

    const tagsEl = document.getElementById('event-detail-tags');
    if (tagsEl) tagsEl.innerHTML = tags;

    // Title
    const titleEl = document.getElementById('event-detail-title');
    if (titleEl) titleEl.textContent = event.title;

    // Description
    const descEl = document.getElementById('event-detail-desc');
    if (descEl) {
      if (event.description) { descEl.textContent = event.description; descEl.style.display = ''; }
      else descEl.style.display = 'none';
    }

    // Event tags
    const tagsListEl = document.getElementById('event-detail-tags-list');
    if (tagsListEl) {
      if (event.tags && event.tags.length) {
        tagsListEl.innerHTML = event.tags.map(t => `<a href="events.html?tag=${encodeURIComponent(t)}" class="event-tag">#${TMC.esc(t)}</a>`).join('');
        tagsListEl.style.display = '';
      } else tagsListEl.style.display = 'none';
    }

    // Actions
    const actionsEl = document.getElementById('event-detail-actions');
    if (actionsEl) {
      actionsEl.innerHTML = [
        event.url ? `<a href="${TMC.esc(event.url)}" target="_blank" rel="noopener" class="btn-primary">View Original Event ↗</a>` : '',
        `<a href="events.html" class="btn-ghost">← Back to Events</a>`,
      ].join('');
    }

    // Sidebar
    const sidebar = document.getElementById('event-detail-sidebar');
    if (sidebar) {
      const items = [
        event.date ? `<div class="detail-item"><span class="detail-item-icon">📅</span><div><strong>Date</strong><p>${TMC.esc(event.date)}${event.end_date && event.end_date !== event.date ? ' – ' + TMC.esc(event.end_date) : ''}</p></div></div>` : '',
        event.time ? `<div class="detail-item"><span class="detail-item-icon">🕐</span><div><strong>Time</strong><p>${TMC.esc(event.time)}</p></div></div>` : '',
        event.location ? `<div class="detail-item"><span class="detail-item-icon">📍</span><div><strong>Location</strong><p>${TMC.esc(event.location)}</p>${event.borough ? `<p class="borough-badge">${TMC.esc(event.borough)}</p>` : ''}</div></div>` : '',
        event.price ? `<div class="detail-item"><span class="detail-item-icon">🎟</span><div><strong>Price</strong><p>${TMC.esc(event.price)}</p></div></div>` : '',
        `<div class="detail-item"><span class="detail-item-icon">🔗</span><div><strong>Source</strong><p>${TMC.esc(event.source || '')}</p></div></div>`,
      ].filter(Boolean).join('');
      sidebar.innerHTML = `<div class="detail-card"><h3 class="detail-card-title">Event Details</h3>${items}</div>`;
    }

    // Related events
    if (event.category) {
      TMC.fetch(`/api/events?category=${encodeURIComponent(event.category)}`).then(data => {
        const related = (data.events || []).filter(e => e.id !== id).slice(0, 4);
        const relSection = document.getElementById('related-section');
        const relGrid = document.getElementById('related-events-grid');
        if (related.length && relGrid) {
          relGrid.innerHTML = related.map(ev => TMC.eventCardHtml(ev)).join('');
          if (relSection) relSection.style.display = '';
          animateCards();
        }
      }).catch(() => {});
    }

  } catch (err) {
    section.innerHTML = `<div class="empty-state"><div class="empty-icon">😕</div><h3>Event not found</h3><p><a href="index.html">← Back to Home</a></p></div>`;
  }
}


// ── Calendar Logic ────────────────────────────────────────────────────────────
function initCalendar() {
  const grid = document.getElementById('calendar-grid');
  if (!grid) return;

  const events = window.TMC_EVENTS || [];
  const eventsByDate = {};
  events.forEach(ev => {
    if (ev.date) (eventsByDate[ev.date] = eventsByDate[ev.date] || []).push(ev);
  });

  const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];

  const today = new Date();
  let currentYear = today.getFullYear();
  let currentMonth = today.getMonth();

  function renderCalendar(year, month) {
    const label = document.getElementById('month-label');
    if (label) label.textContent = `${MONTHS[month]} ${year}`;
    grid.innerHTML = '';

    DAYS.forEach(d => {
      const el = document.createElement('div');
      el.className = 'cal-day-header';
      el.textContent = d;
      grid.appendChild(el);
    });

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const daysInPrev = new Date(year, month, 0).getDate();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    const cells = [];
    for (let i = firstDay - 1; i >= 0; i--) cells.push({ day: daysInPrev - i, month: month - 1, year, other: true });
    for (let d = 1; d <= daysInMonth; d++) cells.push({ day: d, month, year, other: false });
    const remaining = 42 - cells.length;
    for (let d = 1; d <= remaining; d++) cells.push({ day: d, month: month + 1, year, other: true });

    cells.forEach(cell => {
      const m = ((cell.month % 12) + 12) % 12;
      const y = cell.year + Math.floor(cell.month / 12);
      const dateStr = `${y}-${String(m + 1).padStart(2, '0')}-${String(cell.day).padStart(2, '0')}`;
      const dayEvents = eventsByDate[dateStr] || [];

      const el = document.createElement('div');
      el.className = 'cal-day';
      if (cell.other) el.classList.add('cal-day--other-month');
      if (dateStr === todayStr) el.classList.add('cal-day--today');
      if (dayEvents.length > 0) el.classList.add('cal-day--has-events');

      const numEl = document.createElement('div');
      numEl.className = 'cal-day-num';
      numEl.textContent = cell.day;
      el.appendChild(numEl);

      dayEvents.slice(0, 3).forEach(ev => {
        const dot = document.createElement('span');
        dot.className = 'cal-event-dot';
        dot.textContent = ev.title.substring(0, 18) + (ev.title.length > 18 ? '…' : '');
        dot.style.background = TMC.catColors[ev.category] || '#2d4a66';
        dot.style.color = '#fff';
        el.appendChild(dot);
      });

      if (dayEvents.length > 3) {
        const more = document.createElement('div');
        more.className = 'cal-event-more';
        more.textContent = `+${dayEvents.length - 3} more`;
        el.appendChild(more);
      }

      if (dayEvents.length > 0) {
        el.addEventListener('click', e => showPopover(e, dateStr, dayEvents));
      }

      grid.appendChild(el);
    });
  }

  function showPopover(e, dateStr, dayEvents) {
    const popover = document.getElementById('event-popover');
    const dateLabel = document.getElementById('popover-date');
    const eventsContainer = document.getElementById('popover-events');
    if (!popover) return;

    if (dateLabel) {
      dateLabel.textContent = new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      });
    }

    if (eventsContainer) {
      eventsContainer.innerHTML = dayEvents.map(ev => `
<div class="popover-event-item">
  <div class="popover-event-title"><a href="${TMC.eventUrl(ev.id)}">${TMC.esc(ev.title)}</a></div>
  <div class="popover-event-meta">${TMC.esc(ev.category || '')} · ${TMC.esc(ev.source || '')}${ev.location ? ' · ' + TMC.esc(ev.location.substring(0, 30)) : ''}</div>
</div>`).join('');
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const scrollY = window.scrollY || 0;
    let top = rect.bottom + scrollY + 8;
    let left = rect.left + (window.scrollX || 0);
    if (left + 340 > window.innerWidth) left = window.innerWidth - 360;
    if (top + 400 > window.innerHeight + scrollY) top = rect.top + scrollY - 416;

    popover.style.top = `${top}px`;
    popover.style.left = `${left}px`;
    popover.classList.remove('hidden');
  }

  document.getElementById('prev-month')?.addEventListener('click', () => {
    currentMonth--;
    if (currentMonth < 0) { currentMonth = 11; currentYear--; }
    renderCalendar(currentYear, currentMonth);
  });
  document.getElementById('next-month')?.addEventListener('click', () => {
    currentMonth++;
    if (currentMonth > 11) { currentMonth = 0; currentYear++; }
    renderCalendar(currentYear, currentMonth);
  });
  document.addEventListener('click', e => {
    const popover = document.getElementById('event-popover');
    if (popover && !popover.contains(e.target) && !e.target.closest('.cal-day--has-events')) {
      popover.classList.add('hidden');
    }
  });

  renderCalendar(currentYear, currentMonth);
}


// ── Shared ────────────────────────────────────────────────────────────────────
function animateCards() {
  if (!('IntersectionObserver' in window)) return;
  const cards = document.querySelectorAll('.event-card, .featured-card, .category-card, .borough-card');
  cards.forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(16px)';
    card.style.transition = `opacity 0.4s ease ${(i % 8) * 50}ms, transform 0.4s ease ${(i % 8) * 50}ms`;
  });
  const obs = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'none';
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  cards.forEach(c => obs.observe(c));
}

function toggleMobileNav() {
  const links = document.querySelector('.nav-links');
  if (!links) return;
  links.style.display = links.style.display === 'flex' ? 'none' : 'flex';
  links.style.flexDirection = 'column';
  links.style.position = 'absolute';
  links.style.top = '64px';
  links.style.left = '0';
  links.style.right = '0';
  links.style.background = '#0d1b2a';
  links.style.padding = '1rem';
  links.style.borderBottom = '2px solid #c9a84c';
  links.style.zIndex = '99';
}

function loadFooterStats() {
  const el = document.getElementById('footer-stats');
  if (!el) return;
  TMC.fetch('/api/stats').then(data => {
    el.innerHTML = `
<h4>Stats</h4>
<div style="font-size:0.8rem;color:rgba(255,255,255,0.55);display:flex;flex-direction:column;gap:.25rem">
  <span>${data.total_events} total events</span>
  <span>${data.upcoming_events} upcoming</span>
  <span>${data.free_events} free</span>
</div>`;
  }).catch(() => {});
}

function triggerScrape(source) {
  const overlay = document.getElementById('scrape-overlay');
  const statusEl = overlay?.querySelector('.scrape-status');
  if (overlay) overlay.classList.remove('hidden');
  if (statusEl) statusEl.textContent = `Scraping ${source || 'all sources'}…`;

  fetch(TMC.apiBase + '/api/scrape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: source || 'all' }),
  }).then(r => r.json()).then(data => {
    if (overlay) overlay.classList.add('hidden');
    alert(`✓ Scrape complete!\n\nNYC.gov: ${data.nyc_gov || 0}\nEventbrite: ${data.eventbrite || 0}\nTimeOut NY: ${data.timeout || 0}\nTotal: ${data.total || 0}`);
    window.location.reload();
  }).catch(err => {
    if (overlay) overlay.classList.add('hidden');
    alert('Scrape failed: ' + err.message);
  });
}


// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;

  if (page === 'index') initIndexPage();
  else if (page === 'events') {
    initEventsPage();
    const savedView = localStorage.getItem('tmc-view-mode');
    if (savedView) setView(savedView);
  }
  else if (page === 'calendar') initCalendarPage();
  else if (page === 'event') initEventDetailPage();

  loadFooterStats();

  // Auto-dismiss flash messages
  setTimeout(() => {
    document.querySelectorAll('.flash').forEach(el => {
      el.style.transition = 'opacity 0.5s ease';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 500);
    });
  }, 5000);
});
