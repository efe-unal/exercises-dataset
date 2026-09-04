/**
 * The screen the athlete opens in the gym: today's session, with a suggested
 * load per exercise, and a form to log what they actually did.
 *
 * Styling here is deliberately plain — structure and behaviour first, so the
 * visual design can be dropped on top without rewriting the logic.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type {
  NextSession,
  PlanEntry,
  SavedPlan,
  SetEntry,
} from '@exercises/api-client';
import { ApiError } from '@exercises/api-client';

import { api } from '../lib/api';
import { labelFor, useTranslation, type Translate } from '../lib/i18n';
import { suggestionText } from '../lib/suggestion';
import { logSession } from '../lib/offline';
import { ExerciseMedia } from '../components/ExerciseMedia';
import { SetLogger, type LoggedSet } from '../components/SetLogger';

type Status = 'loading' | 'ready' | 'no-program' | 'complete' | 'error';

export function Today() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Status>('loading');
  const [program, setProgram] = useState<SavedPlan | null>(null);
  const [session, setSession] = useState<
    Extract<NextSession, { complete: false }> | null
  >(null);
  const [logged, setLogged] = useState<Record<string, LoggedSet[]>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setStatus('loading');
    setMessage(null);
    try {
      const active = await api.activeProgram();
      setProgram(active);
      const next = await api.nextSession(active.id);
      if (next.complete) {
        setSession(null);
        setStatus('complete');
        return;
      }
      setSession(next);
      setLogged({});
      setStatus('ready');
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setStatus('no-program');
        return;
      }
      setMessage(error instanceof Error ? error.message : String(error));
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const entriesWithSets = useMemo(
    () =>
      (session?.day.exercises ?? []).filter(
        (entry) => (logged[entry.exercise.id] ?? []).length > 0,
      ).length,
    [session, logged],
  );

  async function finish() {
    if (!session || !program) return;
    const sets: SetEntry[] = [];
    for (const entry of session.day.exercises) {
      for (const set of logged[entry.exercise.id] ?? []) {
        sets.push({
          exercise_id: entry.exercise.id,
          exercise_name: entry.exercise.name,
          set_index: set.index,
          reps: set.reps,
          weight_kg: set.weightKg,
          rir: set.rir,
          is_warmup: set.isWarmup,
        });
      }
    }
    if (sets.length === 0) {
      setMessage(t('today.needOneSet'));
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      const saved = await logSession({
        program_id: program.id,
        week: session.week,
        day_index: session.day_index,
        day_name: session.day.name,
        sets,
      });
      setMessage(saved ? t('today.sessionSaved') : t('today.savedOffline'));
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  }

  if (status === 'loading') return <p className="muted">{t('common.loading')}</p>;

  if (status === 'no-program') {
    return (
      <section className="panel">
        <h2>{t('today.noProgramTitle')}</h2>
        <p className="muted">{t('today.noProgramBody')}</p>
        <Link className="button" to="/programs/new">
          {t('today.buildProgram')}
        </Link>
      </section>
    );
  }

  if (status === 'complete') {
    return (
      <section className="panel">
        <h2>{t('today.completeTitle')}</h2>
        <p className="muted">{t('today.completeBody')}</p>
        <Link className="button" to="/programs/new">
          {t('today.buildNext')}
        </Link>
      </section>
    );
  }

  if (status === 'error' || !session) {
    return (
      <section className="panel">
        <h2>{t('today.errorTitle')}</h2>
        <p className="error">{message}</p>
        <button type="button" onClick={() => void load()}>
          {t('common.retry')}
        </button>
      </section>
    );
  }

  return (
    <section>
      <header className="page-header">
        <div>
          <h2>{labelFor(t, 'day', session.day.key, session.day.name)}</h2>
          <p className="muted">
            {t('common.week')} {session.week} · ~{session.day.estimated_minutes}{' '}
            {t('common.min')}
            {session.is_deload ? ` · ${t('today.deloadWeek')}` : ''}
          </p>
        </div>
        <span className="counter">
          {entriesWithSets}/{session.day.exercises.length} {t('today.logged')}
        </span>
      </header>

      {session.is_deload && (
        <p className="callout">
          {labelFor(t, 'guidance', session.guidance_key, session.guidance)}
        </p>
      )}

      <ol className="exercise-list">
        {session.day.exercises.map((entry) => (
          <ExerciseCard
            key={entry.exercise.id}
            entry={entry}
            t={t}
            sets={logged[entry.exercise.id] ?? []}
            onChange={(sets) =>
              setLogged((current) => ({ ...current, [entry.exercise.id]: sets }))
            }
          />
        ))}
      </ol>

      {message && <p className="callout">{message}</p>}

      <button
        type="button"
        className="button primary wide"
        onClick={() => void finish()}
        disabled={saving}
      >
        {saving ? t('today.saving') : t('today.finish')}
      </button>

      <p className="attribution">{session.attribution}</p>
    </section>
  );
}

function ExerciseCard({
  entry,
  sets,
  onChange,
  t,
}: {
  entry: PlanEntry;
  sets: LoggedSet[];
  onChange(sets: LoggedSet[]): void;
  t: Translate;
}) {
  const { prescription: rx, suggestion } = entry;
  return (
    <li className="card">
      <div className="card-head">
        <ExerciseMedia exercise={entry.exercise} />
        <div>
          <h3>
            <Link to={`/exercises/${entry.exercise.id}`}>
              {entry.exercise.name}
            </Link>
          </h3>
          <p className="muted">
            {labelFor(t, 'slot', entry.slot_key, entry.slot)} · {rx.sets} ×{' '}
            {rx.rep_min}–{rx.rep_max} · {t('today.rest')} {rx.rest_seconds}s ·{' '}
            {rx.rir} RIR
          </p>
          {suggestion && (
            <p className="suggestion">
              {suggestion.weight_kg !== null && (
                <strong>{suggestion.weight_kg} kg — </strong>
              )}
              {suggestionText(t, suggestion, entry.load_step_kg)}
            </p>
          )}
        </div>
      </div>

      <SetLogger
        targetSets={rx.sets}
        defaultWeightKg={suggestion?.weight_kg ?? null}
        defaultReps={rx.rep_min}
        sets={sets}
        onChange={onChange}
      />
    </li>
  );
}
