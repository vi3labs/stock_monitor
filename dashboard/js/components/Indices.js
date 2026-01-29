/**
 * Stock Monitor Dashboard - Indices Component
 * Renders market index cards with sparklines
 */

const IndicesComponent = (() => {
  const containerId = 'indices-grid';

  // Index display configuration
  const INDEX_CONFIG = {
    '^GSPC': { name: 'S&P 500', order: 1 },
    '^IXIC': { name: 'NASDAQ', order: 2 },
    '^DJI': { name: 'Dow Jones', order: 3 },
    '^VIX': { name: 'VIX', order: 4, isVolatility: true },
    '^RUT': { name: 'Russell 2000', order: 5 }
  };

  /**
   * Render index cards
   * @param {Object} indices - Index data from API
   */
  function render(indices) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!indices || Object.keys(indices).length === 0) {
      container.innerHTML = renderEmptyState();
      return;
    }

    // Sort indices by configured order
    const sortedIndices = Object.entries(indices)
      .map(([symbol, data]) => ({
        symbol,
        ...data,
        config: INDEX_CONFIG[symbol] || { name: data.name, order: 99 }
      }))
      .sort((a, b) => a.config.order - b.config.order)
      .slice(0, 4); // Show only first 4

    // Render cards
    container.innerHTML = sortedIndices.map(renderIndexCard).join('');

    // Draw sparklines after DOM update
    requestAnimationFrame(() => {
      sortedIndices.forEach(index => {
        if (index.daily_closes && index.daily_closes.length > 1) {
          const canvas = document.getElementById(`sparkline-${index.symbol.replace('^', '')}`);
          if (canvas) {
            Charts.drawSparkline(canvas, index.daily_closes, index.change_percent, {
              showEndPoint: true
            });
          }
        }
      });
    });
  }

  /**
   * Render a single index card
   */
  function renderIndexCard(index) {
    const { symbol, config } = index;
    const cleanSymbol = symbol.replace('^', '');
    const isPositive = index.change_percent >= 0;
    const changeClass = isPositive ? 'index-card__change--positive' : 'index-card__change--negative';
    const sign = isPositive ? '+' : '';

    // Format price - VIX doesn't need currency symbol
    let priceDisplay;
    if (config.isVolatility) {
      priceDisplay = index.price.toFixed(2);
    } else {
      priceDisplay = new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }).format(index.price);
    }

    // Format change
    const changeDisplay = `${sign}${index.change.toFixed(2)} (${sign}${index.change_percent.toFixed(2)}%)`;

    return `
      <div class="index-card" role="article" aria-label="${config.name} index">
        <div class="index-card__name">${config.name}</div>
        <div class="index-card__price">${priceDisplay}</div>
        <div class="index-card__change ${changeClass}">
          ${isPositive ? '&#9650;' : '&#9660;'} ${changeDisplay}
        </div>
        <canvas
          class="index-card__sparkline"
          id="sparkline-${cleanSymbol}"
          role="img"
          aria-label="${config.name} 7-day trend"
        ></canvas>
      </div>
    `;
  }

  /**
   * Render empty state
   */
  function renderEmptyState() {
    return `
      <div class="index-card">
        <div class="empty-state">
          <p class="empty-state__message">Unable to load market indices</p>
        </div>
      </div>
    `;
  }

  /**
   * Render loading state
   */
  function renderLoading() {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = Array(4).fill(null).map(() => `
      <div class="index-card loading">
        <div class="index-card__name skeleton skeleton--text" style="width: 80px;"></div>
        <div class="index-card__price skeleton skeleton--price"></div>
        <div class="index-card__change skeleton skeleton--text" style="width: 100px;"></div>
        <div class="index-card__sparkline skeleton skeleton--sparkline"></div>
      </div>
    `).join('');
  }

  return {
    render,
    renderLoading
  };
})();
