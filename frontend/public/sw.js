const CACHE_NAME = 'ai-crm-v2';
const STATIC_ASSETS = [
  '/',
  '/crm',
  '/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Skip API requests
  if (request.url.includes('/api/') || request.url.includes('/health')) {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        // Cache successful navigation responses
        if (request.mode === 'navigate' && response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => {
        // Offline fallback
        return caches.match(request).then((cached) => cached || caches.match('/'));
      })
  );
});
