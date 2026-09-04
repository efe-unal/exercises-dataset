/**
 * A read-only view of a generated block: week by week, day by day.
 *
 * The weekly set volume is shown because it is the number that tells an
 * athlete whether the plan is actually reasonable — far more informative than
 * the list of exercise names it is derived from.
 */

import { useState } from 'react';
import type { Plan, PlanWeek } from '@exercises/api-client';

import { ExerciseMedia } from './ExerciseMedia';

export function PlanPreview({ plan }: { plan: Plan }) {
  const [openWeek, setOpenWeek] = useState(1);
  const week = plan.weeks.find((candidate) => candidate.week === openWeek)
    ?? plan.weeks[0];

  return (
    <section className="plan-preview">
      <header className="page-header">
        <div>
          <h3>{plan.split}</h3>
          <p className="muted">
            {plan.weeks.length} weeks · {plan.profile.days_per_week} days a week
            · {plan.progression_model.replace(/_/g, ' ')} progression
          </p>
        </div>
      </header>

      <nav className="week-tabs" aria-label="Weeks">
        {plan.weeks.map((candidate) => (
          <button
            key={candidate.week}
            type="button"
            className={candidate.week === week?.week ? 'active' : ''}
            onClick={() => setOpenWeek(candidate.week)}
          >
            {candidate.is_deload ? `${candidate.week} ·` : candidate.week}
          </button>
        ))}
      </nav>

      {week && <WeekView week={week} />}

      <p className="attribution">{plan.attribution}</p>
    </section>
  );
}

function WeekView({ week }: { week: PlanWeek }) {
  return (
    <div>
      <p className="callout">
        {week.is_deload && <strong>Deload week. </strong>}
        {week.guidance}
      </p>

      {week.days.map((day, index) => (
        <article key={`${day.name}-${index}`} className="card">
          <h4>
            {day.name} <span className="muted">· ~{day.estimated_minutes} min</span>
          </h4>
          <ul className="plain-list">
            {day.exercises.map((entry) => (
              <li key={entry.exercise.id} className="plan-row">
                <ExerciseMedia exercise={entry.exercise} size={56} />
                <div>
                  <strong>{entry.exercise.name}</strong>
                  <p className="muted small">
                    {entry.prescription.sets} × {entry.prescription.rep_min}–
                    {entry.prescription.rep_max} · rest{' '}
                    {entry.prescription.rest_seconds}s
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </article>
      ))}

      <div className="volume">
        <h4>Weekly sets per body part</h4>
        <ul className="plain-list">
          {Object.entries(week.weekly_set_volume).map(([part, sets]) => (
            <li key={part} className="volume-row">
              <span>{part}</span>
              <span className="bar" style={{ '--sets': sets } as React.CSSProperties}>
                {sets}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
