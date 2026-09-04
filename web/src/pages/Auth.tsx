/** Sign-in and sign-up, sharing one form because they differ by two fields. */

import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../lib/auth';

export function SignIn() {
  return <AuthForm mode="sign-in" />;
}

export function SignUp() {
  return <AuthForm mode="sign-up" />;
}

function AuthForm({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const { signIn, signUp } = useAuth();
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
      <h2>{isSignUp ? 'Create an account' : 'Sign in'}</h2>

      <form onSubmit={submit}>
        {isSignUp && (
          <label>
            <span>Name (optional)</span>
            <input
              type="text"
              autoComplete="name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
        )}

        <label>
          <span>Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <label>
          <span>Password</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete={isSignUp ? 'new-password' : 'current-password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {isSignUp && <small className="muted">At least 8 characters.</small>}
        </label>

        {error && <p className="error">{error}</p>}

        <button type="submit" className="button primary wide" disabled={busy}>
          {busy ? 'Working…' : isSignUp ? 'Create account' : 'Sign in'}
        </button>
      </form>

      <p className="muted">
        {isSignUp ? (
          <>
            Already have an account? <Link to="/sign-in">Sign in</Link>.
          </>
        ) : (
          <>
            No account yet? <Link to="/sign-up">Create one</Link>.
          </>
        )}
      </p>
    </section>
  );
}
