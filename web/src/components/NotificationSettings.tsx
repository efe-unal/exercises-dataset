/**
 * Notification settings: the permission, the categories, and quiet hours.
 *
 * The permission button is never pressed on the athlete's behalf. A browser
 * asks once, and a refusal can only be undone in its own settings, so the
 * prompt appears after they have read what they are agreeing to.
 */

import { useCallback, useEffect, useState } from 'react';
import type { NotificationPreferences } from '@exercises/api-client';

import { api } from '../lib/api';
import { useTranslation } from '../lib/i18n';
import {
  currentState,
  needsHomeScreenInstall,
  subscribe,
  unsubscribe,
  type PushState,
} from '../lib/push';

/** Offered as quiet-hour boundaries; a full clock would be a wall of options. */
const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

export function NotificationSettings() {
  const { t } = useTranslation();
  const [state, setState] = useState<PushState | null>(null);
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setState(await currentState());
    setPrefs(await api.notificationPreferences().catch(() => null));
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function toggleDevice() {
    setBusy(true);
    setMessage(null);
    try {
      setState(state === 'subscribed' ? await unsubscribe() : await subscribe());
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function setCategory(category: string, enabled: boolean) {
    await api.setNotificationPreference(category, enabled);
    await refresh();
  }

  async function sendTest() {
    setMessage(null);
    try {
      await api.sendTestPush();
      setMessage(t('push.testSent'));
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : String(caught));
    }
  }

  if (state === null) return null;

  return (
    <section className="profile-settings">
      <h3>{t('push.title')}</h3>

      {state === 'unsupported' && (
        <p className="muted small">{t('push.unsupported')}</p>
      )}

      {state === 'unconfigured' && (
        <p className="muted small">{t('push.unconfigured')}</p>
      )}

      {state === 'denied' && (
        <p className="muted small">{t('push.denied')}</p>
      )}

      {/* Without this, the button on an iPhone would appear to do nothing. */}
      {(state === 'available' || state === 'subscribed') &&
        needsHomeScreenInstall() && (
          <p className="callout">{t('push.iosInstall')}</p>
        )}

      {(state === 'available' || state === 'subscribed') && (
        <>
          <p className="muted small">
            {state === 'subscribed' ? t('push.onBody') : t('push.offBody')}
          </p>
          <div className="actions">
            <button
              type="button"
              className={state === 'subscribed' ? 'button' : 'button primary'}
              onClick={() => void toggleDevice()}
              disabled={busy}
            >
              {state === 'subscribed' ? t('push.turnOff') : t('push.turnOn')}
            </button>
            {state === 'subscribed' && (
              <button type="button" className="button subtle"
                      onClick={() => void sendTest()}>
                {t('push.sendTest')}
              </button>
            )}
          </div>
        </>
      )}

      {message && <p className="muted small">{message}</p>}

      {prefs && (
        <>
          <h4>{t('push.whatToSend')}</h4>
          <ul className="plain-list">
            {prefs.categories.map((category) => (
              <li key={category.category} className="volume-row">
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={category.enabled}
                    disabled={!category.available}
                    onChange={(event) =>
                      void setCategory(category.category, event.target.checked)
                    }
                  />
                  <span>
                    {t(`push.category.${category.category}`)}
                    {/* The operator turned this off for everyone; saying so
                        beats a checkbox that silently does nothing. */}
                    {!category.available && (
                      <small className="muted"> — {t('push.categoryOff')}</small>
                    )}
                  </span>
                </label>
              </li>
            ))}
          </ul>

          <h4>{t('push.quietHours')}</h4>
          <p className="muted small">{t('push.quietHoursBody')}</p>
          <div className="quiet-hours">
            <label>
              <span>{t('push.quietFrom')}</span>
              <select
                value={prefs.quiet_from_hour}
                onChange={(event) =>
                  void api
                    .setQuietHours({ quiet_from_hour: Number(event.target.value) })
                    .then(refresh)
                }
              >
                {HOURS.map((hour) => (
                  <option key={hour} value={hour}>{`${hour}:00`}</option>
                ))}
              </select>
            </label>
            <label>
              <span>{t('push.quietTo')}</span>
              <select
                value={prefs.quiet_to_hour}
                onChange={(event) =>
                  void api
                    .setQuietHours({ quiet_to_hour: Number(event.target.value) })
                    .then(refresh)
                }
              >
                {HOURS.map((hour) => (
                  <option key={hour} value={hour}>{`${hour}:00`}</option>
                ))}
              </select>
            </label>
          </div>
          <p className="muted small">
            {t('push.timezone')}: {prefs.timezone}{' '}
            <button
              type="button"
              className="button subtle small"
              onClick={() =>
                void api
                  .setQuietHours({
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                  })
                  .then(refresh)
              }
            >
              {t('push.useDeviceTimezone')}
            </button>
          </p>
        </>
      )}
    </section>
  );
}
