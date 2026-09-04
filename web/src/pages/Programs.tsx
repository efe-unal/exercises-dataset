/** Saved programs: switch between blocks, or delete one. */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { ProgramSummary } from '@exercises/api-client';

import { api } from '../lib/api';
import { useTranslation } from '../lib/i18n';

export function Programs() {
  const { t } = useTranslation();
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
    if (!globalThis.confirm(t('programs.confirmDelete'))) return;
    await api.deleteProgram(id);
    await load();
  }

  if (error) return <p className="error">{error}</p>;
  if (!programs) return <p className="muted">{t('common.loading')}</p>;

  return (
    <section>
      <header className="page-header">
        <h2>{t('programs.title')}</h2>
        <Link className="button primary" to="/programs/new">
          {t('programs.new')}
        </Link>
      </header>

      {programs.length === 0 ? (
        <p className="muted">{t('programs.empty')}</p>
      ) : (
        <ul className="plain-list">
          {programs.map((program) => (
            <li key={program.id} className="card row">
              <div>
                <strong>{program.name}</strong>
                {program.is_active && (
                  <span className="badge">{t('programs.active')}</span>
                )}
                <p className="muted small">
                  {t(`goal.${program.goal}`)} · {t(`level.${program.level}`)} ·{' '}
                  {program.days_per_week} {t('programs.daysPerWeek')} ·{' '}
                  {program.weeks} {t('builder.weeks')}
                </p>
              </div>
              <div className="actions">
                {!program.is_active && (
                  <button type="button" onClick={() => void activate(program.id)}>
                    {t('programs.makeActive')}
                  </button>
                )}
                <button
                  type="button"
                  className="danger"
                  onClick={() => void remove(program.id)}
                >
                  {t('common.delete')}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
