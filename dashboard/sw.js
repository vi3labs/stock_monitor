const CACHE_NAME = 'stock-monitor-v1';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/css/variables.css',
    '/css/base.css',
    '/css/layout.css',
    '/css/components.css',
    '/js/api.js',
    '/js/charts.js',
    '/js/components/Indices.js',
    '/js/components/Sectors.js',
    '/js/components/Watchlist.js',
    '/js/components/Movers.js',
    '/js/components/News.js',
    '/js/components/Earnings.js',
    '/js/components/StockDetail.js',
    '/js/app.js'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
            )
        )
    );
});

self.addEventListener('fetch', (event) => {
    // Network-first for API calls, cache-first for static assets
    if (event.request.url.includes('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() => caches.match(event.request))
        );
    } else {
        event.respondWith(
            caches.match(event.request).then(cached => cached || fetch(event.request))
        );
    }
});
