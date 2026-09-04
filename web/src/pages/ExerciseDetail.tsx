/**
 * One exercise: how to do it, what you have lifted on it, and what to lift
 * next.
 *
 * The history chart plots the estimated one-rep max rather than raw weight,
 * because that is the number that stays comparable when the rep range moves.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import type { Exercise, ExerciseHistory, Suggestion } from '@exercises/api-client';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useTranslation } from '../lib/i18n';
import { suggestionText } from '../lib/suggestion';
import { ExerciseMedia } from '../components/ExerciseMedia';
import { OneRepMaxChart } from '../components/OneRepMaxChart';

export function ExerciseDetail() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const { t } = useTranslation();
  const language = user?.language ?? 'en';

  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [history, setHistory] = useState<ExerciseHistory | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setExercise(null);
    setError(null);

    void api
      .exercise(id, language)
      .then((result) => {
        if (!cancelled) setExercise(result);
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      });

    if (user) {
      void api
        .exerciseHistory(id)
        .then((result) => !cancelled && setHistory(result))
        .catch(() => undefined);
      void api
        .suggestion(id)
        .then((result) => !cancelled && setSuggestion(result))
        .catch(() => undefined);
    }

    return () => {
      cancelled = true;
    };
  }, [id, language, user]);

  if (error) return <p className="error">{error}</p>;
  if (!exercise) return <p className="muted">{t('common.loading')}</p>;

  const workingSets = (history?.sets ?? []).filter((set) => !set.is_warmup);

  return (
    <article>
      <header className="page-header">
        <ExerciseMedia exercise={exercise} size={160} />
        <div>
          <h2>{exercise.name}</h2>
          <p className="muted">
            {exercise.body_part} · {exercise.target} · {exercise.equipment}
          </p>
          <p className="muted small">
            {exercise.pattern.replace(/_/g, ' ')} · {exercise.mechanic} ·{' '}
            {exercise.difficulty}
          </p>
        </div>
      </header>

      {suggestion && (
        <p className="callout">
          <strong>
            {t('exercises.nextLoad')}:{' '}
            {suggestion.weight_kg !== null
              ? `${suggestion.weight_kg} kg`
              : t('exercises.bodyweight')}
          </strong>{' '}
          — {suggestionText(t, suggestion, 2.5)}
        </p>
      )}

      {exercise.instruction_steps && exercise.instruction_steps.length > 0 && (
        <section>
          <h3>{t('exercises.howTo')}</h3>
          <ol className="steps">
            {exercise.instruction_steps.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
        </section>
      )}

      {user && (
        <section>
          <h3>{t('exercises.yourHistory')}</h3>
          {workingSets.length === 0 ? (
            <p className="muted">{t('exercises.noHistory')}</p>
          ) : (
            <>
              <OneRepMaxChart sets={workingSets} />
              <ul className="plain-list history-list">
                {workingSets.slice(0, 12).map((set, index) => (
                  <li key={index}>
                    <span>{new Date(set.performed_at).toLocaleDateString()}</span>
                    <span>
                      {set.reps} reps
                      {set.weight_kg !== null ? ` × ${set.weight_kg} kg` : ''}
                    </span>
                    <span className="muted">
                      {set.estimated_1rm !== null ? `e1RM ${set.estimated_1rm}` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      <p className="attribution">© Gym visual — https://gymvisual.com/</p>
    </article>
  );
}
