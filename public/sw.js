// NETRA Surveillance PWA Service Worker
// Handles push notifications and offline caching

const CACHE_NAME = 'netra-v1';
const STATIC_ASSETS = ['/', '/index.html'];

// ── Install ──────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// ── Activate ─────────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch (network-first for API, cache-first for statics) ───────────────────
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  // Always network for API calls
  if (url.pathname.startsWith('/api/') || url.pathname === '/video_feed') return;
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});

// ── Push Notifications ────────────────────────────────────────────────────────
self.addEventListener('push', event => {
  let data = {};
  try { data = event.data.json(); } catch (e) { data = { title: '🚨 Alert', body: event.data?.text() || 'Border alert triggered' }; }

  const title = data.title || '🚨 BORDER ALERT';
  const options = {
    body: data.body || 'Threat detected',
    icon: data.icon || '/icon-192.png',
    badge: data.badge || '/badge-72.png',
    tag: data.tag || 'netra-alert',
    renotify: data.renotify ?? true,
    requireInteraction: true,
    vibrate: [200, 100, 200, 100, 400],
    data: data.data || {},
    actions: [
      { action: 'view', title: '📋 View Alert' },
      { action: 'live', title: '📹 Live Feed' },
      { action: 'dismiss', title: 'Dismiss' }
    ]
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// ── Notification Click ────────────────────────────────────────────────────────
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const action = event.action;
  const notifData = event.notification.data || {};
  let targetUrl = '/';

  if (action === 'live') targetUrl = '/#live';
  else if (action === 'view' || action === '') targetUrl = '/#alerts';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      for (const client of clientList) {
        if ('focus' in client) {
          client.postMessage({ type: 'NAVIGATE', url: targetUrl });
          return client.focus();
        }
      }
      return clients.openWindow(targetUrl);
    })
  );
});
