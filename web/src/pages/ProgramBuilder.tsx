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
import { PlanPreview } from '../components/PlanPreview';

const GOALS: Array<{ value: Goal; label: string }> = [
  { value: 'hypertrophy', label: 'Build muscle' },
  { value: 'strength', label: 'Get stronger' },
  { value: 'fat_loss', label: 'Lose fat' },
  { value: 'endurance', label: 'Muscular endurance' },
  { value: 'general_fitness', label: 'General fitness' },
];

const LEVELS: Array<{ value: Level; label: string; hint: string }> = [
  { value: 'beginner', label: 'New to training', hint: 'Under a year of consistent lifting' },
  { value: 'intermediate', label: 'Experienced', hint: 'One to three years' },
  { value: 'advanced', label: 'Advanced', hint: 'Several years of structured training' },
];

const EQUIPMENT: Array<{ value: EquipmentProfile; label: string }> = [
  { value: 'full_gym', label: 'Full gym' },
  { value: 'home_dumbbell', label: 'Dumbbells at home' },
  { value: 'home_minimal', label: 'Bands and a ball' },
  { value: 'bodyweight', label: 'Bodyweight only' },
];

export function ProgramBuilder() {
  const { user } = useAuth();
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
        setError(
          'Free accounts keep one program at a time. Delete the old one, or upgrade to keep several.',
        );
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
      <h2>Build a program</h2>

      <form className="builder" onSubmit={preview}>
        <fieldset>
          <legend>What are you training for?</legend>
          <div className="options">
            {GOALS.map((goal) => (
              <label key={goal.value} className="option">
                <input
                  type="radio"
                  name="goal"
                  checked={request.goal === goal.value}
                  onChange={() => update('goal', goal.value)}
                />
                <span>{goal.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend>How much training have you done?</legend>
          <div className="options">
            {LEVELS.map((level) => (
              <label key={level.value} className="option">
                <input
                  type="radio"
                  name="level"
                  checked={request.level === level.value}
                  onChange={() => update('level', level.value)}
                />
                <span>
                  {level.label}
                  <small>{level.hint}</small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend>What do you have to train with?</legend>
          <div className="options">
            {EQUIPMENT.map((equipment) => (
              <label key={equipment.value} className="option">
                <input
                  type="radio"
                  name="equipment"
                  checked={request.equipment === equipment.value}
                  onChange={() => update('equipment', equipment.value)}
                />
                <span>{equipment.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="sliders">
          <label>
            <span>Days per week: {request.days_per_week}</span>
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
            <span>Minutes per session: {request.session_minutes}</span>
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
            <span>Block length: {request.weeks} weeks</span>
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
          {busy ? 'Working…' : 'Show me the program'}
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
              Save and start this block
            </button>
          ) : (
            <p className="callout">
              Create an account to save this block and log your sessions —{' '}
              <a href="/sign-up">sign up</a>.
            </p>
          )}
        </>
      )}
    </section>
  );
}
