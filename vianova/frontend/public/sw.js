/* Service worker de Vianova (PWA).
 * - Guarda en caché solo el "cascarón" de la app (HTML, JS, CSS, íconos) para abrir rápido e instalarse en el celular.
 * - NUNCA guarda respuestas de /api: los datos de salud no se almacenan en la caché del dispositivo.
 * - Muestra las notificaciones de recordatorio y abre la app al tocarlas. */
const CACHE = 'vianova-shell-v2'
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png']

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()))
})
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()))
})
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(() => caches.match('/index.html')))
    return
  }
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
      const copy = res.clone()
      caches.open(CACHE).then(c => c.put(e.request, copy))
      return res
    })))
  }
})
self.addEventListener('notificationclick', e => {
  e.notification.close()
  e.waitUntil(self.clients.matchAll({ type: 'window' }).then(list => {
    for (const c of list) if ('focus' in c) { c.navigate('/#/agenda'); return c.focus() }
    return self.clients.openWindow('/#/agenda')
  }))
})
