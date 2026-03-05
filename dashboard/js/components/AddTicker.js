/**
 * Stock Monitor Dashboard - Add Ticker Modal Component
 * Allows adding new tickers to the Notion watchlist from the dashboard
 */

const AddTickerComponent = (() => {
  let isOpen = false;

  // Sector options matching SECTOR_MAP from notion_sync.py
  const SECTORS = [
    'Tech', 'Semiconductors', 'Defense', 'Space', 'Energy',
    'Nuclear', 'Crypto', 'Robotics', 'Financials', 'Industrial',
    'ETF', 'Biotech', 'Consumer', 'Speculative'
  ];

  const SENTIMENTS = ['Bullish', 'Neutral', 'Bearish', 'Caution'];
  const STATUSES = ['Watching', 'Holding'];

  /**
   * Create and inject the modal HTML into the DOM
   */
  function createModal() {
    if (document.getElementById('add-ticker-modal')) return;

    const sectorOptions = SECTORS.map(s => `<option value="${s}">${s}</option>`).join('');
    const sentimentOptions = SENTIMENTS.map(s => `<option value="${s}">${s}</option>`).join('');
    const statusOptions = STATUSES.map(s => `<option value="${s}">${s}</option>`).join('');

    const modalHtml = `
      <div class="modal-overlay" id="add-ticker-modal" aria-hidden="true">
        <div class="modal" style="max-width: 420px;">
          <button class="modal__close" aria-label="Close" id="add-ticker-close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <div class="modal__content">
            <h2 class="modal__title">Add Ticker</h2>
            <form id="add-ticker-form" autocomplete="off">
              <div class="form-group">
                <label class="form-label" for="add-ticker-symbol">Ticker *</label>
                <input class="form-input" type="text" id="add-ticker-symbol"
                       placeholder="e.g. PLTR" maxlength="10" required autofocus>
                <div class="form-error" id="add-ticker-error" style="display: none;"></div>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label class="form-label" for="add-ticker-sector">Sector</label>
                  <select class="form-select" id="add-ticker-sector">
                    <option value="">Select...</option>
                    ${sectorOptions}
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label" for="add-ticker-status">Status</label>
                  <select class="form-select" id="add-ticker-status">
                    ${statusOptions}
                  </select>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label" for="add-ticker-sentiment">Sentiment</label>
                <select class="form-select" id="add-ticker-sentiment">
                  <option value="">Select...</option>
                  ${sentimentOptions}
                </select>
              </div>

              <div class="form-group">
                <label class="form-label" for="add-ticker-thesis">Investment Thesis</label>
                <textarea class="form-textarea" id="add-ticker-thesis"
                          placeholder="Why are you watching this stock?" rows="2"></textarea>
              </div>

              <div class="form-group">
                <label class="form-label" for="add-ticker-catalysts">Catalysts</label>
                <textarea class="form-textarea" id="add-ticker-catalysts"
                          placeholder="Upcoming events, earnings, product launches..." rows="2"></textarea>
              </div>

              <div class="form-actions">
                <button type="button" class="btn" id="add-ticker-cancel">Cancel</button>
                <button type="submit" class="btn btn--primary" id="add-ticker-submit">Add Ticker</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Event listeners
    document.getElementById('add-ticker-close').addEventListener('click', close);
    document.getElementById('add-ticker-cancel').addEventListener('click', close);
    document.getElementById('add-ticker-modal').addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-overlay')) close();
    });
    document.getElementById('add-ticker-form').addEventListener('submit', handleSubmit);

    // Auto-uppercase ticker input
    document.getElementById('add-ticker-symbol').addEventListener('input', (e) => {
      e.target.value = e.target.value.toUpperCase();
      // Clear error on input
      const errorEl = document.getElementById('add-ticker-error');
      errorEl.style.display = 'none';
      e.target.classList.remove('form-input--error');
    });
  }

  /**
   * Open the add ticker modal
   */
  function open() {
    createModal();
    const modal = document.getElementById('add-ticker-modal');
    modal.classList.add('modal-overlay--visible');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    isOpen = true;

    // Focus ticker input
    setTimeout(() => {
      document.getElementById('add-ticker-symbol').focus();
    }, 100);
  }

  /**
   * Close the add ticker modal and reset form
   */
  function close() {
    const modal = document.getElementById('add-ticker-modal');
    if (!modal) return;

    modal.classList.remove('modal-overlay--visible');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    isOpen = false;

    // Reset form
    document.getElementById('add-ticker-form').reset();
    const errorEl = document.getElementById('add-ticker-error');
    errorEl.style.display = 'none';
    document.getElementById('add-ticker-symbol').classList.remove('form-input--error');
  }

  /**
   * Handle form submission
   */
  async function handleSubmit(e) {
    e.preventDefault();

    const ticker = document.getElementById('add-ticker-symbol').value.trim().toUpperCase();
    if (!ticker) {
      showError('Ticker symbol is required');
      return;
    }

    const submitBtn = document.getElementById('add-ticker-submit');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Adding...';

    try {
      const result = await API.addTicker({
        ticker,
        sector: document.getElementById('add-ticker-sector').value,
        status: document.getElementById('add-ticker-status').value,
        sentiment: document.getElementById('add-ticker-sentiment').value,
        investment_thesis: document.getElementById('add-ticker-thesis').value,
        catalysts: document.getElementById('add-ticker-catalysts').value,
      });

      // Success — optimistically inject the new ticker into the watchlist UI
      close();
      App.showToast(`${ticker} added to watchlist — refreshing data...`, 'success');

      // Optimistically add to the current watchlist so it appears immediately
      if (WatchlistComponent && WatchlistComponent.getFilteredStocks) {
        const optimisticStock = {
          symbol: ticker,
          name: result.company || ticker,
          price: 0,
          change: 0,
          change_percent: 0,
          sector: result.sector || '',
          sentiment: result.sentiment || '',
          status: result.status || 'Watching',
          investment_thesis: result.investment_thesis || '',
          catalysts: result.catalysts || '',
          daily_closes: [],
        };
        WatchlistComponent.addStock(optimisticStock);
      }

      // Also do a full refresh in the background to get real price data
      App.refreshData(true);

    } catch (error) {
      const message = error.message || 'Failed to add ticker';
      showError(message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Add Ticker';
    }
  }

  /**
   * Show an error message on the ticker input
   */
  function showError(message) {
    const errorEl = document.getElementById('add-ticker-error');
    const inputEl = document.getElementById('add-ticker-symbol');
    errorEl.textContent = message;
    errorEl.style.display = 'block';
    inputEl.classList.add('form-input--error');
    inputEl.focus();
  }

  /**
   * Check if the modal is currently open
   */
  function isModalOpen() {
    return isOpen;
  }

  return {
    open,
    close,
    isModalOpen
  };
})();
