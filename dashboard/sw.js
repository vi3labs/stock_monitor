const CACHE_NAME = 'stock-monitor-v6';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/css/variables.css',
    '/css/base.css',
    '/css/layout.css',
    '/css/components.css',
    '/js/api.js',
    '/js/charts.js',
    '/js/router.js',
    '/js/components/Indices.js',
    '/js/components/Sectors.js',
    '/js/components/Watchlist.js',
    '/js/components/Movers.js',
    '/js/components/News.js',
    '/js/components/Earnings.js',
    '/js/components/StockDetail.js',
    '/js/components/AddTicker.js',
    '/js/components/History.js',
    '/js/components/Performance.js',
    '/js/app.js'
];

self.addEventListener('install', (event) => {
    // Skip waiting so new SW activates immediately (no stale cache issues)
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
});

self.addEventListener('activate', (event) => {
    // Claim all clients immediately so new SW handles fetches right away
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Only handle same-origin requests — don't intercept cross-origin API calls
    if (url.origin !== self.location.origin) return;

    // Network-first for API calls, cache-first for static assets
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() => caches.match(event.request))
        );
    } else {
        event.respondWith(
            caches.match(event.request).then(cached => cached || fetch(event.request))
        );
    }
});
