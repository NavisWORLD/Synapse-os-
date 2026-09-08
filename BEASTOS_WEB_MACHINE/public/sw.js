const CACHE = 'beastos-web-v2';
const SHELL = [
  '/',
  '/styles.css',
  '/app.webmanifest',
  '/icon.svg',
  '/src/app/app.js',
  '/src/authority/client.js',
  '/src/hardware/capabilities.js',
  '/src/storage/scopes.js',
  '/src/beast/conversation.js',
  '/src/beast/conversation.css',
];
self.addEventListener('install', (event) => event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL))));
self.addEventListener('activate', (event) => event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))));
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/v1/')) return;
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request).then((response) => {
    const copy = response.clone();
    caches.open(CACHE).then((cache) => cache.put(event.request, copy));
    return response;
  }).catch(() => caches.match(event.request).then((cached) => cached || caches.match('/'))));
});
