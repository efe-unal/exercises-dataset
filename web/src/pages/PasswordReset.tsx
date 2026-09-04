/**
 * The two halves of a password reset: asking for a link, and using one.
 *
 * The request form always reports success, matching the API — telling someone
 * which addresses have accounts is exactly what an attacker is probing for.
 */

import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useTranslation } from '../lib/i18n';

export function ForgotPassword() {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await api.requestPasswordReset(email);
    } catch {
      // Even a failure is reported as success: any difference in the response
      // would tell the caller whether the address exists.
    } finally {
      setSent(true);
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <section className="panel narrow">
        <h2>{t('reset.checkInbox')}</h2>
        <p className="muted">{t('reset.sentBody')}</p>
        <Link className="button wide" to="/sign-in">
          {t('auth.signIn')}
        </Link>
      </section>
    );
  }

  return (
    <section className="panel narrow">
      <h2>{t('reset.forgotTitle')}</h2>
      <p className="muted">{t('reset.forgotBody')}</p>

      <form onSubmit={submit}>
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
        <button type="submit" className="button primary wide" disabled={busy}>
          {busy ? t('common.working') : t('reset.sendLink')}
        </button>
      </form>

      <p className="muted">
        <Link to="/sign-in">{t('auth.signIn')}</Link>
      </p>
    </section>
  );
}

export function ResetPassword() {
  const { t } = useTranslation();
  const { clearSession } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.confirmPasswordReset(token, password);
      // Every session was just invalidated, including this browser's. Without
      // clearing it here the app would still believe someone is signed in and
      // send them to a screen that fails on its first request.
      clearSession();
      navigate('/sign-in');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <section className="panel narrow">
        <h2>{t('reset.badLink')}</h2>
        <Link className="button wide" to="/forgot-password">
          {t('reset.requestAnother')}
        </Link>
      </section>
    );
  }

  return (
    <section className="panel narrow">
      <h2>{t('reset.chooseTitle')}</h2>
      <p className="muted">{t('reset.chooseBody')}</p>

      <form onSubmit={submit}>
        <label>
          <span>{t('reset.newPassword')}</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <small className="muted">{t('auth.passwordHint')}</small>
        </label>

        {error && <p className="error">{error}</p>}

        <button type="submit" className="button primary wide" disabled={busy}>
          {busy ? t('common.working') : t('reset.setPassword')}
        </button>
      </form>
    </section>
  );
}
