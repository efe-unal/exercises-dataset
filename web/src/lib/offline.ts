/**
 * An offline queue for workout logging.
 *
 * Gyms are the worst place on earth for a signal, and a logged set that
 * vanishes because the connection dropped is the fastest way to lose a user.
 * Every log is written to local storage first and sent afterwards; anything
 * that fails to send stays queued and is retried when the browser reports it
 * is back online.
 */

import { ApiError, type LogSessionRequest, type WorkoutSession } from '@exercises/api-client';

import { api } from './api';

const QUEUE_KEY = 'exercises.pending-sessions';

interface QueuedLog {
  id: string;
  request: LogSessionRequest;
  queuedAt: string;
  attempts: number;
}

type Listener = (pending: number) => void;

const listeners = new Set<Listener>();

function read(): QueuedLog[] {
  try {
    const raw = globalThis.localStorage?.getItem(QUEUE_KEY);
    return raw ? (JSON.parse(raw) as QueuedLog[]) : [];
  } catch {
    return [];
  }
}

function write(queue: QueuedLog[]): void {
  try {
    globalThis.localStorage?.setItem(QUEUE_KEY, JSON.stringify(queue));
  } catch {
    /* storage unavailable — the queue simply does not survive a reload */
  }
  for (const listener of listeners) listener(queue.length);
}

export function pendingCount(): number {
  return read().length;
}

export function onPendingChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Log a session, queueing it if the request cannot be delivered.
 *
 * Returns the saved session when the server accepted it, or null when the log
 * was queued for later. A rejected request — bad data, or a program that is
 * not the caller's — is thrown rather than queued, because retrying it would
 * never succeed.
 */
export async function logSession(
  request: LogSessionRequest,
): Promise<WorkoutSession | null> {
  try {
    return await api.logSession(request);
  } catch (error) {
    if (error instanceof ApiError && error.status >= 400 && error.status < 500
        && error.status !== 408 && error.status !== 429) {
      throw error;
    }
    enqueue(request);
    return null;
  }
}

function enqueue(request: LogSessionRequest): void {
  const queue = read();
  // One entry per program day: re-logging a slot replaces it on the server,
  // so a queued duplicate would only send the same correction twice.
  const key = `${request.program_id}:${request.week}:${request.day_index}`;
  const without = queue.filter(
    (item) =>
      `${item.request.program_id}:${item.request.week}:${item.request.day_index}` !== key,
  );
  without.push({
    id: key,
    request,
    queuedAt: new Date().toISOString(),
    attempts: 0,
  });
  write(without);
}

/**
 * Try to send everything queued. Safe to call at any time; it does nothing
 * when the queue is empty or the browser is offline.
 */
export async function flushQueue(): Promise<{ sent: number; remaining: number }> {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return { sent: 0, remaining: pendingCount() };
  }

  let queue = read();
  let sent = 0;

  for (const item of [...queue]) {
    try {
      await api.logSession(item.request);
      queue = queue.filter((queued) => queued.id !== item.id);
      sent += 1;
    } catch (error) {
      if (error instanceof ApiError && error.status >= 400 && error.status < 500
          && error.status !== 408 && error.status !== 429) {
        // The server will never accept this one; dropping it is better than
        // retrying forever.
        queue = queue.filter((queued) => queued.id !== item.id);
      } else {
        // Still offline, or the server is down. Stop and try again later.
        const index = queue.findIndex((queued) => queued.id === item.id);
        if (index >= 0) queue[index]!.attempts += 1;
        break;
      }
    }
  }

  write(queue);
  return { sent, remaining: queue.length };
}

/** Flush when the browser regains connectivity, and once at startup. */
export function startAutoFlush(): () => void {
  const handler = () => void flushQueue();
  globalThis.addEventListener?.('online', handler);
  void flushQueue();
  return () => globalThis.removeEventListener?.('online', handler);
}
