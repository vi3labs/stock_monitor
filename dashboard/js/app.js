/**
 * Stock Monitor Dashboard - Main Application Controller
 * Initializes components and handles global state
 */

const App = (() => {
  // State
  let isLoading = false;
  let lastUpdate = null;
  let autoRefreshInterval = null;
  let isAutoRefreshEnabled = true;

  // Auto-refresh configuration
  const AUTO_REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes

  // DOM elements
  const elements = {
    timestamp: null,
    refreshBtn: null,
    refreshIcon: null,
    toastContainer: null,
    marketStatus: null
  };

  /**
   * Initialize the application
   */
  async function init() {
    console.log('[App] Initializing Stock Monitor Dashboard');

    // Cache DOM elements
    elements.timestamp = document.getElementById('timestamp');
    elements.refreshBtn = document.getElementById('refresh-btn');
    elements.refreshIcon = document.getElementById('refresh-icon');
    elements.toastContainer = document.getElementById('toast-container');
    elements.marketStatus = document.getElementById('market-status');

    // Set up event listeners
    setupEventListeners();

    // Wait for server to be ready, then load data
    await waitForServerAndLoad();

    // Start auto-refresh if market is open
    startAutoRefresh();

    // Update market status indicator
    updateMarketStatus();

    // Update market status every minute
    setInterval(updateMarketStatus, 60 * 1000);

    console.log('[App] Initialization complete');
  }

  /**
   * Check if the US stock market is currently open
   * Market hours: Mon-Fri 9:30 AM - 4:00 PM EST
   */
  function isMarketOpen() {
    const now = new Date();

    // Convert to EST
    const estOptions = { timeZone: 'America/New_York' };
    const estString = now.toLocaleString('en-US', estOptions);
    const estDate = new Date(estString);

    const day = estDate.getDay(); // 0 = Sunday, 6 = Saturday
    const hours = estDate.getHours();
    const minutes = estDate.getMinutes();
    const totalMinutes = hours * 60 + minutes;

    // Check if weekday (Mon = 1, Fri = 5)
    if (day === 0 || day === 6) {
      return false;
    }

    // Market open: 9:30 AM (570 min) to 4:00 PM (960 min)
    const marketOpen = 9 * 60 + 30;  // 9:30 AM = 570 minutes
    const marketClose = 16 * 60;     // 4:00 PM = 960 minutes

    return totalMinutes >= marketOpen && totalMinutes < marketClose;
  }

  /**
   * Update the market status indicator
   */
  function updateMarketStatus() {
    if (!elements.marketStatus) return;

    const open = isMarketOpen();
    elements.marketStatus.classList.toggle('market-status--open', open);
    elements.marketStatus.classList.toggle('market-status--closed', !open);
    elements.marketStatus.querySelector('.market-status__text').textContent = open ? 'Market Open' : 'Market Closed';
    elements.marketStatus.title = open ? 'US market is open (9:30 AM - 4:00 PM EST)' : 'US market is closed';
  }

  /**
   * Start auto-refresh when market is open
   */
  function startAutoRefresh() {
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
    }

    autoRefreshInterval = setInterval(() => {
      if (!isAutoRefreshEnabled) return;
      if (!document.hidden && isMarketOpen()) {
        console.log('[App] Auto-refresh triggered');
        refreshData(false);
      }
    }, AUTO_REFRESH_INTERVAL);

    console.log('[App] Auto-refresh started (every 5 minutes when market is open)');
  }

  /**
   * Stop auto-refresh
   */
  function stopAutoRefresh() {
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;
    }
    console.log('[App] Auto-refresh stopped');
  }

  /**
   * Toggle auto-refresh enabled state
   */
  function setAutoRefreshEnabled(enabled) {
    isAutoRefreshEnabled = enabled;
    console.log(`[App] Auto-refresh ${enabled ? 'enabled' : 'disabled'}`);
  }

  /**
   * Wait for the server cache to be ready, polling every 2 seconds
   */
  async function waitForServerAndLoad() {
    showToast('Connecting to server...', 'info');
    setRefreshingState(true);

    let attempts = 0;
    const maxAttempts = 60; // 2 minutes max wait

    while (attempts < maxAttempts) {
      try {
        const health = await API.checkHealth();

        if (health.cache_ready) {
          console.log('[App] Server cache ready, loading data');
          await refreshData();
          return;
        }

        if (health.status === 'ok') {
          console.log('[App] Server is loading data, waiting...');
          if (attempts === 0) {
            showToast('Server is loading market data... (this may take a minute)', 'info');
          }
        }

      } catch (error) {
        console.log('[App] Server not ready yet, retrying...');
        if (attempts === 0) {
          showToast('Waiting for API server...', 'info');
        }
      }

      // Wait 2 seconds before next attempt
      await new Promise(resolve => setTimeout(resolve, 2000));
      attempts++;
    }

    // Timeout - try to load anyway
    console.log('[App] Timeout waiting for server, attempting to load anyway');
    showToast('Server taking too long, loading partial data...', 'warning');
    await refreshData();
  }

  /**
   * Set up global event listeners
   */
  function setupEventListeners() {
    // Refresh button
    if (elements.refreshBtn) {
      elements.refreshBtn.addEventListener('click', () => refreshData(true));
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboard);

    // Pause auto-refresh when tab is hidden
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        console.log('[App] Tab hidden, pausing auto-refresh');
      } else {
        console.log('[App] Tab visible, resuming auto-refresh');
        // Refresh data when tab becomes visible if market is open
        if (isMarketOpen()) {
          refreshData(false);
        }
        updateMarketStatus();
      }
    });
  }

  /**
   * Check if an input element is focused
   */
  function isInputFocused() {
    const active = document.activeElement;
    return active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.tagName === 'SELECT');
  }

  /**
   * Handle keyboard navigation
   */
  function handleKeyboard(e) {
    // Don't handle shortcuts when modals are open (except Escape)
    const stockModalOpen = StockDetailComponent && StockDetailComponent.isModalOpen();
    const helpModalOpen = document.getElementById('keyboard-help-modal')?.classList.contains('modal-overlay--visible');

    // Escape key - close modals or clear selection
    if (e.key === 'Escape') {
      if (stockModalOpen) {
        StockDetailComponent.close();
        e.preventDefault();
        return;
      }
      if (helpModalOpen) {
        closeKeyboardHelp();
        e.preventDefault();
        return;
      }
      // Clear watchlist selection
      if (WatchlistComponent) {
        WatchlistComponent.clearSelection();
      }
      return;
    }

    // Don't handle other shortcuts when modal is open
    if (stockModalOpen || helpModalOpen) return;

    // Don't handle shortcuts when input is focused (except some special cases)
    if (isInputFocused()) {
      // Allow Escape to blur input
      if (e.key === 'Escape') {
        document.activeElement.blur();
        e.preventDefault();
      }
      return;
    }

    // Prevent default for handled keys
    let handled = true;

    switch (e.key) {
      case 'j':
      case 'ArrowDown':
        // Navigate down in watchlist
        if (WatchlistComponent) {
          WatchlistComponent.selectNext();
        }
        break;

      case 'k':
      case 'ArrowUp':
        // Navigate up in watchlist
        if (WatchlistComponent) {
          WatchlistComponent.selectPrevious();
        }
        break;

      case 'Enter':
      case 'o':
        // Open selected stock detail
        if (WatchlistComponent) {
          WatchlistComponent.openSelected();
        }
        break;

      case '/':
        // Focus search input
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
          searchInput.focus();
          e.preventDefault();
        }
        break;

      case 'r':
        // Refresh data
        if (!e.ctrlKey && !e.metaKey) {
          refreshData(true);
        } else {
          handled = false;
        }
        break;

      case '?':
        // Show keyboard shortcuts help
        showKeyboardHelp();
        break;

      default:
        handled = false;
    }

    if (handled) {
      e.preventDefault();
    }
  }

  /**
   * Show keyboard shortcuts help modal
   */
  function showKeyboardHelp() {
    const modal = document.getElementById('keyboard-help-modal');
    if (modal) {
      modal.classList.add('modal-overlay--visible');
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';

      // Set up close handlers
      const closeBtn = modal.querySelector('.modal__close');
      if (closeBtn) {
        closeBtn.onclick = closeKeyboardHelp;
      }

      modal.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
          closeKeyboardHelp();
        }
      });
    }
  }

  /**
   * Close keyboard shortcuts help modal
   */
  function closeKeyboardHelp() {
    const modal = document.getElementById('keyboard-help-modal');
    if (modal) {
      modal.classList.remove('modal-overlay--visible');
      modal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    }
  }

  /**
   * Refresh all dashboard data
   */
  async function refreshData(forceRefresh = false) {
    if (isLoading) {
      console.log('[App] Already loading, skipping refresh');
      return;
    }

    console.log('[App] Refreshing data...');
    isLoading = true;
    setRefreshingState(true);

    try {
      // Fetch all data in parallel
      const data = await API.getAllData(forceRefresh);

      // Update components
      if (data.indices) {
        IndicesComponent.render(data.indices);
      }

      if (data.sectors) {
        SectorsComponent.render(data.sectors);
      }

      if (data.quotes) {
        WatchlistComponent.render(data.quotes);
      }

      if (data.movers) {
        MoversComponent.render(data.movers);
      }

      if (data.news) {
        NewsComponent.render(data.news);
      }

      // Update timestamp
      lastUpdate = new Date();
      updateTimestamp();

      if (forceRefresh) {
        showToast('Data refreshed successfully', 'success');
      }

    } catch (error) {
      console.error('[App] Error refreshing data:', error);
      showToast('Failed to refresh data. Is the API server running?', 'error');
    } finally {
      isLoading = false;
      setRefreshingState(false);
    }
  }

  /**
   * Update the timestamp display
   */
  function updateTimestamp() {
    if (!elements.timestamp || !lastUpdate) return;

    const options = {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    };

    elements.timestamp.textContent = `Last updated: ${lastUpdate.toLocaleString('en-US', options)}`;
  }

  /**
   * Set the visual refresh state
   */
  function setRefreshingState(refreshing) {
    if (elements.refreshBtn) {
      elements.refreshBtn.disabled = refreshing;
    }
    if (elements.refreshIcon) {
      elements.refreshIcon.classList.toggle('spin', refreshing);
    }
  }

  /**
   * Show a toast notification
   */
  function showToast(message, type = 'info') {
    if (!elements.toastContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;

    elements.toastContainer.appendChild(toast);

    // Auto-remove after 3 seconds
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  /**
   * Format a number as currency
   */
  function formatCurrency(value, decimals = 2) {
    if (value === null || value === undefined) return '--';

    // Show more decimals for small values
    if (Math.abs(value) < 1) {
      decimals = 4;
    }

    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    }).format(value);
  }

  /**
   * Format a percentage
   */
  function formatPercent(value, showSign = true) {
    if (value === null || value === undefined) return '--';

    const sign = showSign && value > 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
  }

  /**
   * Format large numbers with abbreviations
   */
  function formatNumber(value) {
    if (value === null || value === undefined) return '--';

    if (value >= 1e12) {
      return `${(value / 1e12).toFixed(2)}T`;
    }
    if (value >= 1e9) {
      return `${(value / 1e9).toFixed(2)}B`;
    }
    if (value >= 1e6) {
      return `${(value / 1e6).toFixed(2)}M`;
    }
    if (value >= 1e3) {
      return `${(value / 1e3).toFixed(1)}K`;
    }

    return value.toLocaleString();
  }

  /**
   * Get sector badge class
   */
  function getSectorClass(sector) {
    if (!sector) return '';

    const normalized = sector.toLowerCase()
      .replace(/\s+/g, '-')
      .replace(/[^a-z-]/g, '');

    // Map common variations
    const sectorMap = {
      'etf-index': 'etf',
      'etf-sector': 'etf',
      'etf-dividend': 'etf',
      'etf-income': 'etf',
      'etf-thematic': 'etf',
      'crypto-etf': 'crypto'
    };

    return sectorMap[normalized] || normalized;
  }

  // Public API
  return {
    init,
    refreshData,
    showToast,
    formatCurrency,
    formatPercent,
    formatNumber,
    getSectorClass,
    isMarketOpen,
    startAutoRefresh,
    stopAutoRefresh,
    setAutoRefreshEnabled
  };
})();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
