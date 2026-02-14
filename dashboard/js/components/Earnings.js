/**
 * Stock Monitor Dashboard - Earnings Calendar Component
 * Renders upcoming earnings grouped by date
 */

const EarningsComponent = (() => {
  const containerId = 'earnings-list';

  /**
   * Render the earnings calendar
   * @param {Array} earnings - Earnings data from API
   */
  function render(earnings) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!earnings || earnings.length === 0) {
      container.innerHTML = '<div class="empty-state"><p class="empty-state__message">No upcoming earnings</p></div>';
      return;
    }

    // Group by date
    const grouped = {};
    earnings.forEach(e => {
      if (!grouped[e.date]) grouped[e.date] = [];
      grouped[e.date].push(e);
    });

    let html = '';
    Object.entries(grouped).forEach(([date, items]) => {
      const dateObj = new Date(date + 'T00:00:00');
      const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
      const dateStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

      html += `<div class="earnings-date-group">
        <div class="earnings-date-header">${dayName}, ${dateStr}</div>`;
      items.forEach(item => {
        html += `<div class="earnings-item">
          <span class="earnings-item__symbol">${escapeHtml(item.symbol)}</span>
          <span class="earnings-item__name">${escapeHtml((item.name || '').substring(0, 25))}</span>
          <span class="earnings-item__time">${escapeHtml(item.time || '')}</span>
        </div>`;
      });
      html += '</div>';
    });

    container.innerHTML = html;
  }

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Render loading state
   */
  function renderLoading() {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
      <div class="earnings-date-group">
        <div class="skeleton skeleton--text" style="width: 100px; margin-bottom: var(--space-sm);"></div>
        <div class="skeleton skeleton--text" style="width: 100%; margin-bottom: var(--space-xs);"></div>
        <div class="skeleton skeleton--text" style="width: 90%; margin-bottom: var(--space-xs);"></div>
        <div class="skeleton skeleton--text" style="width: 80%;"></div>
      </div>
    `;
  }

  return {
    render,
    renderLoading
  };
})();
