/**
 * Swap one exercise for another that does the same job.
 *
 * The rack is busy, the machine is taken, a joint is complaining. The
 * substitute has to train the same movement pattern — the API answers that
 * from the taxonomy — and the swap applies to today only: the saved plan is a
 * snapshot and must not change under someone mid-block. What gets logged is
 * whatever they actually did.
 */

import { useEffect, useState } from 'react';
import type { Exercise } from '@exercises/api-client';

import { api } from '../lib/api';
import { useTranslation } from '../lib/i18n';
import { ExerciseMedia } from './ExerciseMedia';

interface Props {
  exerciseId: string;
  equipmentProfile?: string;
  language: string;
  onSwap(exercise: Exercise): void;
  onCancel(): void;
}

export function SwapExercise({
  exerciseId,
  equipmentProfile,
  language,
  onSwap,
  onCancel,
}: Props) {
  const { t } = useTranslation();
  const [options, setOptions] = useState<Exercise[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .alternatives(exerciseId, {
        equipment_profile: equipmentProfile,
        language,
        limit: 8,
      })
      .then((response) => {
        if (!cancelled) setOptions(response.alternatives);
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [exerciseId, equipmentProfile, language]);

  return (
    <div className="swap-panel">
      <div className="swap-head">
        <strong>{t('swap.title')}</strong>
        <button type="button" className="button subtle small" onClick={onCancel}>
          {t('swap.cancel')}
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {!options && !error && <p className="muted small">{t('common.loading')}</p>}
      {options?.length === 0 && (
        <p className="muted small">{t('swap.none')}</p>
      )}

      <ul className="plain-list">
        {options?.map((option) => (
          <li key={option.id} className="plan-row">
            <ExerciseMedia exercise={option} size={48} />
            <div className="swap-option">
              <strong>{option.name}</strong>
              <span className="muted small">{option.equipment}</span>
            </div>
            <button
              type="button"
              className="button small"
              onClick={() => onSwap(option)}
            >
              {t('swap.use')}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
