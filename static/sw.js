// static/sw.js
const CACHE_NAME = 'postcard-player-v1';

// Files to cache immediately so the player loads offline
const APP_SHELL = [
    '/', // Root
    // We cannot know the dynamic frame URL here, but the browser
    // will cache the visited page automatically if we handle fetch.
];

self.addEventListener('install', (event) => {
    self.skipWaiting(); // Take over immediately
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim()); // Control all open tabs
});

// Intercept network requests
self.addEventListener('fetch', (event) => {
    // We only care about GET requests
    if (event.request.method !== 'GET') return;

    event.respondWith(
        (async () => {
            // 1. Try to find it in the cache
            const cachedResponse = await caches.match(event.request);
            if (cachedResponse) {
                return cachedResponse;
            }

            // 2. If not in cache, fetch from network
            try {
                const networkResponse = await fetch(event.request);

                // 3. IMPORTANT: Cache the Kiosk HTML page dynamically
                // so it works offline next time.
                // We check if the URL contains "/player/"
                if (event.request.url.includes('/player/')) {
                    const cache = await caches.open(CACHE_NAME);
                    cache.put(event.request, networkResponse.clone());
                }

                return networkResponse;
            } catch (error) {
                // Network failed and no cache?
                // This usually only happens on the very first load if offline.
                console.error("Fetch failed; returning offline page instead.", error);
                throw error;
            }
        })()
    );
});
