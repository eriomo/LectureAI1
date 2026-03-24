const CACHE_NAME = 'lectureai-v1.0';
const SHELL = ['/', '/manifest.json', '/icon-192.png', '/icon-512.png', '/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(SHELL).catch(()=>{})).then(()=>self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if(e.request.method!=='GET'||url.pathname.startsWith('/generate')||url.pathname.startsWith('/save')||url.pathname.startsWith('/get')||url.pathname.startsWith('/layer2')||url.pathname.startsWith('/ping')||url.pathname.startsWith('/create')||url.pathname.startsWith('/submit')||url.pathname.startsWith('/grade')||url.pathname.startsWith('/delete')||url.pathname.startsWith('/ai_')||url.pathname.startsWith('/discussion')) return;
  if(e.request.mode==='navigate'){
    e.respondWith(fetch(e.request).catch(()=>caches.match('/').then(r=>r||offlinePage())));
    return;
  }
  e.respondWith(caches.match(e.request).then(cached=>{
    if(cached) return cached;
    return fetch(e.request).then(res=>{
      if(res.ok){ const clone=res.clone(); caches.open(CACHE_NAME).then(c=>c.put(e.request,clone)); }
      return res;
    }).catch(()=>new Response('',{status:408}));
  }));
});
function offlinePage(){
  return new Response(`<!DOCTYPE html><html><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>LectureAI — Offline</title><style>body{background:#071a10;color:#ecf0ec;font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column;gap:16px;padding:20px;text-align:center;}h1{font-size:28px;color:#74c69d;}p{color:rgba(236,240,236,0.5);font-size:14px;}button{background:#2d6a4f;color:#fff;border:none;padding:12px 28px;border-radius:9px;font-size:14px;cursor:pointer;}</style></head><body><div style="width:60px;height:60px;background:#2d6a4f;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:30px;font-weight:700;margin-bottom:8px;">L</div><h1>LectureAI</h1><p>You are currently offline. Please check your connection.</p><button onclick="location.reload()">Try Again</button></body></html>`,{headers:{'Content-Type':'text/html'}});
}
