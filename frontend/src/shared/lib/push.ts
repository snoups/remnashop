import { readStorage, removeStorage, writeStorage } from "@shared/lib/safe-storage";

// `shared` can't import entities, so the API calls come in as an argument
export interface PushApi {
  getPublicKey: () => Promise<string | null>;
  subscribe: (body: { endpoint: string; keys: { p256dh: string; auth: string } }) => Promise<unknown>;
  listEndpoints: () => Promise<{ id: number; endpoint: string }[]>;
  remove: (id: number) => Promise<void>;
}

export type PushSupport = "ready" | "unsupported" | "ios-needs-install";
export type EnablePushResult = "subscribed" | "denied" | "not-configured" | "failed";
export type ServiceWorkerMessage = { type: "notification" } | { type: "navigate"; url: string };

// set when the admin switched push off here, so the silent heal leaves it off
const OPT_OUT_KEY = "remnashop_push_optout";

export function detectPushSupport(): PushSupport {
  if ("serviceWorker" in navigator && "PushManager" in window && "Notification" in window) return "ready";
  // iOS exposes push only to a dashboard added to the Home Screen
  return /iphone|ipad|ipod/i.test(navigator.userAgent) ? "ios-needs-install" : "unsupported";
}

export function registerServiceWorker(): void {
  if ("serviceWorker" in navigator) void navigator.serviceWorker.register("/sw.js").catch(() => undefined);
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
}

function hasKey(subscription: PushSubscription, publicKey: string): boolean {
  const current = subscription.options.applicationServerKey;
  // some browsers hide it; then keep the endpoint rather than churn it on every load
  if (!current) return true;
  const expected = keyBytes(publicKey);
  const actual = new Uint8Array(current);
  return actual.length === expected.length && actual.every((byte, i) => byte === expected[i]);
}

async function browserSubscription(): Promise<PushSubscription | null> {
  if (detectPushSupport() !== "ready") return null;
  // not `ready`: it never settles when sw.js failed to register
  const registration = await navigator.serviceWorker.getRegistration();
  return (await registration?.pushManager.getSubscription()) ?? null;
}

export async function currentPushEndpoint(): Promise<string | null> {
  return (await browserSubscription())?.endpoint ?? null;
}

export async function enablePush(api: PushApi): Promise<EnablePushResult> {
  if ((await Notification.requestPermission()) !== "granted") return "denied";
  const publicKey = await api.getPublicKey();
  if (!publicKey) return "not-configured";
  let subscription: PushSubscription | null;
  try {
    const registration = await navigator.serviceWorker.ready;
    subscription = await registration.pushManager.getSubscription();
    if (subscription && !hasKey(subscription, publicKey)) {
      await subscription.unsubscribe();
      subscription = null;
    }
    subscription ??= await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes(publicKey),
    });
  } catch {
    return "failed";
  }
  // a server refusal propagates: the caller shows its own message
  const json = subscription.toJSON();
  await api.subscribe({
    endpoint: subscription.endpoint,
    keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
  });
  removeStorage(OPT_OUT_KEY);
  return "subscribed";
}

export async function disablePush(api: PushApi, { optOut }: { optOut: boolean }): Promise<void> {
  if (optOut) writeStorage(OPT_OUT_KEY, "1");
  const subscription = await browserSubscription();
  if (!subscription) return;
  try {
    const own = (await api.listEndpoints()).find((item) => item.endpoint === subscription.endpoint);
    if (own) await api.remove(own.id);
  } finally {
    await subscription.unsubscribe();
  }
}

// once per dashboard load: re-registers a subscription the server dropped
// (key rotation, pruning) without asking, unless the admin switched push off here
export async function healPushSubscription(api: PushApi): Promise<void> {
  if (detectPushSupport() !== "ready" || Notification.permission !== "granted") return;
  if (readStorage(OPT_OUT_KEY) === "1") return;
  const publicKey = await api.getPublicKey();
  if (!publicKey) return;
  const subscription = await browserSubscription();
  if (subscription && hasKey(subscription, publicKey)) {
    const known = (await api.listEndpoints()).some((item) => item.endpoint === subscription.endpoint);
    if (known) return;
  }
  await enablePush(api);
}

export function onServiceWorkerMessage(handler: (message: ServiceWorkerMessage) => void): () => void {
  if (!("serviceWorker" in navigator)) return () => undefined;
  const listener = (event: MessageEvent<ServiceWorkerMessage>) => handler(event.data);
  navigator.serviceWorker.addEventListener("message", listener);
  return () => navigator.serviceWorker.removeEventListener("message", listener);
}
