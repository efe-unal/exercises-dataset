/**
 * What the people you follow have been doing.
 *
 * Not a feed — a list of events, each pointing at one profile. Opening the
 * page is what marks them read: a per-item read button would be a round trip
 * for something nobody thinks about.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { AppNotification, ProfileSummary } from '@exercises/api-client';

import { api } from '../lib/api';
import { useTranslation } from '../lib/i18n';
import { refreshUnreadCount } from '../lib/notifications';

export function Notifications() {
  const { t } = useTranslation();
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [following, setFollowing] = useState<ProfileSummary[]>([]);

  useEffect(() => {
    void api.notifications().then(setItems).catch(() => setItems([]));
    void api.following().then(setFollowing).catch(() => undefined);
    // Reading the list is the act of reading them.
    void api.markNotificationsRead()
      .then(refreshUnreadCount)
      .catch(() => undefined);
  }, []);

  if (!items) return <p className="muted">{t('common.loading')}</p>;

  return (
    <section>
      <h2>{t('nav.activity')}</h2>

      {items.length === 0 ? (
        <p className="muted">{t('activity.empty')}</p>
      ) : (
        <ul className="plain-list">
          {items.map((item) => (
            <li key={item.id} className="card row">
              <div>
                <strong>
                  {item.actor_username ? (
                    <Link to={`/@${item.actor_username}`}>
                      {item.actor_display_name || `@${item.actor_username}`}
                    </Link>
                  ) : (
                    t('activity.someone')
                  )}
                </strong>{' '}
                {t('activity.publishedWorkout')}
                <p className="muted small">
                  {new Date(item.created_at).toLocaleString()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <h3>{t('activity.followingTitle')}</h3>
      {following.length === 0 ? (
        <p className="muted">{t('activity.followingEmpty')}</p>
      ) : (
        <ul className="plain-list">
          {following.map((person) => (
            <li key={person.username} className="card row">
              <div>
                <Link to={`/@${person.username}`}>
                  <strong>{person.display_name || `@${person.username}`}</strong>
                </Link>
                <p className="muted small">@{person.username}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
