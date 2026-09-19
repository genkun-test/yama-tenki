// 電波が切れても最後に見た画面と地図が出るようにする
const C = 'yama-tenki-v1';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  const u = e.request.url;
  if (e.request.method !== 'GET') return;
  const isApi = u.includes('open-meteo.com');
  const isPage = e.request.mode === 'navigate';
  if (isApi) return; // 天気はページ側で localStorage に持つ
  e.respondWith((async () => {
    const cache = await caches.open(C);
    const hit = await cache.match(e.request);
    if (hit && !isPage) return hit; // 地図タイル・ライブラリは手元優先
    try {
      const res = await fetch(e.request);
      if (res.ok || res.type === 'opaque') cache.put(e.request, res.clone());
      return res;
    } catch (err) {
      if (hit) return hit;
      throw err;
    }
  })());
});
