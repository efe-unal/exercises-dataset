/** Training history and the headline numbers derived from it. */

import { useEffect, useState } from 'react';
import type { Stats, WorkoutSession } from '@exercises/api-client';

import { api } from '../lib/api';
import { useTranslation } from '../lib/i18n';

export function Progress() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<Stats | null>(null);
  const [sessions, setSessions] = useState<WorkoutSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void Promise.all([api.stats(), api.listSessions({ limit: 30 })])
      .then(([loadedStats, loadedSessions]) => {
        setStats(loadedStats);
        setSessions(loadedSessions);
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="muted">{t('common.loading')}</p>;

  return (
    <section>
      <h2>{t('progress.title')}</h2>

      {stats && (
        <ul className="stat-tiles">
          <StatTile
            label={t('progress.sessions')}
            value={stats.total_sessions}
          />
          <StatTile
            label={t('progress.workingSets')}
            value={stats.total_working_sets}
          />
          <StatTile
            label={t('progress.totalVolume')}
            value={`${Math.round(stats.total_volume_kg).toLocaleString()} kg`}
          />
          <StatTile
            label={t('progress.lastSession')}
            value={
              stats.last_session_at
                ? new Date(stats.last_session_at).toLocaleDateString()
                : '—'
            }
          />
        </ul>
      )}

      <h3>{t('progress.recent')}</h3>
      {sessions.length === 0 ? (
        <p className="muted">{t('progress.nothingLogged')}</p>
      ) : (
        <ul className="plain-list">
          {sessions.map((session) => {
            const working = session.sets.filter((set) => !set.is_warmup);
            const volume = working.reduce(
              (total, set) => total + (set.weight_kg ?? 0) * set.reps,
              0,
            );
            return (
              <li key={session.id} className="card row">
                <div>
                  <strong>{session.day_name}</strong>
                  <p className="muted small">
                    {t('common.week')} {session.week} ·{' '}
                    {new Date(session.started_at).toLocaleDateString()} ·{' '}
                    {working.length} {t('progress.sets')}
                    {volume > 0
                      ? ` · ${Math.round(volume).toLocaleString()} kg`
                      : ''}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <li className="stat-tile">
      <span className="stat-value">{value}</span>
      <span className="muted small">{label}</span>
    </li>
  );
}
