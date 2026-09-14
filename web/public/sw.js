/**
 * Service worker: what makes the app installable and usable in a basement gym
 * with no signal.
 *
 * Three caching rules, chosen by what each kind of request costs to be wrong:
 *
 * - App shell: cache-first. It changes only on deploy, and a stale shell for
 *   one load is better than a blank screen.
 * - Exercise media: cache-first with a cap. The GIFs are immutable and heavy,
 *   so re-fetching them is pure waste.
 * - API calls: network-first, falling back to the last good response. Fresh
 *   data when there is a connection; something rather than nothing when there
 *   is not.
 *
 * Writes are never cached or replayed here — the app's own offline queue owns
 * that, because it knows which requests are safe to retry.
 */

const VERSION = 'v1';
const SHELL_CACHE = `shell-${VERSION}`;
const MEDIA_CACHE = `media-${VERSION}`;
const API_CACHE = `api-${VERSION}`;

const SHELL_ASSETS = ['/', '/index.html', '/manifest.webmanifest', '/icon.svg'];

// Roughly the media for a few blocks' worth of exercises.
const MEDIA_LIMIT = 400;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // A single missing asset must not fail the whole install.
      .then((cache) => Promise.allSettled(SHELL_ASSETS.map((url) => cache.add(url))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  const keep = new Set([SHELL_CACHE, MEDIA_CACHE, API_CACHE]);
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(names.filter((name) => !keep.has(name)).map((name) => caches.delete(name))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/images/') || url.pathname.startsWith('/videos/')) {
    event.respondWith(cacheFirst(request, MEDIA_CACHE, MEDIA_LIMIT));
    return;
  }

  if (url.pathname.startsWith('/v1/')) {
    // Never cache anything account-specific: a shared device would otherwise
    // serve one person's history to the next.
    const isPrivate =
      url.pathname.startsWith('/v1/auth/') ||
      url.pathname.startsWith('/v1/workouts/') ||
      url.pathname.startsWith('/v1/programs');
    event.respondWith(isPrivate ? fetch(request) : networkFirst(request, API_CACHE));
    return;
  }

  if (request.mode === 'navigate') {
    // A client-side router owns every path, so any navigation resolves to the
    // shell rather than a 404 from the server.
    event.respondWith(
      fetch(request).catch(() =>
        caches.match('/index.html').then((cached) => cached ?? Response.error()),
      ),
    );
    return;
  }

  event.respondWith(cacheFirst(request, SHELL_CACHE));
});

async function cacheFirst(request, cacheName, limit) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
      if (limit) await trim(cache, limit);
    }
    return response;
  } catch (error) {
    if (cached) return cached;
    throw error;
  }
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

/** Oldest-first eviction; the cache API keeps insertion order. */
async function trim(cache, limit) {
  const keys = await cache.keys();
  if (keys.length <= limit) return;
  await Promise.all(keys.slice(0, keys.length - limit).map((key) => cache.delete(key)));
}

/**
 * Push notifications.
 *
 * The payload is whatever app/notify.py sent: a title, a body, a url to open
 * and the category it came from. Everything is defensive — a malformed or
 * empty push must still show something rather than throwing inside the
 * service worker, where nobody would ever see the error.
 */
self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { body: event.data ? event.data.text() : '' };
  }

  const title = payload.title || 'Training';
  const options = {
    body: payload.body || '',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    // The category is the tag, so a second reminder replaces the first
    // rather than stacking two of the same thing in the shade.
    tag: payload.category || 'general',
    renotify: false,
    data: { url: payload.url || '/' },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

/**
 * Tapping a notification opens the screen it is about.
 *
 * An already-open tab is focused and navigated rather than duplicated —
 * opening a second copy of an installed app is disorienting.
 */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || '/', self.location.origin);

  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((windows) => {
        for (const client of windows) {
          if (new URL(client.url).origin === target.origin && 'focus' in client) {
            client.navigate(target.href);
            return client.focus();
          }
        }
        return self.clients.openWindow(target.href);
      }),
  );
});
