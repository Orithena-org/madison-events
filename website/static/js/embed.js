/**
 * Madison Events Embeddable Widget
 *
 * Usage:
 *   <div id="madison-events-widget"
 *        data-category=""
 *        data-venue=""
 *        data-limit="5"
 *        data-theme="light">
 *   </div>
 *   <script src="https://orithena-org.github.io/madison-events/static/js/embed.js" async></script>
 */
(function() {
  var SITE = 'https://orithena-org.github.io/madison-events';
  var DATA_URL = SITE + '/data/events.json';

  function init() {
    var container = document.getElementById('madison-events-widget');
    if (!container) return;

    var category = (container.getAttribute('data-category') || '').toLowerCase();
    var venue = (container.getAttribute('data-venue') || '').toLowerCase();
    var limit = parseInt(container.getAttribute('data-limit') || '5', 10);
    var theme = container.getAttribute('data-theme') || 'light';

    // Inject styles
    var style = document.createElement('style');
    style.textContent = buildCSS(theme);
    container.appendChild(style);

    // Show loading
    container.innerHTML += '<div class="mew-loading">Loading events...</div>';

    // Fetch events
    var xhr = new XMLHttpRequest();
    xhr.open('GET', DATA_URL);
    xhr.onload = function() {
      if (xhr.status !== 200) {
        container.innerHTML = '<div class="mew-error">Unable to load events.</div>';
        return;
      }
      try {
        var data = JSON.parse(xhr.responseText);
      } catch (e) {
        container.innerHTML = '<div class="mew-error">Unable to load events.</div>';
        return;
      }
      var events = filterEvents(data.events || [], category, venue, limit);
      render(container, events, theme);
    };
    xhr.onerror = function() {
      container.innerHTML = '<div class="mew-error">Unable to load events.</div>';
    };
    xhr.send();
  }

  function filterEvents(events, category, venue, limit) {
    var today = new Date().toISOString().slice(0, 10);
    var filtered = events.filter(function(e) {
      if (e.date < today) return false;
      if (category && (e.category || '').toLowerCase() !== category) return false;
      if (venue && (e.venue || '').toLowerCase().indexOf(venue) === -1) return false;
      return true;
    });
    filtered.sort(function(a, b) { return a.date.localeCompare(b.date); });
    return filtered.slice(0, limit);
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function render(container, events, theme) {
    var html = '<div class="mew-widget">';
    html += '<div class="mew-header"><a href="' + SITE + '/" target="_blank" rel="noopener">Madison Events</a></div>';

    if (events.length === 0) {
      html += '<div class="mew-empty">No upcoming events found.</div>';
    } else {
      for (var i = 0; i < events.length; i++) {
        var e = events[i];
        html += '<a class="mew-event" href="' + SITE + '/' + esc(e.detail_url) + '" target="_blank" rel="noopener">';
        html += '<div class="mew-date">' + esc(e.date_display || e.date) + '</div>';
        html += '<div class="mew-title">' + esc(e.title) + '</div>';
        html += '<div class="mew-meta">';
        if (e.venue) html += '<span>' + esc(e.venue) + '</span>';
        if (e.time_display) html += '<span>' + esc(e.time_display) + '</span>';
        html += '</div>';
        html += '</a>';
      }
    }

    html += '<div class="mew-footer"><a href="' + SITE + '/" target="_blank" rel="noopener">View all events &rarr;</a></div>';
    html += '</div>';
    container.innerHTML = html;

    // Re-inject styles (innerHTML cleared them)
    var style = document.createElement('style');
    style.textContent = buildCSS(theme);
    container.appendChild(style);
  }

  function buildCSS(theme) {
    var isDark = theme === 'dark';
    var bg = isDark ? '#1a1a2e' : '#ffffff';
    var text = isDark ? '#e0e0e0' : '#1a1a2e';
    var muted = isDark ? '#999' : '#666';
    var border = isDark ? '#333' : '#e0e0e0';
    var hover = isDark ? '#252545' : '#f8f8f8';
    var accent = '#c41e3a';

    return '' +
      '#madison-events-widget { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }' +
      '.mew-widget { background: ' + bg + '; border: 1px solid ' + border + '; border-radius: 8px; overflow: hidden; max-width: 400px; }' +
      '.mew-header { padding: 12px 16px; border-bottom: 1px solid ' + border + '; font-weight: 700; font-size: 15px; }' +
      '.mew-header a { color: ' + accent + '; text-decoration: none; }' +
      '.mew-event { display: block; padding: 12px 16px; border-bottom: 1px solid ' + border + '; text-decoration: none; color: ' + text + '; transition: background 0.15s; }' +
      '.mew-event:hover { background: ' + hover + '; }' +
      '.mew-event:last-of-type { border-bottom: none; }' +
      '.mew-date { font-size: 12px; color: ' + accent + '; font-weight: 600; margin-bottom: 2px; }' +
      '.mew-title { font-size: 14px; font-weight: 600; line-height: 1.3; margin-bottom: 2px; color: ' + text + '; }' +
      '.mew-meta { font-size: 12px; color: ' + muted + '; display: flex; gap: 8px; }' +
      '.mew-empty { padding: 24px 16px; text-align: center; color: ' + muted + '; font-size: 14px; }' +
      '.mew-loading { padding: 24px 16px; text-align: center; color: ' + muted + '; font-size: 14px; }' +
      '.mew-error { padding: 24px 16px; text-align: center; color: ' + accent + '; font-size: 14px; }' +
      '.mew-footer { padding: 10px 16px; border-top: 1px solid ' + border + '; text-align: center; font-size: 13px; }' +
      '.mew-footer a { color: ' + accent + '; text-decoration: none; font-weight: 600; }' +
      '.mew-footer a:hover { text-decoration: underline; }';
  }

  // Auto-init when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
