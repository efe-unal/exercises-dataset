/**
 * The app shell: navigation, routes, and the two banners that matter on a
 * phone — offline state and unsynced sessions.
 */

import { useEffect, useState } from 'react';
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom';

import { useAuth } from './lib/auth';
import { useTranslation } from './lib/i18n';
import { onPendingChange, pendingCount, startAutoFlush } from './lib/offline';
import { SignIn, SignUp } from './pages/Auth';
import { ExerciseDetail } from './pages/ExerciseDetail';
import { Exercises } from './pages/Exercises';
import { ProgramBuilder } from './pages/ProgramBuilder';
import { Programs } from './pages/Programs';
import { Progress } from './pages/Progress';
import { Settings } from './pages/Settings';
import { Today } from './pages/Today';

export function App() {
  const { user, loading } = useAuth();
  const { t } = useTranslation();

  return (
    <div className="app">
      <StatusBanners />
      <header className="app-header">
        <Link to="/" className="brand">
          {t('app.name')}
        </Link>
        {!loading && !user && (
          <nav className="auth-links">
            <Link to="/sign-in">{t('auth.signIn')}</Link>
            <Link className="button primary" to="/sign-up">
              {t('auth.signUp')}
            </Link>
          </nav>
        )}
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={user ? <Today /> : <ProgramBuilder />} />
          <Route path="/programs/new" element={<ProgramBuilder />} />
          <Route
            path="/programs"
            element={<RequireAuth>{<Programs />}</RequireAuth>}
          />
          <Route path="/exercises" element={<Exercises />} />
          <Route path="/exercises/:id" element={<ExerciseDetail />} />
          <Route
            path="/progress"
            element={<RequireAuth>{<Progress />}</RequireAuth>}
          />
          <Route
            path="/settings"
            element={<RequireAuth>{<Settings />}</RequireAuth>}
          />
          <Route path="/sign-in" element={user ? <Navigate to="/" /> : <SignIn />} />
          <Route path="/sign-up" element={user ? <Navigate to="/" /> : <SignUp />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>

      {user && <TabBar />}
    </div>
  );
}

/** Bottom tabs: thumb-reachable, which is where navigation belongs on a phone. */
function TabBar() {
  const { t } = useTranslation();
  return (
    <nav className="tab-bar" aria-label="Main">
      <NavLink to="/" end>
        {t('nav.today')}
      </NavLink>
      <NavLink to="/programs">{t('nav.programs')}</NavLink>
      <NavLink to="/exercises">{t('nav.exercises')}</NavLink>
      <NavLink to="/progress">{t('nav.progress')}</NavLink>
      <NavLink to="/settings">{t('nav.settings')}</NavLink>
    </nav>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();

  if (loading) return <p className="muted">{t('common.loading')}</p>;
  if (!user) return <Navigate to="/sign-in" state={{ from: location }} replace />;
  return <>{children}</>;
}

function StatusBanners() {
  const { t } = useTranslation();
  const [online, setOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine,
  );
  const [pending, setPending] = useState(pendingCount());

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    globalThis.addEventListener('online', goOnline);
    globalThis.addEventListener('offline', goOffline);
    const stopFlushing = startAutoFlush();
    const stopWatching = onPendingChange(setPending);
    return () => {
      globalThis.removeEventListener('online', goOnline);
      globalThis.removeEventListener('offline', goOffline);
      stopFlushing();
      stopWatching();
    };
  }, []);

  if (online && pending === 0) return null;

  return (
    <div className="status-banner" role="status">
      {!online && <span>{t('offline.offline')}</span>}
      {pending > 0 && <span>{t('offline.pending', { count: pending })}</span>}
    </div>
  );
}

function NotFound() {
  const { t } = useTranslation();
  return (
    <section className="panel">
      <h2>{t('common.notFound')}</h2>
      <Link className="button" to="/">
        {t('common.back')}
      </Link>
    </section>
  );
}
