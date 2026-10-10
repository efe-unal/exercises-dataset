#!/usr/bin/env node
/**
 * Build one of the two Android apps' web content and copy it into its shell.
 *
 *   VITE_API_URL=https://api.example.com node scripts/build-android.mjs athlete
 *   VITE_API_URL=https://api.example.com node scripts/build-android.mjs operator
 *
 * Then `./gradlew assembleDebug` inside android-<mode>/ makes the APK; the
 * GitHub workflow does both steps.
 *
 * VITE_API_URL is required here and optional for the web app. A web page can
 * fall back to its own origin; inside the Android app that origin is the
 * phone itself, so an APK built without it can never reach a server.
 */

import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';

const mode = process.argv[2];
if (mode !== 'athlete' && mode !== 'operator') {
  console.error('usage: build-android.mjs athlete|operator');
  process.exit(2);
}

const apiUrl = process.env.VITE_API_URL ?? '';
if (!apiUrl.startsWith('https://')) {
  console.error(
    'VITE_API_URL must be set to the API\'s https:// address.\n' +
      'Android refuses plain http by default, and the app has no other way to ' +
      'find its server.',
  );
  process.exit(2);
}

const env = { ...process.env, APP_MODE: mode, VITE_APP_MODE: mode };
const run = (command, args) =>
  execFileSync(command, args, { stdio: 'inherit', env });

run('npx', ['vite', 'build', '--outDir', `dist-${mode}`, '--emptyOutDir']);

// The shell is generated once and committed; only a fresh checkout without it
// needs creating.
if (!existsSync(`android-${mode}`)) run('npx', ['cap', 'add', 'android']);
run('npx', ['cap', 'sync', 'android']);
