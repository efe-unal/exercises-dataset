/**
 * The operator's page: write an announcement, and switch categories on or off.
 *
 * Reachable only to an account whose `is_admin` column was set directly in the
 * database — nothing in the product grants it. The server answers 404 rather
 * than 403 to anyone else, and this page does the same, so its existence is
 * not advertised.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import type {
  AdminOverview,
  AnnouncementResponse,
  NotificationTypeState,
} from '@exercises/api-client';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useTranslation } from '../lib/i18n';

export function Admin() {
  const { t } = useTranslation();
  const { user, loading } = useAuth();

  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [types, setTypes] = useState<NotificationTypeState[]>([]);
  const [sent, setSent] = useState<AnnouncementResponse[]>([]);

  const refresh = useCallback(async () => {
    const [o, ty, an] = await Promise.all([
      api.adminOverview(),
      api.adminNotificationTypes(),
      api.adminAnnouncements(),
    ]);
    setOverview(o);
    setTypes(ty);
    setSent(an);
  }, []);

  useEffect(() => {
    if (user?.is_admin) void refresh().catch(() => undefined);
  }, [user?.is_admin, refresh]);

  if (loading) return <p className="muted">{t('common.loading')}</p>;
  if (!user?.is_admin) {
    return (
      <section className="panel">
        <h2>{t('common.notFound')}</h2>
        <Link className="button" to="/">{t('common.back')}</Link>
      </section>
    );
  }

  return (
    <section>
      <h2>{t('admin.title')}</h2>

      {overview && (
        <ul className="stat-tiles">
          <li className="stat-tile">
            <span className="stat-value">{overview.users}</span>
            <span className="muted small">{t('admin.users')}</span>
          </li>
          <li className="stat-tile">
            <span className="stat-value">{overview.registered_devices}</span>
            <span className="muted small">{t('admin.devices')}</span>
          </li>
          <li className="stat-tile">
            <span className="stat-value">
              {overview.push_configured ? '✓' : '—'}
            </span>
            <span className="muted small">{t('admin.pushConfigured')}</span>
          </li>
        </ul>
      )}

      {overview && !overview.push_configured && (
        <p className="callout">{t('admin.pushMissing')}</p>
      )}

      <AnnouncementForm onSent={refresh} />

      <h3>{t('admin.types')}</h3>
      <p className="muted small">{t('admin.typesBody')}</p>
      <ul className="plain-list">
        {types.map((type) => (
          <li key={type.category} className="volume-row">
            <label className="inline-check">
              <input
                type="checkbox"
                checked={type.enabled}
                onChange={(event) =>
                  void api
                    .adminSetNotificationType(type.category, event.target.checked)
                    .then(refresh)
                }
              />
              <span>{t(`push.category.${type.category}`)}</span>
            </label>
          </li>
        ))}
      </ul>

      <h3>{t('admin.history')}</h3>
      {sent.length === 0 ? (
        <p className="muted">{t('admin.historyEmpty')}</p>
      ) : (
        <ul className="plain-list">
          {sent.map((announcement) => (
            <li key={announcement.id} className="card row">
              <div>
                <strong>{announcement.title}</strong>
                <p className="muted small">
                  {announcement.audience === 'self'
                    ? t('admin.audienceSelf')
                    : t('admin.audienceAll')}{' '}
                  · {announcement.recipient_count} {t('admin.delivered')} ·{' '}
                  {new Date(announcement.created_at).toLocaleString()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AnnouncementForm({ onSent }: { onSent(): Promise<void> }) {
  const { t } = useTranslation();
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  // Only ever set by the confirm step below, and cleared on every edit: a
  // message to everyone cannot be recalled, so it takes two deliberate acts.
  const [confirming, setConfirming] = useState(false);

  function edit<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value);
      setConfirming(false);
    };
  }

  async function send(audience: 'self' | 'all') {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.adminSendAnnouncement({
        title: title.trim(),
        body: body.trim(),
        url: url.trim() || undefined,
        audience,
      });
      setMessage(
        audience === 'self'
          ? t('admin.testSent')
          : t('admin.sentToAll', { count: result.recipient_count }),
      );
      setConfirming(false);
      if (audience === 'all') {
        setTitle('');
        setBody('');
        setUrl('');
      }
      await onSent();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send('self');
  }

  const ready = title.trim().length > 0 && body.trim().length > 0;

  return (
    <form className="panel" onSubmit={submit}>
      <h3>{t('admin.compose')}</h3>

      <label>
        <span>{t('admin.announcementTitle')}</span>
        <input
          type="text"
          maxLength={120}
          value={title}
          onChange={(event) => edit(setTitle)(event.target.value)}
        />
      </label>
      <label>
        <span>{t('admin.announcementBody')}</span>
        <input
          type="text"
          maxLength={500}
          value={body}
          onChange={(event) => edit(setBody)(event.target.value)}
        />
      </label>
      <label>
        <span>{t('admin.announcementUrl')}</span>
        <input
          type="text"
          maxLength={300}
          placeholder="/activity"
          value={url}
          onChange={(event) => edit(setUrl)(event.target.value)}
        />
      </label>

      <div className="actions">
        <button type="submit" className="button" disabled={busy || !ready}>
          {t('admin.sendTest')}
        </button>

        {confirming ? (
          <button
            type="button"
            className="button primary danger"
            disabled={busy}
            onClick={() => void send('all')}
          >
            {t('admin.confirmSendAll')}
          </button>
        ) : (
          <button
            type="button"
            className="button"
            disabled={busy || !ready}
            onClick={() => setConfirming(true)}
          >
            {t('admin.sendAll')}
          </button>
        )}
      </div>

      {confirming && <p className="callout">{t('admin.confirmWarning')}</p>}
      {message && <p className="muted small">{message}</p>}
    </form>
  );
}
