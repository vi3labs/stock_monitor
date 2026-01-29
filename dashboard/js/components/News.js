/**
 * Stock Monitor Dashboard - News Feed Component
 * Renders market news with source, time, and external links
 */

const NewsComponent = (() => {
  const containerId = 'news-list';

  /**
   * Render the news feed
   * @param {Array} news - News items from API
   */
  function render(news) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!news || news.length === 0) {
      container.innerHTML = renderEmptyState();
      return;
    }

    // Limit to 10 most recent news items
    const items = news.slice(0, 10);

    container.innerHTML = items.map((item, index) => renderNewsItem(item, index)).join('');
  }

  /**
   * Render a single news item
   */
  function renderNewsItem(item, index) {
    const timeAgo = formatRelativeTime(item.published || item.date);
    const source = item.source || 'News';
    const url = item.url || item.link || '#';
    const title = item.title || 'Untitled';

    // Add animation delay based on index
    const animationDelay = index * 50;

    return `
      <a href="${escapeHtml(url)}"
         target="_blank"
         rel="noopener noreferrer"
         class="news-item animate-slide-in"
         style="animation-delay: ${animationDelay}ms;">
        <div class="news-item__content">
          <h4 class="news-item__title">${escapeHtml(title)}</h4>
          <div class="news-item__meta">
            <span class="news-item__source">${escapeHtml(source)}</span>
            <span class="news-item__separator">&#8226;</span>
            <span class="news-item__time">${timeAgo}</span>
          </div>
        </div>
        <svg class="news-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
          <polyline points="15 3 21 3 21 9"/>
          <line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
      </a>
    `;
  }

  /**
   * Format a date as relative time (e.g., "2h ago")
   */
  function formatRelativeTime(dateString) {
    if (!dateString) return 'Recently';

    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) {
      return 'Just now';
    } else if (diffMinutes < 60) {
      return `${diffMinutes}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return `${diffDays}d ago`;
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
  }

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Render empty state
   */
  function renderEmptyState() {
    return `
      <div class="empty-state" style="padding: var(--space-lg);">
        <p class="empty-state__message">No news available</p>
      </div>
    `;
  }

  /**
   * Render loading state
   */
  function renderLoading() {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = Array(5).fill(null).map(() => `
      <div class="news-item loading">
        <div class="news-item__content">
          <div class="skeleton skeleton--text" style="width: 90%; height: 1.1em;"></div>
          <div class="news-item__meta">
            <span class="skeleton skeleton--text" style="width: 60px;"></span>
          </div>
        </div>
      </div>
    `).join('');
  }

  return {
    render,
    renderLoading
  };
})();
