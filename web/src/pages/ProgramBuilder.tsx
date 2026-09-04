/**
 * Build a program: choose a goal and constraints, preview the real block, and
 * save it.
 *
 * The preview needs no account. That is the point — a visitor sees an actual
 * generated program before being asked for an email.
 */

import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import type {
  EquipmentProfile,
  Goal,
  Level,
  Plan,
  ProgramRequest,
} from '@exercises/api-client';
import { ApiError } from '@exercises/api-client';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useTranslation } from '../lib/i18n';
import { PlanPreview } from '../components/PlanPreview';

// Labels come from the translation dictionary, keyed by the API's own value,
// so adding a goal never means touching this list twice.
const GOALS: Goal[] = [
  'hypertrophy',
  'strength',
  'fat_loss',
  'endurance',
  'general_fitness',
];

const LEVELS: Level[] = ['beginner', 'intermediate', 'advanced'];

const EQUIPMENT: EquipmentProfile[] = [
  'full_gym',
  'home_dumbbell',
  'home_minimal',
  'bodyweight',
];

export function ProgramBuilder() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [request, setRequest] = useState<ProgramRequest>({
    goal: 'hypertrophy',
    level: 'beginner',
    days_per_week: 3,
    equipment: 'full_gym',
    session_minutes: 60,
    weeks: 4,
    language: user?.language ?? 'en',
  });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof ProgramRequest>(key: K, value: ProgramRequest[K]) {
    setRequest((current) => ({ ...current, [key]: value }));
    setPlan(null); // the preview no longer matches the form
  }

  async function preview(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setPlan(await api.previewProgram(request));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.saveProgram({ ...request, make_active: true });
      navigate('/');
    } catch (caught) {
      if (caught instanceof ApiError && caught.isPaymentRequired) {
        setError(t('builder.freeLimit'));
      } else if (caught instanceof ApiError && caught.isUnauthorized) {
        navigate('/sign-in');
      } else {
        setError(caught instanceof Error ? caught.message : String(caught));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h2>{t('builder.title')}</h2>

      <form className="builder" onSubmit={preview}>
        <fieldset>
          <legend>{t('builder.goalQuestion')}</legend>
          <div className="options">
            {GOALS.map((goal) => (
              <label key={goal} className="option">
                <input
                  type="radio"
                  name="goal"
                  checked={request.goal === goal}
                  onChange={() => update('goal', goal)}
                />
                <span>{t(`goal.${goal}`)}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend>{t('builder.levelQuestion')}</legend>
          <div className="options">
            {LEVELS.map((level) => (
              <label key={level} className="option">
                <input
                  type="radio"
                  name="level"
                  checked={request.level === level}
                  onChange={() => update('level', level)}
                />
                <span>
                  {t(`level.${level}`)}
                  <small>{t(`level.${level}.hint`)}</small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend>{t('builder.equipmentQuestion')}</legend>
          <div className="options">
            {EQUIPMENT.map((equipment) => (
              <label key={equipment} className="option">
                <input
                  type="radio"
                  name="equipment"
                  checked={request.equipment === equipment}
                  onChange={() => update('equipment', equipment)}
                />
                <span>{t(`equipment.${equipment}`)}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="sliders">
          <label>
            <span>
              {t('builder.daysPerWeek')}: {request.days_per_week}
            </span>
            <input
              type="range"
              min={2}
              max={6}
              value={request.days_per_week}
              onChange={(event) =>
                update('days_per_week', Number(event.target.value))
              }
            />
          </label>
          <label>
            <span>
              {t('builder.sessionMinutes')}: {request.session_minutes}
            </span>
            <input
              type="range"
              min={20}
              max={120}
              step={5}
              value={request.session_minutes}
              onChange={(event) =>
                update('session_minutes', Number(event.target.value))
              }
            />
          </label>
          <label>
            <span>
              {t('builder.blockLength')}: {request.weeks} {t('builder.weeks')}
            </span>
            <input
              type="range"
              min={1}
              max={12}
              value={request.weeks}
              onChange={(event) => update('weeks', Number(event.target.value))}
            />
          </label>
        </div>

        <button type="submit" className="button primary wide" disabled={busy}>
          {busy ? t('common.working') : t('builder.generate')}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {plan && (
        <>
          <PlanPreview plan={plan} />
          {user ? (
            <button
              type="button"
              className="button primary wide"
              onClick={() => void save()}
              disabled={busy}
            >
              {t('builder.save')}
            </button>
          ) : (
            <p className="callout">
              {t('builder.signUpPrompt')} —{' '}
              <a href="/sign-up">{t('auth.signUp').toLowerCase()}</a>.
            </p>
          )}
        </>
      )}
    </section>
  );
}
