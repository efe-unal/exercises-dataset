/**
 * The publish step, offered after a session is logged.
 *
 * Publishing is always a separate, deliberate act — never a side effect of
 * finishing a workout. The dialog says plainly what becomes visible, because
 * training data is not something to make public by accident.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '@exercises/api-client';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useTranslation } from '../lib/i18n';

interface Props {
  sessionId: string;
  onPublished(): void;
  onDismiss(): void;
}

export function PublishDialog({ sessionId, onPublished, onDismiss }: Props) {
  const { t } = useTranslation();
  const { user, refresh } = useAuth();
  const [caption, setCaption] = useState('');
  const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // No handle means no profile for the workout to appear on, so the handle is
  // asked for here rather than sending the athlete off to settings and back.
  const needsUsername = user !== null && user.username === null;

  async function publish() {
    setBusy(true);
    setError(null);
    try {
      if (needsUsername) {
        await api.updateMe({ username: username.trim() });
        await refresh();
      }
      await api.publishSession(sessionId, caption.trim() || undefined);
      onPublished();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setError(t('share.usernameTaken'));
      } else {
        setError(caught instanceof Error ? caught.message : String(caught));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel publish-dialog">
      <h3>{t('share.publishTitle')}</h3>
      <p className="muted small">{t('share.publishExplains')}</p>

      {needsUsername && (
        <label>
          <span>{t('share.chooseUsername')}</span>
          <input
            type="text"
            value={username}
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="ayse_lifts"
            onChange={(event) => setUsername(event.target.value)}
          />
          <small className="muted">{t('share.usernameHint')}</small>
        </label>
      )}

      <label>
        <span>{t('share.caption')}</span>
        <input
          type="text"
          maxLength={280}
          value={caption}
          placeholder={t('share.captionPlaceholder')}
          onChange={(event) => setCaption(event.target.value)}
        />
      </label>

      {error && <p className="error">{error}</p>}

      <div className="actions">
        <button
          type="button"
          className="button primary"
          onClick={() => void publish()}
          disabled={busy || (needsUsername && username.trim().length < 3)}
        >
          {busy ? t('common.working') : t('share.publish')}
        </button>
        <button type="button" className="button subtle" onClick={onDismiss}>
          {t('share.keepPrivate')}
        </button>
      </div>

      {user?.username && (
        <p className="muted small">
          {t('share.willAppearOn')}{' '}
          <Link to={`/@${user.username}`}>@{user.username}</Link>
        </p>
      )}
    </section>
  );
}
