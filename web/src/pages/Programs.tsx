/** Saved programs: switch between blocks, or delete one. */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { ProgramSummary } from '@exercises/api-client';

import { api } from '../lib/api';

export function Programs() {
  const [programs, setPrograms] = useState<ProgramSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPrograms(await api.listPrograms());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function activate(id: string) {
    await api.activateProgram(id);
    await load();
  }

  async function remove(id: string) {
    // Deleting a program takes its logged sessions with it, so this asks
    // first — the history is not recoverable.
    if (!globalThis.confirm(
      'Delete this program and everything logged against it?',
    )) {
      return;
    }
    await api.deleteProgram(id);
    await load();
  }

  if (error) return <p className="error">{error}</p>;
  if (!programs) return <p className="muted">Loading…</p>;

  return (
    <section>
      <header className="page-header">
        <h2>Your programs</h2>
        <Link className="button primary" to="/programs/new">
          New program
        </Link>
      </header>

      {programs.length === 0 ? (
        <p className="muted">
          Nothing saved yet. Build a block and it will appear here.
        </p>
      ) : (
        <ul className="plain-list">
          {programs.map((program) => (
            <li key={program.id} className="card row">
              <div>
                <strong>{program.name}</strong>
                {program.is_active && <span className="badge">Active</span>}
                <p className="muted small">
                  {program.goal.replace(/_/g, ' ')} · {program.level} ·{' '}
                  {program.days_per_week} days/week · {program.weeks} weeks
                </p>
              </div>
              <div className="actions">
                {!program.is_active && (
                  <button type="button" onClick={() => void activate(program.id)}>
                    Make active
                  </button>
                )}
                <button
                  type="button"
                  className="danger"
                  onClick={() => void remove(program.id)}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
