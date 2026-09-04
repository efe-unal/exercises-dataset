/**
 * The app's single API client instance, and the React context around it.
 *
 * Everything that talks to the server goes through here, so the base URL, the
 * token store and the sign-out behaviour are configured in exactly one place.
 */

import {
  ExercisesClient,
  LocalStorageTokenStore,
} from '@exercises/api-client';

/**
 * In development Vite proxies `/v1` to the API, so a relative base keeps the
 * browser on one origin. In production set VITE_API_URL to the deployed API.
 */
const baseUrl = import.meta.env.VITE_API_URL ?? window.location.origin;

/** Notified when the server rejects a token, so the UI can drop to signed-out. */
const unauthorizedListeners = new Set<() => void>();

export function onUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

export const api = new ExercisesClient({
  baseUrl,
  tokenStore: new LocalStorageTokenStore(),
  onUnauthorized: () => {
    for (const listener of unauthorizedListeners) listener();
  },
});
