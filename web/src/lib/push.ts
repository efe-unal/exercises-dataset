/**
 * Asking for notification permission, and registering the device.
 *
 * The prompt is a one-way door: a browser only ever asks once, and a refusal
 * can afterwards be undone only in the browser's own settings, which nobody
 * does. So this is never called on load — only from a button the athlete
 * pressed, after the app has explained what they are agreeing to.
 */

import { api } from './api';

export type PushState =
  | 'unsupported'   // no service worker or no Push API in this browser
  | 'unconfigured'  // the server has no VAPID keys, so nothing can be sent
  | 'denied'        // refused, and only the browser's settings can undo it
  | 'subscribed'
  | 'available';    // supported, permitted or not yet asked

export function isSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

/**
 * iOS delivers web push only to a PWA the user added to their home screen,
 * and only from 16.4. Detected so the app can say "add to your home screen
 * first" instead of showing a button that silently does nothing.
 */
export function needsHomeScreenInstall(): boolean {
  const ua = navigator.userAgent;
  const isIos = /iPad|iPhone|iPod/.test(ua);
  if (!isIos) return false;
  const standalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    // Safari's own flag, which predates the standard media query.
    (window.navigator as { standalone?: boolean }).standalone === true;
  return !standalone;
}

export async function currentState(): Promise<PushState> {
  if (!isSupported()) return 'unsupported';

  const { enabled } = await api.pushConfig().catch(() => ({ enabled: false }));
  if (!enabled) return 'unconfigured';

  if (Notification.permission === 'denied') return 'denied';

  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  return subscription ? 'subscribed' : 'available';
}

/**
 * Ask for permission and register this device.
 *
 * Returns the resulting state rather than throwing on refusal: a person
 * saying no is an answer, not an error.
 */
export async function subscribe(): Promise<PushState> {
  if (!isSupported()) return 'unsupported';

  const config = await api.pushConfig();
  if (!config.enabled || !config.public_key) return 'unconfigured';

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return 'denied';

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    // Required by every browser: a push subscription that could deliver a
    // silent message is not allowed, and the spec enforces it here.
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(config.public_key),
  });

  const json = subscription.toJSON();
  if (!json.keys?.p256dh || !json.keys?.auth) {
    throw new Error('the browser returned an incomplete subscription');
  }
  await api.subscribePush({
    endpoint: subscription.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
  });
  return 'subscribed';
}

/** Stop notifications on this device, on both sides. */
export async function unsubscribe(): Promise<PushState> {
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) return 'available';

  const endpoint = subscription.endpoint;
  const json = subscription.toJSON();
  await subscription.unsubscribe();
  // Tell the server too, or it keeps sending into a void until the push
  // service finally reports the subscription gone.
  await api
    .unsubscribePush({
      endpoint,
      keys: {
        p256dh: json.keys?.p256dh ?? '',
        auth: json.keys?.auth ?? '',
      },
    })
    .catch(() => undefined);
  return 'available';
}

/**
 * The server sends the application key base64url-encoded; the browser wants
 * raw bytes.
 *
 * Returns the ArrayBuffer rather than a view: `applicationServerKey` is typed
 * as `BufferSource`, and a `Uint8Array` over an unspecified buffer no longer
 * satisfies that on current TypeScript lib definitions.
 */
function urlBase64ToUint8Array(base64: string): ArrayBuffer {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(normalized);
  const buffer = new ArrayBuffer(raw.length);
  const view = new Uint8Array(buffer);
  for (let i = 0; i < raw.length; i += 1) view[i] = raw.charCodeAt(i);
  return buffer;
}
