/**
 * The rest timer between sets.
 *
 * Starts itself when a set is logged, because the moment an athlete finishes a
 * set is exactly when they are least inclined to press a button. It counts
 * down from the prescribed rest, keeps counting past zero rather than
 * stopping — knowing you rested four minutes matters — and survives the phone
 * screen locking, since it stores the end time rather than ticking a counter.
 */

import { useEffect, useRef, useState } from 'react';

import { useTranslation } from '../lib/i18n';

interface Props {
  /** Prescribed rest in seconds. */
  seconds: number;
  /** Changes whenever a set is logged; that is what restarts the timer. */
  restartKey: number;
}

export function RestTimer({ seconds, restartKey }: Props) {
  const { t } = useTranslation();
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const notified = useRef(false);

  // A set was logged: start (or restart) the rest.
  useEffect(() => {
    if (restartKey === 0) return;
    setStartedAt(Date.now());
    setNow(Date.now());
    notified.current = false;
  }, [restartKey]);

  useEffect(() => {
    if (startedAt === null) return;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [startedAt]);

  if (startedAt === null) return null;

  const elapsed = Math.floor((now - startedAt) / 1000);
  const remaining = seconds - elapsed;
  const done = remaining <= 0;

  // One short vibration when the rest is up. Ignored where unsupported, and
  // silent by design: a phone in a gym is usually in a pocket, and an audible
  // alarm is the wrong default in a shared room.
  if (done && !notified.current) {
    notified.current = true;
    try {
      globalThis.navigator?.vibrate?.(200);
    } catch {
      /* vibration unavailable or blocked */
    }
  }

  return (
    <div className={`rest-timer${done ? ' done' : ''}`} role="timer" aria-live="off">
      <span className="rest-time">
        {done ? '+' : ''}
        {formatDuration(Math.abs(done ? -remaining : remaining))}
      </span>
      <span className="muted small">
        {done ? t('rest.ready') : t('rest.resting')}
      </span>
      <button
        type="button"
        className="button subtle small"
        onClick={() => setStartedAt(null)}
      >
        {t('rest.dismiss')}
      </button>
    </div>
  );
}

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${minutes}:${String(secs).padStart(2, '0')}`;
}
