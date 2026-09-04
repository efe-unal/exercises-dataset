/**
 * Session state: who is signed in, and the operations that change that.
 *
 * Held in one context so every screen reads the same answer and a sign-out
 * anywhere is a sign-out everywhere.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { User } from '@exercises/api-client';

import { api, onUnauthorized } from './api';

interface AuthState {
  user: User | null;
  /** True until the stored token has been checked against the server. */
  loading: boolean;
  signIn(email: string, password: string): Promise<void>;
  signUp(input: {
    email: string;
    password: string;
    display_name?: string;
    language?: string;
  }): Promise<void>;
  signOut(): Promise<void>;
  refresh(): Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!(await api.isSignedIn())) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      // An expired or revoked token is not an error worth surfacing; the
      // client has already cleared it, so the app simply shows signed-out.
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    return onUnauthorized(() => setUser(null));
  }, [refresh]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      async signIn(email, password) {
        await api.login(email, password);
        setUser(await api.me());
      },
      async signUp(input) {
        await api.register(input);
        setUser(await api.me());
      },
      async signOut() {
        await api.logout();
        setUser(null);
      },
      refresh,
    }),
    [user, loading, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used inside an AuthProvider');
  }
  return context;
}
