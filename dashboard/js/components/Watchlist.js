/**
 * Stock Monitor Dashboard - Watchlist Component
 * Renders the main watchlist table with sorting and filtering
 */

const WatchlistComponent = (() => {
  const tableBodyId = 'watchlist-body';
  const searchInputId = 'search-input';
  const sectorFilterId = 'sector-filter';
  const sortSelectId = 'sort-select';
  const countId = 'watchlist-count';

  // State
  let allStocks = [];
  let filteredStocks = [];
  let currentSort = { field: 'change', direction: 'desc' };
  let searchTerm = '';
  let sectorFilter = '';
  let selectedIndex = -1;
  let expandedSymbol = null;
  let editingSymbol = null;

  const SENTIMENTS = ['Bullish', 'Neutral', 'Bearish', 'Caution'];
  const STATUSES = ['Watching', 'Holding'];

  /**
   * Initialize component and event listeners
   */
  function init() {
    // Search input
    const searchInput = document.getElementById(searchInputId);
    if (searchInput) {
      searchInput.addEventListener('input', debounce((e) => {
        searchTerm = e.target.value.toLowerCase();
        renderTable();
      }, 300));
    }

    // Sector filter
    const sectorFilterEl = document.getElementById(sectorFilterId);
    if (sectorFilterEl) {
      sectorFilterEl.addEventListener('change', (e) => {
        sectorFilter = e.target.value;
        renderTable();
      });
    }

    // Sort select
    const sortSelect = document.getElementById(sortSelectId);
    if (sortSelect) {
      sortSelect.addEventListener('change', (e) => {
        currentSort.field = e.target.value;
        renderTable();
      });
    }

    // Table header sorting
    const table = document.getElementById('watchlist-table');
    if (table) {
      table.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
          const field = th.dataset.sort;
          if (currentSort.field === field) {
            currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
          } else {
            currentSort.field = field;
            currentSort.direction = field === 'change' ? 'desc' : 'asc';
          }
          updateSortIndicators();
          renderTable();
        });
      });

      // Click handler — single click toggles expansion, double-click opens modal
      table.addEventListener('click', (e) => {
        // Handle Edit/Save/Cancel/Details buttons FIRST (these live in expansion rows)
        const editBtn = e.target.closest('[data-edit-symbol]');
        if (editBtn) {
          editingSymbol = editBtn.dataset.editSymbol;
          renderTable();
          return;
        }

        const saveBtn = e.target.closest('[data-save-symbol]');
        if (saveBtn) {
          saveEdit(saveBtn.dataset.saveSymbol);
          return;
        }

        const cancelBtn = e.target.closest('[data-cancel-symbol]');
        if (cancelBtn) {
          editingSymbol = null;
          renderTable();
          return;
        }

        const removeBtn = e.target.closest('[data-remove-symbol]');
        if (removeBtn) {
          removeStock(removeBtn.dataset.removeSymbol);
          return;
        }

        const detailsLink = e.target.closest('.expansion-panel__details-link');
        if (detailsLink) {
          const sym = detailsLink.dataset.parentSymbol;
          const stock = filteredStocks.find(s => s.symbol === sym);
          if (stock && StockDetailComponent) {
            StockDetailComponent.open(stock);
          }
          return;
        }

        // Ignore other clicks inside expansion panel (form inputs, textareas, etc.)
        if (e.target.closest('.expansion-panel')) return;

        // For stock rows, require data-symbol
        const row = e.target.closest('tr');
        if (!row || !row.dataset.symbol) return;

        const symbol = row.dataset.symbol;
        const stock = filteredStocks.find(s => s.symbol === symbol);

        if (stock) {
          const newIndex = filteredStocks.findIndex(s => s.symbol === symbol);
          setSelectedIndex(newIndex);
          toggleExpansion(symbol);
        }
      });

      // Double-click opens the full detail modal
      table.addEventListener('dblclick', (e) => {
        const row = e.target.closest('tr');
        if (!row || !row.dataset.symbol) return;

        const symbol = row.dataset.symbol;
        const stock = filteredStocks.find(s => s.symbol === symbol);
        if (stock && StockDetailComponent) {
          StockDetailComponent.open(stock);
        }
      });
    }
  }

  /**
   * Render the watchlist
   * @param {Array} quotes - Stock quote data from API
   */
  function render(quotes) {
    if (!quotes) return;

    // Convert to array if object
    if (!Array.isArray(quotes)) {
      allStocks = Object.values(quotes);
    } else {
      allStocks = quotes;
    }

    // Populate sector filter options
    populateSectorFilter();

    // Render table
    renderTable();
  }

  /**
   * Populate the sector filter dropdown
   */
  function populateSectorFilter() {
    const sectorFilterEl = document.getElementById(sectorFilterId);
    if (!sectorFilterEl) return;

    // Get unique sectors
    const sectors = [...new Set(allStocks.map(s => s.sector).filter(Boolean))].sort();

    // Keep the "All Sectors" option
    const currentValue = sectorFilterEl.value;
    sectorFilterEl.innerHTML = '<option value="">All Sectors</option>';

    sectors.forEach(sector => {
      const option = document.createElement('option');
      option.value = sector;
      option.textContent = sector;
      sectorFilterEl.appendChild(option);
    });

    // Restore selection if still valid
    if (currentValue && sectors.includes(currentValue)) {
      sectorFilterEl.value = currentValue;
    }
  }

  /**
   * Render the table with current filters and sorting
   */
  function renderTable() {
    const tbody = document.getElementById(tableBodyId);
    if (!tbody) return;

    // Filter stocks
    let filtered = allStocks.filter(stock => {
      // Search filter
      if (searchTerm) {
        const searchFields = [
          stock.symbol,
          stock.name,
          stock.sector,
          stock.sentiment
        ].filter(Boolean).join(' ').toLowerCase();

        if (!searchFields.includes(searchTerm)) {
          return false;
        }
      }

      // Sector filter
      if (sectorFilter && stock.sector !== sectorFilter) {
        return false;
      }

      return true;
    });

    // Sort stocks
    filtered = sortStocks(filtered);

    // Store filtered stocks for keyboard navigation
    filteredStocks = filtered;

    // Update count
    const countEl = document.getElementById(countId);
    if (countEl) {
      countEl.textContent = `${filtered.length} stocks`;
    }

    // Reset selection if it's out of bounds
    if (selectedIndex >= filtered.length) {
      selectedIndex = filtered.length - 1;
    }

    // Render rows
    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-state">
            <p class="empty-state__message">No stocks found matching your criteria</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = filtered.map((stock, index) => {
      let html = renderRow(stock, index);
      if (expandedSymbol === stock.symbol) {
        html += renderExpansionRow(stock);
      }
      return html;
    }).join('');

    // Animate expansion panel open
    requestAnimationFrame(() => {
      const panel = tbody.querySelector('.expansion-panel');
      if (panel) {
        panel.style.maxHeight = panel.scrollHeight + 'px';
      }
    });

    // Draw sparklines after DOM update
    requestAnimationFrame(() => {
      filtered.forEach(stock => {
        if (stock.daily_closes && stock.daily_closes.length > 1) {
          const canvas = document.getElementById(`watch-sparkline-${stock.symbol}`);
          if (canvas) {
            Charts.drawSparkline(canvas, stock.daily_closes, stock.change_percent);
          }
        }
      });
    });
  }

  /**
   * Render a single table row
   */
  function renderRow(stock, index) {
    const isPositive = stock.change_percent >= 0;
    const changeClass = isPositive ? 'change--positive' : 'change--negative';
    const sign = isPositive ? '+' : '';
    const sectorClass = App.getSectorClass(stock.sector);
    const isSelected = index === selectedIndex;

    // Format price
    const priceDisplay = App.formatCurrency(stock.price);

    // Format change
    const changeDisplay = `${sign}${(stock.change_percent || 0).toFixed(2)}%`;

    // Sentiment badge
    const sentiment = stock.sentiment || '';
    const sentimentClass = sentiment ? sentiment.toLowerCase() : 'neutral';
    const sentimentHtml = sentiment
      ? `<span class="sentiment-badge sentiment-badge--${sentimentClass}">${sentiment}</span>`
      : '';

    return `
      <tr data-symbol="${stock.symbol}" data-index="${index}" class="watchlist-row${isSelected ? ' watchlist-row--selected' : ''}" tabindex="-1">
        <td class="symbol">${stock.symbol}</td>
        <td class="name truncate" title="${stock.name || stock.symbol}">${stock.name || stock.symbol}</td>
        <td class="price">${priceDisplay}</td>
        <td class="change ${changeClass}">${changeDisplay}</td>
        <td class="sentiment-cell">${sentimentHtml}</td>
        <td class="sparkline-cell">
          <canvas id="watch-sparkline-${stock.symbol}" width="80" height="24"></canvas>
        </td>
        <td class="sector-cell">
          <span class="sector-badge sector-badge--${sectorClass}">${stock.sector || 'Other'}</span>
        </td>
      </tr>
    `;
  }

  /**
   * Render the expansion panel row shown below an expanded stock
   */
  function renderExpansionRow(stock) {
    const isEditing = editingSymbol === stock.symbol;

    if (isEditing) {
      return renderExpansionRowEdit(stock);
    }

    const sentiment = stock.sentiment || '';
    const sentimentClass = sentiment ? sentiment.toLowerCase() : '';
    const sentimentBadge = sentiment
      ? `<span class="sentiment-badge sentiment-badge--${sentimentClass}">${sentiment}</span>`
      : '<span class="expansion-panel__empty">No sentiment</span>';

    const status = stock.status || '';
    const statusClass = status ? status.toLowerCase() : '';
    const statusBadge = status
      ? `<span class="status-badge status-badge--${statusClass}">${status}</span>`
      : '';

    const thesis = stock.investment_thesis || 'No investment thesis recorded.';
    const catalysts = stock.catalysts || 'No catalysts recorded.';

    return `
      <tr class="expansion-row" data-parent-symbol="${stock.symbol}">
        <td colspan="7" class="expansion-cell">
          <div class="expansion-panel" style="max-height: 0;">
            <div class="expansion-panel__top-row">
              <div class="expansion-panel__badges">
                ${sentimentBadge} ${statusBadge}
              </div>
              <button class="expansion-panel__edit-btn" data-edit-symbol="${stock.symbol}">Edit</button>
            </div>
            <div class="expansion-panel__section">
              <div class="expansion-panel__label">Investment Thesis</div>
              <div class="expansion-panel__text">${thesis}</div>
            </div>
            <div class="expansion-panel__section">
              <div class="expansion-panel__label">Catalysts</div>
              <div class="expansion-panel__text">${catalysts}</div>
            </div>
            <div class="expansion-panel__bottom-row">
              <button class="expansion-panel__details-link" data-parent-symbol="${stock.symbol}">
                View Full Details
              </button>
              <button class="expansion-panel__remove-btn" data-remove-symbol="${stock.symbol}" title="Remove from watchlist">Remove</button>
            </div>
          </div>
        </td>
      </tr>
    `;
  }

  /**
   * Render the expansion panel in edit mode
   */
  function renderExpansionRowEdit(stock) {
    const sentimentOptions = ['', ...SENTIMENTS].map(s => {
      const selected = (stock.sentiment || '') === s ? 'selected' : '';
      const label = s || 'None';
      return `<option value="${s}" ${selected}>${label}</option>`;
    }).join('');

    const statusOptions = STATUSES.map(s => {
      const selected = (stock.status || 'Watching') === s ? 'selected' : '';
      return `<option value="${s}" ${selected}>${s}</option>`;
    }).join('');

    const escapeHtml = (str) => (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

    return `
      <tr class="expansion-row expansion-row--editing" data-parent-symbol="${stock.symbol}">
        <td colspan="7" class="expansion-cell">
          <div class="expansion-panel" style="max-height: 0;">
            <div class="form-row" style="margin-bottom: var(--space-md);">
              <div class="form-group" style="margin-bottom: 0;">
                <label class="form-label">Sentiment</label>
                <select class="form-select" id="edit-sentiment-${stock.symbol}">
                  ${sentimentOptions}
                </select>
              </div>
              <div class="form-group" style="margin-bottom: 0;">
                <label class="form-label">Status</label>
                <select class="form-select" id="edit-status-${stock.symbol}">
                  ${statusOptions}
                </select>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Investment Thesis</label>
              <textarea class="form-textarea" id="edit-thesis-${stock.symbol}" rows="3">${escapeHtml(stock.investment_thesis)}</textarea>
            </div>
            <div class="form-group">
              <label class="form-label">Catalysts</label>
              <textarea class="form-textarea" id="edit-catalysts-${stock.symbol}" rows="2">${escapeHtml(stock.catalysts)}</textarea>
            </div>
            <div class="expansion-panel__edit-actions">
              <button class="btn" data-cancel-symbol="${stock.symbol}">Cancel</button>
              <button class="btn btn--primary" data-save-symbol="${stock.symbol}">Save</button>
            </div>
          </div>
        </td>
      </tr>
    `;
  }

  /**
   * Handle removing (archiving) a stock from the watchlist
   */
  async function removeStock(symbol) {
    if (!confirm(`Remove ${symbol} from your watchlist?`)) return;

    try {
      await API.deleteTicker(symbol);

      // Remove from local data
      allStocks = allStocks.filter(s => s.symbol !== symbol);
      expandedSymbol = null;
      editingSymbol = null;
      renderTable();
      App.showToast(`${symbol} removed from watchlist`, 'success');
    } catch (error) {
      App.showToast(`Failed to remove ${symbol}: ${error.message}`, 'error');
    }
  }

  /**
   * Handle saving edited metadata
   */
  async function saveEdit(symbol) {
    const stock = allStocks.find(s => s.symbol === symbol);
    if (!stock) return;

    const sentiment = document.getElementById(`edit-sentiment-${symbol}`)?.value || '';
    const status = document.getElementById(`edit-status-${symbol}`)?.value || 'Watching';
    const thesis = document.getElementById(`edit-thesis-${symbol}`)?.value || '';
    const catalysts = document.getElementById(`edit-catalysts-${symbol}`)?.value || '';

    // Find the save button and show loading state
    const saveBtn = document.querySelector(`[data-save-symbol="${symbol}"]`);
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';
    }

    try {
      await API.updateTicker(symbol, {
        sentiment,
        status,
        investment_thesis: thesis,
        catalysts,
      });

      // Update local data immediately
      stock.sentiment = sentiment;
      stock.status = status;
      stock.investment_thesis = thesis;
      stock.catalysts = catalysts;

      editingSymbol = null;
      renderTable();
      App.showToast(`${symbol} updated`, 'success');
    } catch (error) {
      App.showToast(`Failed to update ${symbol}: ${error.message}`, 'error');
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
      }
    }
  }

  /**
   * Toggle the expansion panel for a given stock symbol
   */
  function toggleExpansion(symbol) {
    if (expandedSymbol === symbol) {
      expandedSymbol = null;
    } else {
      expandedSymbol = symbol;
    }
    renderTable();
  }

  /**
   * Sort stocks by current sort field and direction
   */
  function sortStocks(stocks) {
    const { field, direction } = currentSort;
    const modifier = direction === 'asc' ? 1 : -1;

    return [...stocks].sort((a, b) => {
      let aVal, bVal;

      switch (field) {
        case 'symbol':
          aVal = a.symbol || '';
          bVal = b.symbol || '';
          return aVal.localeCompare(bVal) * modifier;

        case 'name':
          aVal = a.name || '';
          bVal = b.name || '';
          return aVal.localeCompare(bVal) * modifier;

        case 'price':
          aVal = a.price || 0;
          bVal = b.price || 0;
          return (aVal - bVal) * modifier;

        case 'change':
          aVal = a.change_percent || 0;
          bVal = b.change_percent || 0;
          return (aVal - bVal) * modifier;

        case 'sector':
          aVal = a.sector || '';
          bVal = b.sector || '';
          return aVal.localeCompare(bVal) * modifier;

        case 'sentiment':
          aVal = a.sentiment || '';
          bVal = b.sentiment || '';
          return aVal.localeCompare(bVal) * modifier;

        default:
          return 0;
      }
    });
  }

  /**
   * Update sort indicator icons in table headers
   */
  function updateSortIndicators() {
    const table = document.getElementById('watchlist-table');
    if (!table) return;

    table.querySelectorAll('th[data-sort]').forEach(th => {
      const field = th.dataset.sort;
      const icon = th.querySelector('.sort-icon');

      if (field === currentSort.field) {
        th.classList.add('sorted');
        if (icon) {
          icon.innerHTML = currentSort.direction === 'asc' ? '&#9650;' : '&#9660;';
        }
      } else {
        th.classList.remove('sorted');
        if (icon) {
          icon.innerHTML = '';
        }
      }
    });

    // Also update the sort select if it exists
    const sortSelect = document.getElementById(sortSelectId);
    if (sortSelect) {
      sortSelect.value = currentSort.field;
    }
  }

  /**
   * Simple debounce utility
   */
  function debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  /**
   * Render loading state
   */
  function renderLoading() {
    const tbody = document.getElementById(tableBodyId);
    if (!tbody) return;

    tbody.innerHTML = Array(10).fill(null).map(() => `
      <tr class="loading">
        <td><span class="skeleton skeleton--text" style="width: 50px;"></span></td>
        <td><span class="skeleton skeleton--text" style="width: 150px;"></span></td>
        <td><span class="skeleton skeleton--text" style="width: 70px;"></span></td>
        <td><span class="skeleton skeleton--text" style="width: 60px;"></span></td>
        <td><span class="skeleton skeleton--text" style="width: 60px;"></span></td>
        <td><span class="skeleton skeleton--sparkline"></span></td>
        <td><span class="skeleton skeleton--text" style="width: 80px;"></span></td>
      </tr>
    `).join('');
  }

  /**
   * Set the selected row index and update UI
   */
  function setSelectedIndex(index) {
    // Clamp to valid range
    if (filteredStocks.length === 0) {
      selectedIndex = -1;
      return;
    }

    selectedIndex = Math.max(0, Math.min(index, filteredStocks.length - 1));

    // Update row classes
    const tbody = document.getElementById(tableBodyId);
    if (!tbody) return;

    tbody.querySelectorAll('.watchlist-row').forEach((row, i) => {
      row.classList.toggle('watchlist-row--selected', i === selectedIndex);
    });

    // Scroll selected row into view
    const selectedRow = tbody.querySelector('.watchlist-row--selected');
    if (selectedRow) {
      selectedRow.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  /**
   * Move selection up (and auto-expand the new row)
   */
  function selectPrevious() {
    if (selectedIndex <= 0) {
      setSelectedIndex(filteredStocks.length - 1);
    } else {
      setSelectedIndex(selectedIndex - 1);
    }
    // Auto-expand the newly selected row
    if (selectedIndex >= 0 && selectedIndex < filteredStocks.length) {
      expandedSymbol = filteredStocks[selectedIndex].symbol;
      renderTable();
    }
  }

  /**
   * Move selection down (and auto-expand the new row)
   */
  function selectNext() {
    if (selectedIndex >= filteredStocks.length - 1) {
      setSelectedIndex(0);
    } else {
      setSelectedIndex(selectedIndex + 1);
    }
    // Auto-expand the newly selected row
    if (selectedIndex >= 0 && selectedIndex < filteredStocks.length) {
      expandedSymbol = filteredStocks[selectedIndex].symbol;
      renderTable();
    }
  }

  /**
   * Open the detail modal for the selected stock
   */
  function openSelected() {
    if (selectedIndex >= 0 && selectedIndex < filteredStocks.length) {
      const stock = filteredStocks[selectedIndex];
      if (stock && StockDetailComponent) {
        StockDetailComponent.open(stock);
      }
    }
  }

  /**
   * Clear the current selection
   */
  function clearSelection() {
    selectedIndex = -1;
    const tbody = document.getElementById(tableBodyId);
    if (tbody) {
      tbody.querySelectorAll('.watchlist-row--selected').forEach(row => {
        row.classList.remove('watchlist-row--selected');
      });
    }
  }

  /**
   * Get the currently selected stock
   */
  function getSelectedStock() {
    if (selectedIndex >= 0 && selectedIndex < filteredStocks.length) {
      return filteredStocks[selectedIndex];
    }
    return null;
  }

  /**
   * Focus the selected row (for accessibility)
   */
  function focusSelectedRow() {
    const tbody = document.getElementById(tableBodyId);
    if (tbody) {
      const selectedRow = tbody.querySelector('.watchlist-row--selected');
      if (selectedRow) {
        selectedRow.focus();
      }
    }
  }

  /**
   * Get all filtered stocks
   */
  function getFilteredStocks() {
    return filteredStocks;
  }

  /**
   * Toggle edit mode on the currently expanded row
   */
  function toggleEdit() {
    if (!expandedSymbol) return;
    if (editingSymbol === expandedSymbol) {
      editingSymbol = null;
    } else {
      editingSymbol = expandedSymbol;
    }
    renderTable();
  }

  /**
   * Add a single stock optimistically (before full refresh)
   */
  function addStock(stock) {
    allStocks.push(stock);
    renderTable();
  }

  // Initialize when DOM is ready
  document.addEventListener('DOMContentLoaded', init);

  return {
    render,
    renderLoading,
    selectPrevious,
    selectNext,
    openSelected,
    clearSelection,
    getSelectedStock,
    focusSelectedRow,
    getFilteredStocks,
    setSelectedIndex,
    addStock,
    toggleEdit
  };
})();
