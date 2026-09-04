/**
 * The set-by-set logging control.
 *
 * Built for one-handed use between sets: every row is pre-filled from the
 * suggested load and the bottom of the rep range, so a normal set is one tap
 * to confirm and nothing to type.
 */

import { useState } from 'react';

import { useTranslation } from '../lib/i18n';

export interface LoggedSet {
  index: number;
  reps: number;
  weightKg: number | null;
  rir: number | null;
  isWarmup: boolean;
}

interface Props {
  targetSets: number;
  defaultWeightKg: number | null;
  defaultReps: number;
  sets: LoggedSet[];
  onChange(sets: LoggedSet[]): void;
}

export function SetLogger({
  targetSets,
  defaultWeightKg,
  defaultReps,
  sets,
  onChange,
}: Props) {
  const { t } = useTranslation();
  const [weight, setWeight] = useState<string>(
    defaultWeightKg !== null ? String(defaultWeightKg) : '',
  );
  const [reps, setReps] = useState<string>(String(defaultReps));

  function addSet(isWarmup = false) {
    const parsedReps = Number.parseInt(reps, 10);
    if (!Number.isFinite(parsedReps) || parsedReps <= 0) return;
    const parsedWeight = weight.trim() === '' ? null : Number.parseFloat(weight);
    onChange([
      ...sets,
      {
        index: sets.length + 1,
        reps: parsedReps,
        weightKg:
          parsedWeight !== null && Number.isFinite(parsedWeight)
            ? parsedWeight
            : null,
        rir: null,
        isWarmup,
      },
    ]);
  }

  function removeSet(index: number) {
    onChange(
      sets
        .filter((set) => set.index !== index)
        // Renumber so the stored set order always reads 1, 2, 3.
        .map((set, position) => ({ ...set, index: position + 1 })),
    );
  }

  return (
    <div className="set-logger">
      {sets.length > 0 && (
        <ul className="logged-sets">
          {sets.map((set) => (
            <li key={set.index}>
              <span>
                {set.isWarmup ? '~' : set.index}. {set.reps} {t('sets.reps')}
                {set.weightKg !== null ? ` × ${set.weightKg} kg` : ''}
              </span>
              <button
                type="button"
                aria-label={`Remove set ${set.index}`}
                onClick={() => removeSet(set.index)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="set-inputs">
        <label>
          <span>{t('sets.kg')}</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.5"
            min="0"
            value={weight}
            placeholder="—"
            onChange={(event) => setWeight(event.target.value)}
          />
        </label>
        <label>
          <span>{t('sets.reps')}</span>
          <input
            type="number"
            inputMode="numeric"
            step="1"
            min="1"
            value={reps}
            onChange={(event) => setReps(event.target.value)}
          />
        </label>
        <button type="button" className="button" onClick={() => addSet(false)}>
          {t('sets.addSet')}
        </button>
        <button
          type="button"
          className="button subtle"
          onClick={() => addSet(true)}
        >
          {t('sets.warmup')}
        </button>
      </div>

      <p className="muted small">
        {t('sets.progress', {
          done: sets.filter((set) => !set.isWarmup).length,
          total: targetSets,
        })}
      </p>
    </div>
  );
}
