// Service worker de l'appli « Gestion 2K27 ».
// Objectif : l'appli s'ouvre même si le wifi coupe un instant, SANS jamais servir une vieille version
// quand on est en ligne (réseau d'abord, copie en cache seulement en secours).
// Les appels Firebase (base de données, connexion) ne passent jamais par ici.
const VERSION = 'gestion-2k27-v1';
const COQUILLE = [
  './',
  './gestion-parties.html',
  './verrouillage.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png'
];
// bibliothèques et polices : on garde une copie pour pouvoir démarrer hors connexion
const EXTERNES = ['https://www.gstatic.com/firebasejs/', 'https://fonts.googleapis.com/', 'https://fonts.gstatic.com/'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(VERSION)
      .then(cache => Promise.all(COQUILLE.map(url => cache.add(new Request(url, { cache: 'reload' })).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(noms => Promise.all(noms.filter(n => n !== VERSION).map(n => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (url.origin === self.location.origin){
    event.respondWith(
      fetch(req, { cache: 'no-cache' })
        .then(rep => {
          if (rep && rep.ok){
            const copie = rep.clone();
            caches.open(VERSION).then(c => c.put(req, copie));
          }
          return rep;
        })
        .catch(() => caches.match(req, { ignoreSearch: true }).then(r => r || caches.match('./gestion-parties.html')))
    );
    return;
  }

  if (EXTERNES.some(prefixe => req.url.startsWith(prefixe))){
    event.respondWith(
      caches.match(req).then(enCache => {
        const reseau = fetch(req).then(rep => {
          if (rep && (rep.ok || rep.type === 'opaque')){
            const copie = rep.clone();
            caches.open(VERSION).then(c => c.put(req, copie));
          }
          return rep;
        }).catch(() => enCache);
        return enCache || reseau;
      })
    );
  }
});
