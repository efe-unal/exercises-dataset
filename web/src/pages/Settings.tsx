/** Account preferences, and the sign-out button. */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';

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
  const navigate = useNavigate();
  const [saved, setSaved] = useState(false);
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
      <h2>Settings</h2>
      <p className="muted">
        Signed in as {user.email}
        {user.tier === 'pro' ? ' · pro' : ''}
      </p>

      <label>
        <span>Instruction language</span>
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
        <span>Units</span>
        <select
          value={user.unit_system}
          onChange={(event) =>
            void update({
              unit_system: event.target.value as 'metric' | 'imperial',
            })
          }
        >
          <option value="metric">Metric (kg)</option>
          <option value="imperial">Imperial (lb)</option>
        </select>
      </label>

      {saved && <p className="callout">Saved.</p>}
      {error && <p className="error">{error}</p>}

      <button
        type="button"
        className="button wide"
        onClick={async () => {
          await signOut();
          navigate('/');
        }}
      >
        Sign out
      </button>
    </section>
  );
}
