/**
 * The unread badge.
 *
 * Polled rather than pushed. Real push — a notification on a locked phone —
 * needs VAPID keys and a push service configured for the deployment, which is
 * the same kind of gap as email delivery; see docs/SOCIAL.md. Until then the
 * badge updates while the app is open, which is honest about what it can do.
 */

import { api } from './api';

/** Slow enough to be invisible on a phone bill, fast enough to feel live. */
const POLL_INTERVAL_MS = 120_000;

type Listener = (unread: number) => void;

const listeners = new Set<Listener>();
let unread = 0;
let timer: ReturnType<typeof setInterval> | null = null;

export function onUnreadChange(listener: Listener): () => void {
  listeners.add(listener);
  listener(unread);
  return () => listeners.delete(listener);
}

export async function refreshUnreadCount(): Promise<void> {
  try {
    const { unread: count } = await api.unreadNotificationCount();
    unread = count;
    for (const listener of listeners) listener(unread);
  } catch {
    // Signed out, offline, or the server is down — the badge simply does not
    // move. Never surfaced: a failed badge poll is not worth an error.
  }
}

/** Begin polling. Returns a function that stops it. */
export function startUnreadPolling(): () => void {
  void refreshUnreadCount();
  timer ??= setInterval(() => void refreshUnreadCount(), POLL_INTERVAL_MS);

  // Coming back to the app is the moment the count is most likely stale.
  const onVisible = () => {
    if (document.visibilityState === 'visible') void refreshUnreadCount();
  };
  document.addEventListener('visibilitychange', onVisible);

  return () => {
    document.removeEventListener('visibilitychange', onVisible);
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  };
}
