/**
 * Stock Monitor Dashboard - Top Movers Component
 * Renders top gainers and losers panels
 */

const MoversComponent = (() => {
  const gainersListId = 'gainers-list';
  const losersListId = 'losers-list';

  /**
   * Render the movers panels
   * @param {Object} movers - Object with gainers and losers arrays
   */
  function render(movers) {
    if (!movers) return;

    const { gainers, losers } = movers;

    // Render gainers
    const gainersList = document.getElementById(gainersListId);
    if (gainersList) {
      if (gainers && gainers.length > 0) {
        gainersList.innerHTML = gainers.slice(0, 5).map(stock => renderMoverItem(stock, true)).join('');

        // Draw sparklines
        requestAnimationFrame(() => {
          gainers.slice(0, 5).forEach(stock => {
            if (stock.daily_closes && stock.daily_closes.length > 1) {
              const canvas = document.getElementById(`gainer-sparkline-${stock.symbol}`);
              if (canvas) {
                Charts.drawSparkline(canvas, stock.daily_closes, 1, { lineWidth: 1 });
              }
            }
          });
        });
      } else {
        gainersList.innerHTML = renderEmptyState('No gainers today');
      }
    }

    // Render losers
    const losersList = document.getElementById(losersListId);
    if (losersList) {
      if (losers && losers.length > 0) {
        losersList.innerHTML = losers.slice(0, 5).map(stock => renderMoverItem(stock, false)).join('');

        // Draw sparklines
        requestAnimationFrame(() => {
          losers.slice(0, 5).forEach(stock => {
            if (stock.daily_closes && stock.daily_closes.length > 1) {
              const canvas = document.getElementById(`loser-sparkline-${stock.symbol}`);
              if (canvas) {
                Charts.drawSparkline(canvas, stock.daily_closes, -1, { lineWidth: 1 });
              }
            }
          });
        });
      } else {
        losersList.innerHTML = renderEmptyState('No losers today');
      }
    }
  }

  /**
   * Render a single mover item
   */
  function renderMoverItem(stock, isGainer) {
    const changeClass = isGainer ? 'mover-item__change--positive' : 'mover-item__change--negative';
    const sign = isGainer ? '+' : '';
    const sparklineId = isGainer ? `gainer-sparkline-${stock.symbol}` : `loser-sparkline-${stock.symbol}`;

    // Format values
    const changeDisplay = `${sign}${(stock.change_percent || 0).toFixed(2)}%`;
    const priceDisplay = App.formatCurrency(stock.price);

    return `
      <div class="mover-item">
        <span class="mover-item__symbol">${stock.symbol}</span>
        <canvas class="mover-item__sparkline" id="${sparklineId}" width="60" height="20"></canvas>
        <div class="mover-item__data">
          <div class="mover-item__change ${changeClass}">${changeDisplay}</div>
          <div class="mover-item__price">${priceDisplay}</div>
        </div>
      </div>
    `;
  }

  /**
   * Render empty state
   */
  function renderEmptyState(message) {
    return `
      <div class="empty-state" style="padding: var(--space-md);">
        <p class="empty-state__message text-sm">${message}</p>
      </div>
    `;
  }

  /**
   * Render loading state
   */
  function renderLoading() {
    const loadingHtml = Array(3).fill(null).map(() => `
      <div class="mover-item loading">
        <span class="skeleton skeleton--text" style="width: 50px;"></span>
        <span class="skeleton skeleton--sparkline" style="width: 60px; height: 20px;"></span>
        <div class="mover-item__data">
          <span class="skeleton skeleton--text" style="width: 60px;"></span>
        </div>
      </div>
    `).join('');

    const gainersList = document.getElementById(gainersListId);
    const losersList = document.getElementById(losersListId);

    if (gainersList) gainersList.innerHTML = loadingHtml;
    if (losersList) losersList.innerHTML = loadingHtml;
  }

  return {
    render,
    renderLoading
  };
})();
