const CACHE_NAME = 'kiosk-cache-v5';
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

// Assets to cache aggressively on install
const PRECACHE_URLS = [
    '/static/offline.html',
    '/static/app.css',
    '/static/manifest.json',
    '/static/logo.png',
    '/static/ka-ching.wav'
];

// Install Event: Precache core assets
self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(PRECACHE_URLS))
    );
});

// Activate Event: Cleanup old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch Event: Time-based Stale-While-Revalidate & Offline Fallback
self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);

    // 1. Static Assets (CSS, JS, Images in /static/) -> Time-based Stale-While-Revalidate
    if (request.method === 'GET' && url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.open(CACHE_NAME).then(async cache => {
                const cachedResponse = await cache.match(request);

                const fetchPromise = fetch(request).then(networkResponse => {
                    if (networkResponse && networkResponse.ok) {
                        cache.put(request, networkResponse.clone());
                    }
                    return networkResponse;
                }).catch(() => {
                    // Ignore background fetch errors (we are offline)
                });

                if (cachedResponse) {
                    const dateHeader = cachedResponse.headers.get('date');
                    if (dateHeader) {
                        const age = Date.now() - new Date(dateHeader).getTime();
                        if (age < CACHE_TTL_MS) {
                            return cachedResponse;
                        }
                    }
                    // It's stale, return cached version immediately, but the fetchPromise is running
                    return cachedResponse;
                }

                // Not in cache, wait for network
                return fetchPromise;
            })
        );
        return;
    }

    // 2. Navigation Requests (HTML pages) -> Network First, fallback to offline.html
    // This catches both GET and POST requests that result in page navigation (like form submissions)
    if (request.mode === 'navigate' || (request.headers.get('accept') && request.headers.get('accept').includes('text/html'))) {
        event.respondWith(
            fetch(request).catch(error => {
                console.log('Fetch failed; returning offline page instead.', error);
                return caches.match('/static/offline.html');
            })
        );
        return;
    }

    // 3. Other requests (e.g., AJAX GET/POST) -> Network First
    if (request.method === 'GET') {
        event.respondWith(
            fetch(request).catch(() => caches.match(request))
        );
    } else {
        // For POST/PUT/DELETE AJAX, let it fail naturally if offline
        event.respondWith(fetch(request));
    }
});
