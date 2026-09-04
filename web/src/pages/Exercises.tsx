/** Browse and search the exercise catalog. */

import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Exercise, Facets } from '@exercises/api-client';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useTranslation } from '../lib/i18n';
import { ExerciseMedia } from '../components/ExerciseMedia';

const PAGE_SIZE = 24;

export function Exercises() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const language = user?.language ?? 'en';

  const [facets, setFacets] = useState<Facets | null>(null);
  const [query, setQuery] = useState('');
  const [bodyPart, setBodyPart] = useState('');
  const [equipment, setEquipment] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [results, setResults] = useState<Exercise[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void api.facets().then(setFacets).catch(() => setFacets(null));
  }, []);

  // Typing a search term should not fire a request per keystroke.
  const [debouncedQuery, setDebouncedQuery] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 250);
    return () => clearTimeout(timer);
  }, [query]);

  const filters = useMemo(
    () => ({
      q: debouncedQuery || undefined,
      body_part: bodyPart || undefined,
      equipment_profile: equipment || undefined,
      difficulty: difficulty || undefined,
      language,
      limit: PAGE_SIZE,
      offset,
    }),
    [debouncedQuery, bodyPart, equipment, difficulty, language, offset],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void api
      .exercises(filters)
      .then((response) => {
        if (cancelled) return;
        setResults(response.results);
        setTotal(response.total);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters]);

  // Any filter change invalidates the current page.
  useEffect(() => {
    setOffset(0);
  }, [debouncedQuery, bodyPart, equipment, difficulty]);

  return (
    <section>
      <h2>{t('exercises.title')}</h2>

      <div className="filters">
        <input
          type="search"
          placeholder={t('exercises.search')}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label={t('exercises.search')}
        />
        <select
          value={bodyPart}
          onChange={(event) => setBodyPart(event.target.value)}
          aria-label="Body part"
        >
          <option value="">{t('exercises.anyBodyPart')}</option>
          {facets?.body_part.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <select
          value={equipment}
          onChange={(event) => setEquipment(event.target.value)}
          aria-label="Equipment"
        >
          <option value="">{t('exercises.anyEquipment')}</option>
          {facets?.equipment_profile.map((value) => (
            <option key={value} value={value}>
              {value.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
        <select
          value={difficulty}
          onChange={(event) => setDifficulty(event.target.value)}
          aria-label="Difficulty"
        >
          <option value="">{t('exercises.anyDifficulty')}</option>
          {facets?.difficulty.map((value) => (
            <option key={value} value={value}>
              {t(`level.${value}`)}
            </option>
          ))}
        </select>
      </div>

      <p className="muted small">
        {loading ? t('exercises.searching') : t('exercises.count', { count: total })}
      </p>

      <ul className="exercise-grid">
        {results.map((exercise) => (
          <li key={exercise.id}>
            <Link to={`/exercises/${exercise.id}`} className="grid-card">
              <ExerciseMedia exercise={exercise} size={120} />
              <strong>{exercise.name}</strong>
              <span className="muted small">
                {exercise.body_part} · {exercise.equipment}
              </span>
            </Link>
          </li>
        ))}
      </ul>

      {total > PAGE_SIZE && (
        <nav className="pager">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            {t('exercises.previous')}
          </button>
          <span className="muted small">
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <button
            type="button"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            {t('exercises.next')}
          </button>
        </nav>
      )}
    </section>
  );
}
