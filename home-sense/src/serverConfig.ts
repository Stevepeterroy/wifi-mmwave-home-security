/**
 * Server configuration for the Haven Android app.
 *
 * On Android (Capacitor), API calls cannot use relative paths because the app
 * is served from a local file:// origin. This module stores and returns the
 * base URL of the Python backend server running on the local network.
 *
 * On a regular browser (dev / PWA), this returns "" so relative paths work as before.
 */

const STORAGE_KEY = "haven_server_url";

/** Returns true when running inside a Capacitor Android native app */
export function isAndroid(): boolean {
  if (typeof window === "undefined") return false;
  // If already loaded from the server directly in a browser (e.g. http://10.91.1.112:8768),
  // no setup is needed because relative URLs work as-is.
  if (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
    return false;
  }
  // @ts-expect-error Capacitor global
  return Boolean(window.Capacitor?.isNativePlatform?.()) || /Android/i.test(navigator.userAgent);
}

export const DEFAULT_SERVER_URL = "https://catalyst-again-cylinder-plus.trycloudflare.com";

/** Get the stored server URL (e.g. "https://appointment-purpose-spencer-diesel.trycloudflare.com") */
export function getServerUrl(): string {
  if (!isAndroid()) return "";
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_SERVER_URL;
}

/** Save the server URL */
export function setServerUrl(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.replace(/\/$/, ""));
}

/** Resolve a path against the configured server URL */
export function resolveUrl(path: string): string {
  const base = getServerUrl();
  if (!base) return path;
  return base + path;
}
