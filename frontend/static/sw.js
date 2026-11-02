// No-op service worker that unregisters any stale localhost:5173 service worker from previous projects.
self.addEventListener('install', () => {
	self.skipWaiting();
});

self.addEventListener('activate', (event) => {
	event.waitUntil(
		self.registration.unregister().then(() => self.clients.matchAll()).then((clients) => {
			for (const client of clients) {
				if (client.url && 'navigate' in client) {
					client.navigate(client.url);
				}
			}
		})
	);
});
