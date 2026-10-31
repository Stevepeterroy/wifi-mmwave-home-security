self.addEventListener("push", (event) => {
  let message = {};
  try {
    message = event.data.json();
  } catch {}
  event.waitUntil(
    self.registration.showNotification(
      typeof message.title === "string" ? message.title : "Haven reminder",
      {
        body:
          typeof message.body === "string"
            ? message.body
            : "Open Haven to review.",
        icon: "/icon.svg",
        tag: typeof message.tag === "string" ? message.tag : undefined,
        requireInteraction: true,
        data: { url: "/" },
      },
    ),
  );
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clients) => {
        const existing = clients.find(
          (client) => new URL(client.url).origin === self.location.origin,
        );
        return existing ? existing.focus() : self.clients.openWindow("/");
      }),
  );
});
