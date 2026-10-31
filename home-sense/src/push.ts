import { resolveUrl } from "./serverConfig";
async function request(path: string, body?: unknown) {
  const response = await fetch(
    resolveUrl(path),
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const value = await response.json();
  if (!response.ok) throw Error(value.error || "Notification setup failed");
  return value;
}
export async function enableBackgroundPush() {
  if (
    !window.isSecureContext ||
    !("serviceWorker" in navigator) ||
    !("PushManager" in window)
  )
    throw Error(
      "This browser needs supported push notifications and a secure connection.",
    );
  const status = await request("/api/push/status");
  if (!status.configured)
    throw Error("Background delivery is not configured on this workspace yet.");
  if (!status.enrolled)
    throw Error(
      "Create a workspace password before enabling background delivery.",
    );
  const permission = await Notification.requestPermission();
  if (permission !== "granted")
    throw Error("Notification permission was not granted.");
  const registration =
    await navigator.serviceWorker.register("/push-worker.js");
  await navigator.serviceWorker.ready;
  const encoded = status.publicKey.replace(/-/g, "+").replace(/_/g, "/");
  const key = Uint8Array.from(
    atob(encoded + "=".repeat((4 - (encoded.length % 4)) % 4)),
    (c) => c.charCodeAt(0),
  );
  const subscription =
    (await registration.pushManager.getSubscription()) ||
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: key,
    }));
  await request("/api/push/subscribe", subscription.toJSON());
  return "This browser’s subscription is saved. Actual delivery has not been verified.";
}
export async function disableBackgroundPush() {
  const registration = await navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager.getSubscription();
  if (subscription) {
    await request("/api/push/unsubscribe", { endpoint: subscription.endpoint });
    await subscription.unsubscribe();
  }
  return "Background notifications disabled for this browser.";
}
