/**
 * Stock Monitor Dashboard - Sectors Component
 * Renders sector performance horizontal bar chart
 */

const SectorsComponent = (() => {
  const containerId = 'sector-chart';

  /**
   * Render sector performance chart
   * @param {Array} sectors - Sector data from API
   */
  function render(sectors) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!sectors || sectors.length === 0) {
      container.innerHTML = renderEmptyState();
      return;
    }

    // Use the Charts module to render
    Charts.drawSectorChart(container, sectors);
  }

  /**
   * Render empty state
   */
  function renderEmptyState() {
    return `
      <div class="empty-state">
        <div class="empty-state__icon">&#128202;</div>
        <p class="empty-state__message">No sector data available</p>
      </div>
    `;
  }

  /**
   * Render loading state
   */
  function renderLoading() {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = Array(6).fill(null).map(() => `
      <div class="sector-row loading">
        <span class="sector-row__name skeleton skeleton--text" style="width: 100px;"></span>
        <div class="sector-row__bar-container">
          <div class="skeleton" style="height: 100%; width: 100%;"></div>
        </div>
        <span class="sector-row__value skeleton skeleton--text" style="width: 50px;"></span>
      </div>
    `).join('');
  }

  return {
    render,
    renderLoading
  };
})();
