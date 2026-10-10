/**
 * Which app this build is, and whether it runs inside the Android shell.
 *
 * One codebase ships three ways. The mode is fixed at build time, so the
 * athlete APK does not carry the operator screen at all, and the operator APK
 * carries nothing else.
 */

import { Capacitor } from '@capacitor/core';

export type AppMode =
  | 'all'       // the web app: everything, operator page included for admins
  | 'athlete'   // the athlete APK
  | 'operator'; // the operator APK

function readMode(): AppMode {
  const value = import.meta.env.VITE_APP_MODE;
  return value === 'athlete' || value === 'operator' ? value : 'all';
}

export const APP_MODE: AppMode = readMode();

/** True inside the installed Android app, false in any browser. */
export const IS_NATIVE: boolean = Capacitor.isNativePlatform();

/**
 * Where a shared link should point: the public web app.
 *
 * Inside the Android app the page's own origin is `https://localhost`, which
 * means nothing to the person receiving the link.
 */
export const PUBLIC_ORIGIN: string =
  import.meta.env.VITE_PUBLIC_URL || window.location.origin;
