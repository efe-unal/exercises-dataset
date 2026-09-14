/** Account preferences, and the sign-out button. */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useTranslation } from '../lib/i18n';

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'tr', label: 'Türkçe' },
  { value: 'es', label: 'Español' },
  { value: 'it', label: 'Italiano' },
  { value: 'ru', label: 'Русский' },
  { value: 'zh', label: '中文' },
  { value: 'hi', label: 'हिन्दी' },
  { value: 'pl', label: 'Polski' },
  { value: 'ko', label: '한국어' },
];

export function Settings() {
  const { user, signOut, refresh } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [saved, setSaved] = useState(false);
  const [username, setUsername] = useState('');
  const [bio, setBio] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;

  async function update(changes: Parameters<typeof api.updateMe>[0]) {
    setError(null);
    try {
      await api.updateMe(changes);
      await refresh();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  return (
    <section className="panel narrow">
      <h2>{t('settings.title')}</h2>
      <p className="muted">
        {t('settings.signedInAs')}: {user.email}
        {user.tier === 'pro' ? ' · pro' : ''}
      </p>

      <section className="profile-settings">
        <h3>{t('profile.yourProfile')}</h3>
        {user.username ? (
          <>
            <p className="muted">
              <Link to={`/@${user.username}`}>@{user.username}</Link>
            </p>
            <label>
              <span>{t('profile.bio')}</span>
              <input
                type="text"
                maxLength={300}
                defaultValue={user.bio ?? ''}
                onChange={(event) => setBio(event.target.value)}
                onBlur={() => bio !== (user.bio ?? '') && void update({ bio })}
              />
            </label>
          </>
        ) : (
          <>
            <p className="muted small">{t('profile.claimUsername')}</p>
            <label>
              <span>{t('profile.username')}</span>
              <input
                type="text"
                autoCapitalize="none"
                autoCorrect="off"
                placeholder="ayse_lifts"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
              <small className="muted">{t('share.usernameHint')}</small>
            </label>
            <button
              type="button"
              className="button"
              disabled={username.trim().length < 3}
              onClick={() => void update({ username: username.trim() })}
            >
              {t('common.save')}
            </button>
          </>
        )}
      </section>

      <label>
        <span>{t('settings.language')}</span>
        <select
          value={user.language}
          onChange={(event) => void update({ language: event.target.value })}
        >
          {LANGUAGES.map((language) => (
            <option key={language.value} value={language.value}>
              {language.label}
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t('settings.units')}</span>
        <select
          value={user.unit_system}
          onChange={(event) =>
            void update({
              unit_system: event.target.value as 'metric' | 'imperial',
            })
          }
        >
          <option value="metric">{t('settings.metric')}</option>
          <option value="imperial">{t('settings.imperial')}</option>
        </select>
      </label>

      {saved && <p className="callout">{t('common.saved')}</p>}
      {error && <p className="error">{error}</p>}

      <button
        type="button"
        className="button wide"
        onClick={async () => {
          await signOut();
          navigate('/');
        }}
      >
        {t('auth.signOut')}
      </button>
    </section>
  );
}
