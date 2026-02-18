/**
 * Stock Monitor Dashboard - Stock Detail Modal Component
 * Shows detailed stock information in a modal overlay
 */

const StockDetailComponent = (() => {
  const modalId = 'stock-detail-modal';
  let currentStock = null;
  let isOpen = false;

  /**
   * Initialize the modal event listeners
   */
  function init() {
    // Create modal container if it doesn't exist
    if (!document.getElementById(modalId)) {
      createModalElement();
    }

    // Close on backdrop click
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
          close();
        }
      });
    }

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && isOpen) {
        close();
      }
    });
  }

  /**
   * Create the modal DOM element
   */
  function createModalElement() {
    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal-overlay';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
      <div class="modal stock-detail-modal">
        <button class="modal__close" aria-label="Close modal">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
        <div class="modal__content" id="stock-detail-content">
          <!-- Content populated dynamically -->
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // Attach close button handler
    modal.querySelector('.modal__close').addEventListener('click', close);
  }

  /**
   * Open the modal with stock data
   * @param {Object} stock - Stock data object
   */
  function open(stock) {
    if (!stock) return;

    currentStock = stock;
    isOpen = true;

    const modal = document.getElementById(modalId);
    const content = document.getElementById('stock-detail-content');

    if (!modal || !content) return;

    // Render content
    content.innerHTML = renderContent(stock);

    // Show modal with animation
    modal.setAttribute('aria-hidden', 'false');
    modal.classList.add('modal-overlay--visible');

    // Draw the larger sparkline
    requestAnimationFrame(() => {
      if (stock.daily_closes && stock.daily_closes.length > 1) {
        const canvas = document.getElementById('detail-sparkline');
        if (canvas) {
          Charts.drawSparkline(canvas, stock.daily_closes, stock.change_percent, {
            width: 280,
            height: 80,
            lineWidth: 2,
            showEndPoint: true
          });
        }
      }
    });

    // Prevent body scroll
    document.body.style.overflow = 'hidden';
  }

  /**
   * Close the modal
   */
  function close() {
    isOpen = false;
    currentStock = null;

    const modal = document.getElementById(modalId);
    if (modal) {
      modal.setAttribute('aria-hidden', 'true');
      modal.classList.remove('modal-overlay--visible');
    }

    // Restore body scroll
    document.body.style.overflow = '';

    // Return focus to previously focused element if applicable
    if (WatchlistComponent && WatchlistComponent.focusSelectedRow) {
      WatchlistComponent.focusSelectedRow();
    }
  }

  /**
   * Render the modal content
   */
  function renderContent(stock) {
    const isPositive = stock.change_percent >= 0;
    const changeClass = isPositive ? 'text-gain' : 'text-loss';
    const changeSign = isPositive ? '+' : '';
    const arrowIcon = isPositive ? '&#9650;' : '&#9660;';

    // Format values
    const price = App.formatCurrency(stock.price);
    const change = `${changeSign}${(stock.change || 0).toFixed(2)}`;
    const changePercent = `${changeSign}${(stock.change_percent || 0).toFixed(2)}%`;
    const volume = App.formatNumber(stock.volume);
    const avgVolume = App.formatNumber(stock.avg_volume);
    const marketCap = App.formatNumber(stock.market_cap);
    const dayHigh = App.formatCurrency(stock.day_high);
    const dayLow = App.formatCurrency(stock.day_low);
    const open = App.formatCurrency(stock.open);
    const prevClose = App.formatCurrency(stock.previous_close);

    // Volume ratio indicator
    const volRatio = stock.volume_ratio || 1;
    let volIndicator = '';
    if (volRatio > 2) {
      volIndicator = '<span class="volume-spike">High Volume</span>';
    } else if (volRatio < 0.5) {
      volIndicator = '<span class="volume-low">Low Volume</span>';
    }

    const yahooUrl = `https://finance.yahoo.com/quote/${encodeURIComponent(stock.symbol)}`;

    return `
      <div class="stock-detail">
        <div class="stock-detail__header">
          <div class="stock-detail__title">
            <h2 class="stock-detail__symbol">${escapeHtml(stock.symbol)}</h2>
            <span class="stock-detail__name">${escapeHtml(stock.name || stock.symbol)}</span>
            <span class="sector-badge sector-badge--${App.getSectorClass(stock.sector)}">${escapeHtml(stock.sector || 'Other')}</span>
          </div>
          <div class="stock-detail__price-block">
            <div class="stock-detail__price">${price}</div>
            <div class="stock-detail__change ${changeClass}">
              ${arrowIcon} ${change} (${changePercent})
            </div>
          </div>
        </div>

        <div class="stock-detail__chart">
          <div class="stock-detail__chart-label">7-Day Trend</div>
          <canvas id="detail-sparkline" width="280" height="80"></canvas>
        </div>

        <div class="stock-detail__stats">
          <div class="stat-row">
            <span class="stat-row__label">Open</span>
            <span class="stat-row__value">${open}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row__label">Previous Close</span>
            <span class="stat-row__value">${prevClose}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row__label">Day Range</span>
            <span class="stat-row__value">${dayLow} - ${dayHigh}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row__label">Volume</span>
            <span class="stat-row__value">${volume} ${volIndicator}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row__label">Avg Volume</span>
            <span class="stat-row__value">${avgVolume}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row__label">Market Cap</span>
            <span class="stat-row__value">${marketCap}</span>
          </div>
        </div>

        ${renderThesisSection(stock)}

        <div class="stock-detail__actions">
          <a href="${yahooUrl}" target="_blank" rel="noopener noreferrer" class="btn btn--primary">
            <svg class="btn__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
              <polyline points="15 3 21 3 21 9"/>
              <line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
            View on Yahoo Finance
          </a>
        </div>
      </div>
    `;
  }

  /**
   * Render the thesis/catalysts section for the detail modal
   */
  function renderThesisSection(stock) {
    const sentiment = stock.sentiment || '';
    const status = stock.status || '';
    const thesis = stock.investment_thesis || '';
    const catalysts = stock.catalysts || '';

    // Don't render the section if there's nothing to show
    if (!sentiment && !status && !thesis && !catalysts) return '';

    const sentimentClass = sentiment ? sentiment.toLowerCase() : 'neutral';
    const statusClass = status ? status.toLowerCase() : '';

    return `
      <div class="stock-detail__thesis">
        <div class="stock-detail__thesis-header">
          ${sentiment ? `<span class="sentiment-badge sentiment-badge--${sentimentClass}">${escapeHtml(sentiment)}</span>` : ''}
          ${status ? `<span class="sentiment-badge status-badge--${statusClass}">${escapeHtml(status)}</span>` : ''}
        </div>
        ${thesis ? `<div class="stock-detail__thesis-text"><strong>Thesis:</strong> ${escapeHtml(thesis)}</div>` : ''}
        ${catalysts ? `<div class="stock-detail__catalysts-text"><strong>Catalysts:</strong> ${escapeHtml(catalysts)}</div>` : ''}
      </div>
    `;
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
   * Check if modal is currently open
   */
  function isModalOpen() {
    return isOpen;
  }

  /**
   * Get the currently displayed stock
   */
  function getCurrentStock() {
    return currentStock;
  }

  // Initialize when DOM is ready
  document.addEventListener('DOMContentLoaded', init);

  return {
    init,
    open,
    close,
    isModalOpen,
    getCurrentStock
  };
})();
