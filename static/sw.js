self.addEventListener("install", event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open("rental-cache-v1").then(cache =>
      cache.addAll([
        "/",
        "/login",
        "/register"
      ])
    )
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", event => {
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
const CACHE_NAME = "rental-cache-v2";
const OFFLINE_URL = "/offline";

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      cache.addAll([
        "/",
        "/login",
        "/register",
        OFFLINE_URL
      ])
    )
  );
});

self.addEventListener("fetch", event => {
  event.respondWith(
    fetch(event.request)
      .then(res => {
        const resClone = res.clone();
        caches.open(CACHE_NAME).then(cache =>
          cache.put(event.request, resClone)
        );
        return res;
      })
      .catch(() => caches.match(event.request)
        .then(res => res || caches.match(OFFLINE_URL))
      )
  );
});
