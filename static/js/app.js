/**
 * TMC Cultural Calendar — Main App JS
 */

// ── Scrape Trigger ──────────────────────────────────────────────
function triggerScrape(source) {
  const overlay = document.getElementById('scrape-overlay');
  const statusEl = overlay ? overlay.querySelector('.scrape-status') : null;

  if (overlay) {
    overlay.classList.remove('hidden');
    if (statusEl) statusEl.textContent = `Scraping ${source === 'all' || !source ? 'all sources' : source}…`;
  }

  fetch('/api/scrape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: source || 'all' }),
  })
    .then(r => r.json())
    .then(data => {
      if (overlay) overlay.classList.add('hidden');
      const msg = [
        `✓ Scrape complete!`,
        ``,
        `NYC.gov:    ${data.nyc_gov || 0} events`,
        `Eventbrite: ${data.eventbrite || 0} events`,
        `TimeOut NY: ${data.timeout || 0} events`,
        `─────────────────────`,
        `Total:      ${data.total || 0} unique events`,
        data.errors?.length ? `\nWarnings: ${data.errors.join(', ')}` : '',
      ].filter(Boolean).join('\n');
      alert(msg);
      window.location.reload();
    })
    .catch(err => {
      if (overlay) overlay.classList.add('hidden');
      alert('Scrape failed: ' + err.message + '\n\nMake sure the Flask server is running.');
    });
}

// ── Mobile Nav ──────────────────────────────────────────────────
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

// ── Footer Stats ────────────────────────────────────────────────
function loadFooterStats() {
  const statsEl = document.getElementById('footer-stats');
  if (!statsEl) return;

  fetch('/api/stats')
    .then(r => r.json())
    .then(data => {
      statsEl.innerHTML = `
        <h4>Stats</h4>
        <div style="font-size:0.8rem;color:rgba(255,255,255,0.55);display:flex;flex-direction:column;gap:0.25rem;">
          <span>${data.total_events} total events</span>
          <span>${data.upcoming_events} upcoming</span>
          <span>${data.free_events} free</span>
        </div>
      `;
    })
    .catch(() => {
      if (statsEl) statsEl.querySelector('.stat-loading')?.remove();
    });
}

// ── Calendar Logic ──────────────────────────────────────────────
(function initCalendar() {
  const grid = document.getElementById('calendar-grid');
  if (!grid) return; // Not on calendar page

  const events = window.TMC_EVENTS || [];

  // Build date → events map
  const eventsByDate = {};
  events.forEach(ev => {
    if (ev.date) {
      (eventsByDate[ev.date] = eventsByDate[ev.date] || []).push(ev);
    }
  });

  const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const MONTHS = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December'];

  const today = new Date();
  let currentYear = today.getFullYear();
  let currentMonth = today.getMonth();

  // Category colors (must match CSS legend)
  const catColors = {
    'Arts & Culture': '#e63946',
    'Music': '#2a9d8f',
    'Theater': '#9b59b6',
    'Dance': '#e76f51',
    'Festivals': '#f4a261',
    'Parks & Recreation': '#2d6a4f',
    'Heritage & History': '#8b6914',
    'Community': '#457b9d',
    'Weekend Picks': '#c0392b',
    'Other': '#666',
  };

  function renderCalendar(year, month) {
    const label = document.getElementById('month-label');
    if (label) label.textContent = `${MONTHS[month]} ${year}`;

    grid.innerHTML = '';

    // Day headers
    DAYS.forEach(d => {
      const el = document.createElement('div');
      el.className = 'cal-day-header';
      el.textContent = d;
      grid.appendChild(el);
    });

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const daysInPrev = new Date(year, month, 0).getDate();

    const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;

    let cells = [];

    // Previous month fill
    for (let i = firstDay - 1; i >= 0; i--) {
      cells.push({ day: daysInPrev - i, month: month - 1, year, other: true });
    }
    // Current month
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push({ day: d, month, year, other: false });
    }
    // Next month fill
    const remaining = 42 - cells.length;
    for (let d = 1; d <= remaining; d++) {
      cells.push({ day: d, month: month + 1, year, other: true });
    }

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

      // Show up to 3 event dots
      const visible = dayEvents.slice(0, 3);
      visible.forEach(ev => {
        const dot = document.createElement('span');
        dot.className = 'cal-event-dot';
        dot.textContent = ev.title.substring(0, 18) + (ev.title.length > 18 ? '…' : '');
        dot.style.background = catColors[ev.category] || '#2d4a66';
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
        el.addEventListener('click', (e) => showPopover(e, dateStr, dayEvents));
      }

      grid.appendChild(el);
    });
  }

  function showPopover(e, dateStr, dayEvents) {
    const popover = document.getElementById('event-popover');
    const dateLabel = document.getElementById('popover-date');
    const eventsContainer = document.getElementById('popover-events');
    if (!popover || !dateLabel || !eventsContainer) return;

    dateLabel.textContent = new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });

    eventsContainer.innerHTML = dayEvents.map(ev => `
      <div class="popover-event-item">
        <div class="popover-event-title">
          <a href="/event/${ev.id}">${ev.title}</a>
        </div>
        <div class="popover-event-meta">
          ${ev.category || ''} · ${ev.source || ''} ${ev.location ? `· ${ev.location.substring(0, 30)}` : ''}
        </div>
      </div>
    `).join('');

    // Position near click
    const rect = e.currentTarget.getBoundingClientRect();
    const scrollY = window.scrollY || 0;
    const scrollX = window.scrollX || 0;
    let top = rect.bottom + scrollY + 8;
    let left = rect.left + scrollX;

    // Keep on screen
    if (left + 340 > window.innerWidth) left = window.innerWidth - 360;
    if (top + 400 > window.innerHeight + scrollY) top = rect.top + scrollY - 416;

    popover.style.top = `${top}px`;
    popover.style.left = `${left}px`;
    popover.classList.remove('hidden');
  }

  // Nav buttons
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

  // Close popover on outside click
  document.addEventListener('click', (e) => {
    const popover = document.getElementById('event-popover');
    if (popover && !popover.contains(e.target) && !e.target.closest('.cal-day--has-events')) {
      popover.classList.add('hidden');
    }
  });

  renderCalendar(currentYear, currentMonth);
})();

// ── Card Entrance Animation ─────────────────────────────────────
(function animateCards() {
  if (!('IntersectionObserver' in window)) return;

  const cards = document.querySelectorAll('.event-card, .featured-card, .category-card, .borough-card');
  cards.forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(16px)';
    card.style.transition = `opacity 0.4s ease ${(i % 8) * 50}ms, transform 0.4s ease ${(i % 8) * 50}ms`;
  });

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'none';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  cards.forEach(card => observer.observe(card));
})();

// ── Init ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
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
