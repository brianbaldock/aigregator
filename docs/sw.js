// AIgregator service worker — minimal cache-first for assets, network-first for HTML
const CACHE = "aigregator-64a7949e7a";
const ASSETS = [
  "./",
  "./index.html",
  "./archive.html",
  "./about.html",
  "./assets/base.css",
  "./assets/themes.css",
  "./assets/terminal.css",
  "./assets/app.js",
  "./assets/aigregator-logo.png",
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS).catch(() => {})));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Network-first for HTML so users see fresh digests
  if (req.headers.get("accept")?.includes("text/html")) {
    e.respondWith(
      fetch(req).then(r => {
        const copy = r.clone();
        caches.open(CACHE).then(c => c.put(req, copy));
        return r;
      }).catch(() => caches.match(req).then(c => c || caches.match("./index.html")))
    );
    return;
  }
  // Cache-first for everything else
  e.respondWith(
    caches.match(req).then(c => c || fetch(req).then(r => {
      const copy = r.clone();
      if (r.ok) caches.open(CACHE).then(c => c.put(req, copy));
      return r;
    }))
  );
});
