/**
 * Stock Monitor Dashboard - Hash Router
 * Simple hash-based routing for dashboard pages
 */

const Router = (() => {
  const routes = {
    '': 'dashboard',
    '#/dashboard': 'dashboard',
    '#/history': 'history',
    '#/performance': 'performance'
  };

  function init() {
    window.addEventListener('hashchange', handleRoute);
    handleRoute();
  }

  function handleRoute() {
    const hash = window.location.hash || '';
    const page = routes[hash] || 'dashboard';

    // Hide all pages, show active
    document.querySelectorAll('.page').forEach(p => p.classList.remove('page--active'));
    const active = document.getElementById(`page-${page}`);
    if (active) active.classList.add('page--active');

    // Update nav
    document.querySelectorAll('.nav__tab').forEach(t => t.classList.remove('nav__tab--active'));
    const activeTab = document.querySelector(`[data-page="${page}"]`);
    if (activeTab) activeTab.classList.add('nav__tab--active');

    // Trigger page-specific init
    if (page === 'history' && typeof HistoryComponent !== 'undefined') HistoryComponent.init();
    if (page === 'performance' && typeof PerformanceComponent !== 'undefined') PerformanceComponent.init();
  }

  function getActivePage() {
    const hash = window.location.hash || '';
    return routes[hash] || 'dashboard';
  }

  return { init, getActivePage };
})();
