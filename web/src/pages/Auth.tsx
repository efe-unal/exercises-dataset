/** Sign-in and sign-up, sharing one form because they differ by two fields. */

import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../lib/auth';
import { useTranslation } from '../lib/i18n';

export function SignIn() {
  return <AuthForm mode="sign-in" />;
}

export function SignUp() {
  return <AuthForm mode="sign-up" />;
}

function AuthForm({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const { signIn, signUp } = useAuth();
  const { t, language } = useTranslation();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isSignUp = mode === 'sign-up';

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isSignUp) {
        await signUp({
          email,
          password,
          display_name: displayName.trim() || undefined,
          // Someone signing up from a Turkish browser gets a Turkish
          // account; without this the new account defaults to English and
          // the interface flips language the moment they register.
          language,
        });
      } else {
        await signIn(email, password);
      }
      navigate('/');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel narrow">
      <h2>{isSignUp ? t('auth.createAccount') : t('auth.signIn')}</h2>

      <form onSubmit={submit}>
        {isSignUp && (
          <label>
            <span>{t('auth.nameOptional')}</span>
            <input
              type="text"
              autoComplete="name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
        )}

        <label>
          <span>{t('auth.email')}</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <label>
          <span>{t('auth.password')}</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete={isSignUp ? 'new-password' : 'current-password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {isSignUp && <small className="muted">{t('auth.passwordHint')}</small>}
        </label>

        {error && <p className="error">{error}</p>}

        <button type="submit" className="button primary wide" disabled={busy}>
          {busy ? t('common.working') : isSignUp ? t('auth.createAccountButton') : t('auth.signIn')}
        </button>
      </form>

      <p className="muted">
        {isSignUp ? (
          <>
            {t('auth.haveAccount')} <Link to="/sign-in">{t('auth.signIn')}</Link>.
          </>
        ) : (
          <>
            {t('auth.noAccount')} <Link to="/sign-up">{t('auth.createOne')}</Link>.
          </>
        )}
      </p>
    </section>
  );
}
