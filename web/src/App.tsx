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

  return (
    <div className="app">
      <StatusBanners />
      <header className="app-header">
        <Link to="/" className="brand">
          Training
        </Link>
        {!loading && !user && (
          <nav className="auth-links">
            <Link to="/sign-in">Sign in</Link>
            <Link className="button primary" to="/sign-up">
              Sign up
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
  return (
    <nav className="tab-bar" aria-label="Main">
      <NavLink to="/" end>
        Today
      </NavLink>
      <NavLink to="/programs">Programs</NavLink>
      <NavLink to="/exercises">Exercises</NavLink>
      <NavLink to="/progress">Progress</NavLink>
      <NavLink to="/settings">Settings</NavLink>
    </nav>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to="/sign-in" state={{ from: location }} replace />;
  return <>{children}</>;
}

function StatusBanners() {
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
      {!online && <span>Offline — your sets are saved on this device.</span>}
      {pending > 0 && (
        <span>
          {pending} session{pending === 1 ? '' : 's'} waiting to sync.
        </span>
      )}
    </div>
  );
}

function NotFound() {
  return (
    <section className="panel">
      <h2>Not found</h2>
      <Link className="button" to="/">
        Go back
      </Link>
    </section>
  );
}
