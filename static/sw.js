/* Service Worker — کش هوشمند با اولویت شبکه برای JS/CSS (جلوگیری از نسخه‌های کهنه)
   استراتژی:
   - JS/CSS: network-first با fallback به کش (همیشه تازه، آفلاین هم کار می‌کند)
   - تصاویر/فونت‌ها: cache-first با به‌روزرسانی پس‌زمینه
   - HTML و API: هرگز کش نمی‌شوند
*/
var CACHE = 'academy-v3';
var CORE = [
  '/static/css/base.css',
  '/static/css/ux.css',
  '/static/css/builder.css',
  '/static/js/app.js',
  '/static/js/ux.js',
  '/static/js/builder.js',
  '/static/js/player.js'
];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return c.addAll(CORE).catch(function () { /* برخی ممکن است نباشند */ });
  }).then(function () { self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // HTML و API → هیچ‌وقت کش نشوند
  if (req.mode === 'navigate' || url.pathname.startsWith('/api') || url.pathname.startsWith('/builder/api')) return;

  if (url.pathname.startsWith('/static/')) {
    var isCode = url.pathname.endsWith('.js') || url.pathname.endsWith('.css');
    e.respondWith(caches.open(CACHE).then(function (c) {
      return c.match(req).then(function (hit) {
        if (isCode) {
          // network-first: تازگی مهم‌تر است
          return fetch(req).then(function (resp) {
            if (resp && resp.status === 200) c.put(req, resp.clone());
            return resp;
          }).catch(function () { return hit || Response.error(); });
        }
        // تصاویر/فونت: cache-first با به‌روزرسانی پس‌زمینه
        var fetchP = fetch(req).then(function (resp) {
          if (resp && resp.status === 200) c.put(req, resp.clone());
          return resp;
        }).catch(function () { return hit; });
        return hit || fetchP;
      });
    }));
  }
});
