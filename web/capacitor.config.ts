/**
 * The Android shells around the web app — two of them, one per app.
 *
 * Capacitor reads one config, so the mode arrives as an environment variable
 * and picks the app's identity. `scripts/build-android.mjs` sets it; run that
 * rather than `npx cap` directly.
 *
 * `appId` is the identity Android (and later Play) knows the app by. Changing
 * it after testers have installed a build makes it a different app: they get a
 * second icon, and the first one's data stays behind with it.
 */

import type { CapacitorConfig } from '@capacitor/cli';

const mode = process.env.APP_MODE === 'operator' ? 'operator' : 'athlete';

const apps = {
  athlete: { appId: 'com.efeunal.training', appName: 'Antrenman' },
  operator: { appId: 'com.efeunal.training.operator', appName: 'Antrenman Yönetim' },
} as const;

const config: CapacitorConfig = {
  ...apps[mode],
  webDir: `dist-${mode}`,
  android: { path: `android-${mode}` },
};

export default config;
