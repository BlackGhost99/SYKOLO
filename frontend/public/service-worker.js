/* YEM privacy-preserving PWA: never persist login pages, school data or API responses. */
const VERSION="yem-public-v1";
const ASSETS=["/offline.html","/manifest.webmanifest","/icons/icon-192.png","/icons/icon-512.png"];
self.addEventListener("install",event=>{
  event.waitUntil(caches.open(VERSION).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==VERSION).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});
self.addEventListener("fetch",event=>{
  const request=event.request;
  if(request.method!=="GET")return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;
  // Private pages/JSON/receipts must be read from the server on every request.
  if(url.pathname.startsWith("/api/")||url.pathname.startsWith("/healthz")||url.pathname.startsWith("/readyz"))return;
  if(request.mode==="navigate"){
    event.respondWith(fetch(request).catch(()=>caches.match("/offline.html")));
    return;
  }
  if(url.pathname.startsWith("/assets/")||ASSETS.includes(url.pathname)){
    event.respondWith(caches.match(request).then(hit=>hit||fetch(request).then(response=>{
      if(response.ok){const copy=response.clone();caches.open(VERSION).then(cache=>cache.put(request,copy));}
      return response;
    })));
  }
});
