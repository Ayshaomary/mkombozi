// MUKOMBOZI service worker: lets the installed app open and show data without internet.
//
// - The app itself (index.html and the files in /assets/) is kept on the phone.
// - Every successful GET from the API is kept too, and shown when the phone is offline, marked with
//   the X-Mukombozi-Offline header so the app knows the server wasn't reached.
//   It is deleted on logout (see lib/outbox.js), so the next user can't see it.
// - Sending data (POST, PATCH, DELETE) is never handled here; offline sales and expenses wait
//   in the outbox instead (lib/outbox.js) and are sent when the internet returns.

const APP_CACHE = 'mukombozi-app-v1'
const API_CACHE = 'mukombozi-api'

const assetPaths = (html) => [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map((match) => match[1])

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(APP_CACHE)
      const response = await fetch('/index.html', { cache: 'no-store' })
      await saveShell(response)
      await cache.addAll(['/favicon.svg', '/manifest.webmanifest', '/icon-192.png'])
      await self.skipWaiting()
    })(),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) {
        if (key.startsWith('mukombozi-app-') && key !== APP_CACHE) await caches.delete(key)
      }
      await self.clients.claim()
    })(),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin) return

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(apiNetworkFirst(request))
  } else if (request.mode === 'navigate') {
    event.respondWith(pageNetworkFirst(request))
  } else if (url.pathname.startsWith('/assets/')) {
    // File names in /assets/ change with every new version, so a saved copy is always right
    event.respondWith(cacheFirst(request))
  } else {
    event.respondWith(staleWhileRevalidate(request))
  }
})

// Saves index.html and the app files it uses, and forgets files of older versions
async function saveShell(response) {
  const cache = await caches.open(APP_CACHE)
  const html = await response.text()
  await cache.put('/index.html', new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }))
  const keep = new Set(assetPaths(html))
  await cache.addAll([...keep])
  for (const saved of await cache.keys()) {
    const path = new URL(saved.url).pathname
    if (path.startsWith('/assets/') && !keep.has(path)) await cache.delete(saved)
  }
}

async function pageNetworkFirst(request) {
  try {
    const response = await fetch(request)
    // Every page of the app is index.html (React shows the right page)
    if (response.ok) saveShell(response.clone()).catch(() => {})
    return response
  } catch {
    return (await caches.match('/index.html', { cacheName: APP_CACHE })) || Response.error()
  }
}

async function apiNetworkFirst(request) {
  const cache = await caches.open(API_CACHE)
  try {
    const response = await fetch(request)
    if (response.ok) cache.put(request, response.clone()).catch(() => {})
    return response
  } catch {
    // Offline: the last answer we got, or a network error the app already knows how to show
    const saved = await cache.match(request, { ignoreVary: true })
    if (!saved) return Response.error()
    const headers = new Headers(saved.headers)
    headers.set('X-Mukombozi-Offline', '1')
    return new Response(saved.body, { status: saved.status, statusText: saved.statusText, headers })
  }
}

async function cacheFirst(request) {
  const saved = await caches.match(request)
  if (saved) return saved
  const response = await fetch(request)
  if (response.ok) (await caches.open(APP_CACHE)).put(request, response.clone())
  return response
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(APP_CACHE)
  const saved = await cache.match(request)
  const fresh = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone())
      return response
    })
    .catch(() => saved || Response.error())
  return saved || fresh
}
