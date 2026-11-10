const CACHE = 'jalanyuk-v2-5-no-google-routes' ;
const STATIC=['/','/static/index.html','/static/styles.css','/static/app.js','/static/favicon.svg','/manifest.webmanifest'];
self.addEventListener('install', event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(STATIC)).then(()=>self.skipWaiting()));});
self.addEventListener('activate', event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch', event=>{const req=event.request;if(req.method!=='GET'||new URL(req.url).origin!==self.location.origin||new URL(req.url).pathname.startsWith('/api/'))return;
  event.respondWith(fetch(req).then(response=>{if(response.ok){const copy=response.clone();caches.open(CACHE).then(c=>c.put(req,copy));}return response;}).catch(()=>caches.match(req).then(c=>c||caches.match('/'))));
});
