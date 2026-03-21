/**
 * Stock Monitor Dashboard - Performance Component
 * Rolling performance, heatmap, and streak leaderboard
 */

const PerformanceComponent = (() => {
  let initialized = false;
  let currentPeriod = '1m';
  let performanceData = null;
  let streaksData = null;
  let activeSymbols = new Set();

  async function init() {
    if (initialized) return;

    const container = document.getElementById('performance-container');
    if (!container) return;

    container.innerHTML = '<div class="empty-state"><p class="empty-state__message">Loading performance...</p></div>';

    try {
      const [perfData, streaks, quotes] = await Promise.all([
        API.getRollingPerformance(currentPeriod),
        API.getStreaks().catch(() => []),
        API.getQuotes().catch(() => ({}))
      ]);

      performanceData = perfData;
      streaksData = streaks || [];
      activeSymbols = new Set(Object.keys(quotes));

      render(container);
      initialized = true;
    } catch (error) {
      console.error('[Performance] Error loading data:', error);
      container.innerHTML = '<div class="empty-state"><p class="empty-state__message">Failed to load performance data</p></div>';
    }
  }

  function render(container) {
    if (!performanceData) {
      container.innerHTML = '<div class="empty-state"><p class="empty-state__message">No performance data available</p></div>';
      return;
    }

    const topPerformers = performanceData.top || [];
    const bottomPerformers = performanceData.bottom || [];
    const allTickers = performanceData.all || [];

    container.innerHTML = `
      <div class="perf-tabs">
        <button class="perf-tab ${currentPeriod === '1w' ? 'perf-tab--active' : ''}" onclick="PerformanceComponent.setPeriod('1w')">1W</button>
        <button class="perf-tab ${currentPeriod === '1m' ? 'perf-tab--active' : ''}" onclick="PerformanceComponent.setPeriod('1m')">1M</button>
        <button class="perf-tab ${currentPeriod === '3m' ? 'perf-tab--active' : ''}" onclick="PerformanceComponent.setPeriod('3m')">3M</button>
      </div>

      <div class="perf-layout">
        <div class="perf-layout__columns">
          <div class="perf-column">
            <h3 class="perf-column__title perf-column__title--gain">Top 5 Performers</h3>
            ${renderPerformerList(topPerformers, true)}
          </div>
          <div class="perf-column">
            <h3 class="perf-column__title perf-column__title--loss">Bottom 5 Performers</h3>
            ${renderPerformerList(bottomPerformers, false)}
          </div>
        </div>

        <div class="perf-heatmap-section">
          <h3 class="history-section-title">Heatmap</h3>
          <div class="perf-heatmap" id="perf-heatmap">
            ${renderHeatmap(allTickers)}
          </div>
        </div>

        <div class="perf-streaks-section">
          <h3 class="history-section-title">Streak Leaderboard</h3>
          ${renderStreakLeaderboard()}
        </div>
      </div>
    `;
  }

  function renderPerformerList(performers, isGain) {
    if (!performers.length) {
      return '<p class="history-sidebar-empty">No data</p>';
    }

    return performers.map((p, i) => {
      const changeClass = p.change_pct >= 0 ? 'change--positive' : 'change--negative';
      return `
        <div class="perf-performer">
          <span class="perf-performer__rank">${i + 1}</span>
          <span class="perf-performer__symbol">${p.symbol}</span>
          <span class="perf-performer__change ${changeClass}">${App.formatPercent(p.change_pct)}</span>
        </div>
      `;
    }).join('');
  }

  function renderHeatmap(tickers) {
    if (!tickers.length) {
      return '<p class="history-sidebar-empty">No data</p>';
    }

    return tickers.map(t => {
      const change = t.change_pct || 0;
      const bg = heatmapColor(change);
      const isArchived = !activeSymbols.has(t.symbol);
      const textColor = Math.abs(change) > 3 ? '#fff' : 'var(--text-primary)';
      const archivedClass = isArchived ? ' heatmap-cell--archived' : '';
      const archivedLabel = isArchived ? ' (archived)' : '';
      return `<div class="heatmap-cell${archivedClass}" style="background: ${bg}; color: ${textColor};" title="${t.symbol}: ${App.formatPercent(change)}${archivedLabel}">
        <span class="heatmap-cell__symbol">${t.symbol}</span>
        <span class="heatmap-cell__change">${App.formatPercent(change)}</span>
      </div>`;
    }).join('');
  }

  function heatmapColor(change) {
    const clamped = Math.max(-10, Math.min(10, change));
    const ratio = clamped / 10;

    if (ratio >= 0) {
      const g = Math.round(50 + ratio * 150);
      const r = Math.round(30 * (1 - ratio));
      const b = Math.round(30 * (1 - ratio));
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      const absRatio = Math.abs(ratio);
      const r = Math.round(50 + absRatio * 180);
      const g = Math.round(30 * (1 - absRatio));
      const b = Math.round(30 * (1 - absRatio));
      return `rgb(${r}, ${g}, ${b})`;
    }
  }

  function renderStreakLeaderboard() {
    if (!streaksData.length) {
      return '<p class="history-sidebar-empty">No streaks</p>';
    }

    const sorted = [...streaksData].sort((a, b) => b.weeks - a.weeks);

    return `<div class="streak-leaderboard">${sorted.map((s, i) => {
      const direction = s.direction === 'up' ? 'streak-badge--up' : 'streak-badge--down';
      const arrow = s.direction === 'up' ? '\u2191' : '\u2193';
      return `
        <div class="streak-leader">
          <span class="streak-leader__rank">${i + 1}</span>
          <span class="streak-leader__symbol">${s.symbol}</span>
          <span class="streak-badge ${direction}">${arrow} ${s.weeks}w</span>
        </div>
      `;
    }).join('')}</div>`;
  }

  async function setPeriod(period) {
    if (period === currentPeriod) return;
    currentPeriod = period;
    initialized = false;
    await init();
  }

  function reset() {
    initialized = false;
  }

  return { init, setPeriod, reset };
})();
