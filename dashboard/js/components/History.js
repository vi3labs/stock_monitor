/**
 * Stock Monitor Dashboard - History Component
 * Weekly report timeline, WoW chart, watchlist diffs, and streaks
 */

const HistoryComponent = (() => {
  let initialized = false;
  let reports = [];
  let streaks = [];
  let watchlistChanges = [];
  let selectedReport = null;

  async function init() {
    if (initialized && reports.length) return;

    const container = document.getElementById('history-container');
    if (!container) return;

    container.innerHTML = '<div class="empty-state"><p class="empty-state__message">Loading history...</p></div>';

    try {
      const [reportsData, streaksData, changesData] = await Promise.all([
        API.getHistoryReports(),
        API.getStreaks().catch(() => []),
        API.getWatchlistChanges().catch(() => [])
      ]);

      reports = reportsData || [];
      streaks = streaksData || [];
      watchlistChanges = changesData || [];

      render(container);
      initialized = true;
    } catch (error) {
      console.error('[History] Error loading data:', error);
      container.innerHTML = '<div class="empty-state"><p class="empty-state__message">Failed to load history data</p></div>';
    }
  }

  function render(container) {
    if (!reports.length) {
      container.innerHTML = '<div class="empty-state"><p class="empty-state__message">No weekly reports yet</p></div>';
      return;
    }

    container.innerHTML = `
      <div class="history-layout">
        <div class="history-layout__main">
          <div class="history-chart-section">
            <h3 class="history-section-title">Week-over-Week Performance</h3>
            <canvas id="history-wow-chart" class="history-wow-chart"></canvas>
          </div>
          <div class="history-timeline-section">
            <h3 class="history-section-title">Report Timeline</h3>
            <div class="history-timeline" id="history-timeline"></div>
          </div>
          <div class="history-viewer-section" id="history-viewer-section" style="display: none;">
            <div class="history-viewer-header">
              <h3 class="history-section-title" id="history-viewer-title">Report</h3>
              <button class="btn history-viewer-close" onclick="HistoryComponent.closeViewer()">Close</button>
            </div>
            <iframe id="history-viewer-iframe" class="history-viewer-iframe" sandbox="allow-same-origin"></iframe>
          </div>
        </div>
        <div class="history-layout__sidebar">
          ${renderStreaks()}
          ${renderWatchlistChanges()}
        </div>
      </div>
    `;

    renderTimeline();
    drawWoWChart();
  }

  function renderTimeline() {
    const timeline = document.getElementById('history-timeline');
    if (!timeline) return;

    timeline.innerHTML = reports.map(report => {
      const date = new Date(report.report_date + 'T00:00:00');
      const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      const avgChange = report.avg_change_pct || 0;
      const changeClass = avgChange >= 0 ? 'history-card__change--positive' : 'history-card__change--negative';
      const gainers = report.gainers || 0;
      const losers = report.losers || 0;

      return `
        <div class="history-card" data-date="${report.report_date}" onclick="HistoryComponent.selectReport('${report.report_date}')">
          <div class="history-card__header">
            <span class="history-card__date">${dateStr}</span>
            <span class="history-card__change ${changeClass}">${App.formatPercent(avgChange)}</span>
          </div>
          <div class="history-card__stats">
            <span class="history-card__stat history-card__stat--gain">${gainers} gainers</span>
            <span class="history-card__stat history-card__stat--loss">${losers} losers</span>
          </div>
          ${report.top_gainer ? `<div class="history-card__mover"><span class="history-card__mover-label">Top:</span> ${report.top_gainer} ${App.formatPercent(report.top_gainer_pct)}</div>` : ''}
          ${report.top_loser ? `<div class="history-card__mover"><span class="history-card__mover-label">Bottom:</span> ${report.top_loser} ${App.formatPercent(report.top_loser_pct)}</div>` : ''}
        </div>
      `;
    }).join('');
  }

  function drawWoWChart() {
    const canvas = document.getElementById('history-wow-chart');
    if (!canvas || reports.length < 2) return;

    // Reports come newest-first, reverse for chronological chart
    const data = reports.map(r => r.avg_change_pct || 0).reverse();
    const lastVal = data[data.length - 1];
    Charts.drawSparkline(canvas, data, lastVal, {
      width: canvas.clientWidth || 600,
      height: 80,
      lineWidth: 2,
      showEndPoint: true,
      fill: true
    });
  }

  function renderStreaks() {
    const filtered = streaks.filter(s => s.weeks >= 3);
    if (!filtered.length) {
      return `
        <div class="history-sidebar-section">
          <h3 class="history-section-title">Streaks</h3>
          <p class="history-sidebar-empty">No active streaks (3+ weeks)</p>
        </div>
      `;
    }

    const items = filtered.map(s => {
      const direction = s.direction === 'up' ? 'streak-badge--up' : 'streak-badge--down';
      const arrow = s.direction === 'up' ? '\u2191' : '\u2193';
      return `<div class="streak-item"><span class="streak-badge ${direction}">${arrow} ${s.weeks}w</span> <span class="streak-item__symbol">${s.symbol}</span></div>`;
    }).join('');

    return `
      <div class="history-sidebar-section">
        <h3 class="history-section-title">Streaks (3+ weeks)</h3>
        <div class="streak-list">${items}</div>
      </div>
    `;
  }

  function renderWatchlistChanges() {
    if (!watchlistChanges.length) {
      return `
        <div class="history-sidebar-section">
          <h3 class="history-section-title">Watchlist Changes</h3>
          <p class="history-sidebar-empty">No recent changes</p>
        </div>
      `;
    }

    // Group flat rows {change_date, symbol, action} by date
    const grouped = {};
    watchlistChanges.forEach(c => {
      const d = c.change_date;
      if (!grouped[d]) grouped[d] = { added: [], removed: [] };
      if (c.action === 'added') grouped[d].added.push(c.symbol);
      else grouped[d].removed.push(c.symbol);
    });

    const items = Object.entries(grouped)
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([dateKey, changes]) => {
        const date = new Date(dateKey + 'T00:00:00');
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const added = changes.added.map(s => `<span class="diff-badge diff-badge--added">+${s}</span>`).join('');
        const removed = changes.removed.map(s => `<span class="diff-badge diff-badge--removed">-${s}</span>`).join('');
        return `
          <div class="watchlist-change">
            <span class="watchlist-change__date">${dateStr}</span>
            <div class="watchlist-change__badges">${added}${removed}</div>
          </div>
        `;
      }).join('');

    return `
      <div class="history-sidebar-section">
        <h3 class="history-section-title">Watchlist Changes</h3>
        <div class="watchlist-changes-list">${items}</div>
      </div>
    `;
  }

  async function selectReport(date) {
    selectedReport = date;

    // Highlight selected card
    document.querySelectorAll('.history-card').forEach(c => c.classList.remove('history-card--selected'));
    const card = document.querySelector(`.history-card[data-date="${date}"]`);
    if (card) card.classList.add('history-card--selected');

    // Show viewer
    const viewerSection = document.getElementById('history-viewer-section');
    const iframe = document.getElementById('history-viewer-iframe');
    const title = document.getElementById('history-viewer-title');
    if (!viewerSection || !iframe) return;

    viewerSection.style.display = 'block';
    title.textContent = `Report - ${new Date(date + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`;

    try {
      const html = await API.getHistoryReportHtml(date);
      iframe.srcdoc = html;
    } catch (error) {
      console.error('[History] Error loading report HTML:', error);
      iframe.srcdoc = '<p style="color:#aaa;font-family:sans-serif;padding:20px;">Failed to load report</p>';
    }
  }

  function closeViewer() {
    const viewerSection = document.getElementById('history-viewer-section');
    if (viewerSection) viewerSection.style.display = 'none';
    selectedReport = null;
    document.querySelectorAll('.history-card').forEach(c => c.classList.remove('history-card--selected'));
  }

  function reset() {
    initialized = false;
  }

  return { init, selectReport, closeViewer, reset };
})();
