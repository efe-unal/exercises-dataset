/**
 * Someone's public profile: who they are, and the workouts they published.
 *
 * Reachable signed-out on purpose — a shared card has to lead somewhere for a
 * reader who does not have the app. What they get is an invitation, not a
 * wall.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { ProfileResponse, PublishedSession } from '@exercises/api-client';
import { ApiError } from '@exercises/api-client';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useTranslation } from '../lib/i18n';
import { renderShareCard, shareCard } from '../lib/shareCard';

export function Profile() {
  const { handle = '' } = useParams();
  // The route captures the whole segment, so a handle is only a handle when
  // it carries the @ prefix; anything else is a mistyped page.
  const username = handle.startsWith('@') ? handle.slice(1) : '';
  const { user } = useAuth();
  const { t } = useTranslation();

  const [data, setData] = useState<ProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await api.profile(username));
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 404
        ? t('profile.notFound')
        : caught instanceof Error ? caught.message : String(caught));
    }
  }, [username, t]);

  useEffect(() => {
    if (!username) {
      setError(t('common.notFound'));
      return;
    }
    void load();
  }, [load, username, t]);

  async function toggleFollow() {
    if (!data) return;
    setBusy(true);
    try {
      if (data.is_following) await api.unfollowProfile(username);
      else await api.followProfile(username);
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <section className="panel">
        <h2>{error}</h2>
        <Link className="button" to="/">{t('common.back')}</Link>
      </section>
    );
  }
  if (!data) return <p className="muted">{t('common.loading')}</p>;

  const { profile, is_self: isSelf, is_following: isFollowing } = data;

  return (
    <section>
      <header className="profile-head">
        <div>
          <h2>{profile.display_name || `@${profile.username}`}</h2>
          <p className="muted">@{profile.username}</p>
          {profile.bio && <p className="bio">{profile.bio}</p>}
          <p className="muted small">
            {t('profile.followers', { count: profile.followers })} ·{' '}
            {t('profile.following', { count: profile.following })}
          </p>
        </div>

        {!isSelf && user && (
          <button
            type="button"
            className={isFollowing ? 'button' : 'button primary'}
            onClick={() => void toggleFollow()}
            disabled={busy}
          >
            {isFollowing ? t('profile.unfollow') : t('profile.follow')}
          </button>
        )}
      </header>

      {/* A signed-out reader arrived from a shared card. Tell them what this
          is, rather than showing them a bare follow button they cannot use. */}
      {!user && (
        <p className="callout">
          {t('profile.visitorPrompt')}{' '}
          <Link to="/sign-up">{t('auth.signUp')}</Link>
        </p>
      )}

      {data.sessions.length === 0 ? (
        <p className="muted">
          {isSelf ? t('profile.emptySelf') : t('profile.emptyOther')}
        </p>
      ) : (
        <ul className="plain-list">
          {data.sessions.map((session) => (
            <PublishedCard
              key={session.id}
              session={session}
              username={profile.username}
              displayName={profile.display_name}
              isSelf={isSelf}
              onChanged={load}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function PublishedCard({
  session,
  username,
  displayName,
  isSelf,
  onChanged,
}: {
  session: PublishedSession;
  username: string;
  displayName: string;
  isSelf: boolean;
  onChanged(): void;
}) {
  const { t } = useTranslation();
  const [message, setMessage] = useState<string | null>(null);

  async function share() {
    setMessage(null);
    try {
      const blob = await renderShareCard({
        dayName: session.day_name,
        caption: session.caption,
        totalSets: session.total_sets,
        totalVolumeKg: session.total_volume_kg,
        exercises: session.exercises,
        username,
        displayName,
        profileUrl: api.profileUrl(username),
        labels: {
          sets: t('progress.workingSets'),
          volume: t('progress.totalVolume'),
          exercises: t('exercises.title'),
          andMore: t('share.andMore'),
          reps: t('sets.reps'),
        },
      });
      const how = await shareCard(blob, {
        username,
        profileUrl: api.profileUrl(username),
        dayName: session.day_name,
      });
      setMessage(how === 'shared' ? null : t('share.downloaded'));
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : String(caught));
    }
  }

  async function unpublish() {
    if (!globalThis.confirm(t('share.confirmUnpublish'))) return;
    await api.unpublishSession(session.id);
    onChanged();
  }

  return (
    <li className="card">
      <div className="page-header">
        <div>
          <strong>{session.day_name}</strong>
          <p className="muted small">
            {session.published_at
              ? new Date(session.published_at).toLocaleDateString()
              : ''}{' '}
            · {session.total_sets} {t('progress.sets')} ·{' '}
            {Math.round(session.total_volume_kg).toLocaleString()} kg
          </p>
        </div>
      </div>

      {session.caption && <p>{session.caption}</p>}

      <ul className="plain-list">
        {session.exercises.map((exercise) => (
          <li key={exercise.exercise_id} className="volume-row">
            <Link to={`/exercises/${exercise.exercise_id}`}>{exercise.name}</Link>
            <span className="muted small">
              {exercise.sets} ×{' '}
              {exercise.best_weight_kg
                ? `${exercise.best_weight_kg} kg`
                : `${exercise.total_reps} ${t('sets.reps')}`}
            </span>
          </li>
        ))}
      </ul>

      <div className="actions">
        <button type="button" className="button small" onClick={() => void share()}>
          {t('share.button')}
        </button>
        {isSelf && (
          <button type="button" className="button small danger"
                  onClick={() => void unpublish()}>
            {t('share.unpublish')}
          </button>
        )}
      </div>

      {message && <p className="muted small">{message}</p>}
    </li>
  );
}
