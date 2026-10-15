// Push only: no fetch handler, nothing cached (admin data is sensitive).

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(data.title || "Remnashop", {
        body: data.body || "",
        icon: "/favicon.svg",
        tag: data.tag || "remnashop",
        renotify: true,
        data: { url: data.url || "/dashboard" },
      }),
      self.clients
        .matchAll({ type: "window", includeUncontrolled: true })
        .then((clients) => clients.forEach((client) => client.postMessage({ type: "notification" }))),
    ]),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/dashboard", self.location.origin);
  // own origin only: a notification never opens another site
  const url = target.origin === self.location.origin ? target.href : new URL("/dashboard", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      const open = clients.find((client) => new URL(client.url).origin === self.location.origin);
      if (open) {
        open.postMessage({ type: "navigate", url });
        return open.focus();
      }
      return self.clients.openWindow(url);
    }),
  );
});
