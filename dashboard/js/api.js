/**
 * Stock Monitor Dashboard - API Client
 * Handles all API calls to the backend with caching
 */

const API = (() => {
  const BASE_URL = 'http://localhost:5001/api';
  const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

  // In-memory cache
  const cache = new Map();

  /**
   * Get cached data if still valid
   */
  function getFromCache(key) {
    const cached = cache.get(key);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data;
    }
    return null;
  }

  /**
   * Store data in cache
   */
  function setCache(key, data) {
    cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  /**
   * Clear all cached data
   */
  function clearCache() {
    cache.clear();
  }

  /**
   * Make API request with error handling
   */
  async function request(endpoint, options = {}) {
    const cacheKey = endpoint;

    // Check cache first (unless forced refresh)
    if (!options.forceRefresh) {
      const cached = getFromCache(cacheKey);
      if (cached) {
        console.log(`[API] Cache hit: ${endpoint}`);
        return cached;
      }
    }

    console.log(`[API] Fetching: ${endpoint}`);

    try {
      const response = await fetch(`${BASE_URL}${endpoint}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        ...options
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setCache(cacheKey, data);
      return data;

    } catch (error) {
      console.error(`[API] Error fetching ${endpoint}:`, error);
      throw error;
    }
  }

  /**
   * Fetch all watchlist quotes
   */
  async function getQuotes(forceRefresh = false) {
    return request('/quotes', { forceRefresh });
  }

  /**
   * Fetch sector performance data
   */
  async function getSectors(forceRefresh = false) {
    return request('/sectors', { forceRefresh });
  }

  /**
   * Fetch top movers (gainers/losers)
   */
  async function getMovers(forceRefresh = false) {
    return request('/movers', { forceRefresh });
  }

  /**
   * Fetch market indices
   */
  async function getIndices(forceRefresh = false) {
    return request('/indices', { forceRefresh });
  }

  /**
   * Fetch latest news
   */
  async function getNews(forceRefresh = false) {
    return request('/news', { forceRefresh });
  }

  /**
   * Fetch all dashboard data in ONE request (fastest)
   */
  async function getAllData(forceRefresh = false) {
    const cacheKey = '/all';

    // Check cache first
    if (!forceRefresh) {
      const cached = getFromCache(cacheKey);
      if (cached) {
        console.log('[API] Cache hit: /all');
        return cached;
      }
    }

    console.log('[API] Fetching: /all');

    try {
      const response = await fetch(`${BASE_URL}/all`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      // Check if server is still loading
      if (data.loading && !data.quotes) {
        console.log('[API] Server still loading data...');
        return {
          quotes: {},
          sectors: [],
          movers: { gainers: [], losers: [] },
          indices: {},
          loading: true,
          timestamp: new Date().toISOString()
        };
      }

      setCache(cacheKey, data);
      return data;

    } catch (error) {
      console.error('[API] Error fetching /all:', error);
      throw error;
    }
  }

  /**
   * Check if server data is ready
   */
  async function checkHealth() {
    try {
      const response = await fetch(`${BASE_URL}/health`);
      const data = await response.json();
      return data;
    } catch (error) {
      return { status: 'error', cache_ready: false };
    }
  }

  return {
    getQuotes,
    getSectors,
    getMovers,
    getIndices,
    getNews,
    getAllData,
    checkHealth,
    clearCache
  };
})();
