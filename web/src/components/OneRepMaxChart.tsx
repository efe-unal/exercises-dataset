/**
 * Estimated one-rep max over time, as a single-series line chart.
 *
 * One series, so there is no legend — the heading names it — and the colour
 * carries no identity of its own. A crosshair and tooltip come as standard;
 * a line chart the reader cannot interrogate is a picture, not a chart. The
 * same numbers are available as a table for anyone who cannot use the plot.
 */

import { useId, useMemo, useState } from 'react';

import { useTranslation } from '../lib/i18n';

interface HistorySet {
  performed_at: string;
  reps: number;
  weight_kg: number | null;
  estimated_1rm: number | null;
}

interface Point {
  x: number;
  y: number;
  date: Date;
  value: number;
}

const WIDTH = 640;
const HEIGHT = 220;
const PADDING = { top: 16, right: 16, bottom: 28, left: 44 };

export function OneRepMaxChart({ sets }: { sets: HistorySet[] }) {
  const { t } = useTranslation();
  const titleId = useId();
  const [hovered, setHovered] = useState<Point | null>(null);
  const [showTable, setShowTable] = useState(false);

  const points = useMemo(() => buildPoints(sets), [sets]);

  if (points.length < 2) {
    return (
      <p className="muted small">{t('chart.needMore')}</p>
    );
  }

  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  // A flat series would otherwise divide by zero and draw off-canvas.
  const span = max - min || Math.max(1, max * 0.1);
  const low = min - span * 0.1;
  const high = max + span * 0.1;

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;

  const firstTime = points[0]!.x;
  const lastTime = points[points.length - 1]!.x;
  const timeSpan = lastTime - firstTime || 1;

  const toX = (time: number) =>
    PADDING.left + ((time - firstTime) / timeSpan) * plotWidth;
  const toY = (value: number) =>
    PADDING.top + (1 - (value - low) / (high - low)) * plotHeight;

  const path = points
    .map((point, index) =>
      `${index === 0 ? 'M' : 'L'} ${toX(point.x).toFixed(1)} ${toY(point.value).toFixed(1)}`,
    )
    .join(' ');

  const ticks = [low, (low + high) / 2, high];

  return (
    <figure className="viz-root chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-labelledby={titleId}
        preserveAspectRatio="xMidYMid meet"
        onMouseLeave={() => setHovered(null)}
      >
        <title id={titleId}>
          Estimated one-rep max over time, from {Math.round(min)} to{' '}
          {Math.round(max)} kilograms
        </title>

        {/* Recessive gridlines: present for reading values, never competing
            with the data. */}
        {ticks.map((value) => (
          <g key={value}>
            <line
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={toY(value)}
              y2={toY(value)}
              className="grid"
            />
            <text x={PADDING.left - 8} y={toY(value) + 4} className="axis-label end">
              {Math.round(value)}
            </text>
          </g>
        ))}

        <path d={path} className="series-line" fill="none" />

        {points.map((point, index) => (
          <circle
            key={index}
            cx={toX(point.x)}
            cy={toY(point.value)}
            r={hovered === point ? 6 : 4}
            className="series-dot"
          />
        ))}

        {hovered && (
          <line
            x1={toX(hovered.x)}
            x2={toX(hovered.x)}
            y1={PADDING.top}
            y2={HEIGHT - PADDING.bottom}
            className="crosshair"
          />
        )}

        {/* Hit targets are far larger than the marks, so a fingertip finds
            them on a phone. */}
        {points.map((point, index) => (
          <rect
            key={`hit-${index}`}
            x={toX(point.x) - plotWidth / (points.length * 2) - 2}
            y={PADDING.top}
            width={plotWidth / points.length + 4}
            height={plotHeight}
            fill="transparent"
            onMouseEnter={() => setHovered(point)}
            onFocus={() => setHovered(point)}
            tabIndex={0}
            role="button"
            aria-label={`${point.date.toLocaleDateString()}: ${point.value} kilograms estimated`}
          />
        ))}

        <text x={PADDING.left} y={HEIGHT - 8} className="axis-label">
          {points[0]!.date.toLocaleDateString()}
        </text>
        <text x={WIDTH - PADDING.right} y={HEIGHT - 8} className="axis-label end">
          {points[points.length - 1]!.date.toLocaleDateString()}
        </text>
      </svg>

      <figcaption>
        {hovered ? (
          <span>
            <strong>{hovered.value} kg</strong> {t('chart.estimatedShort')} ·{' '}
            {hovered.date.toLocaleDateString()}
          </span>
        ) : (
          <span className="muted small">{t('chart.caption')}</span>
        )}
        <button
          type="button"
          className="button subtle small"
          onClick={() => setShowTable((current) => !current)}
        >
          {showTable ? t('chart.hideTable') : t('chart.viewTable')}
        </button>
      </figcaption>

      {showTable && (
        <table className="data-table">
          <caption className="visually-hidden">
            Estimated one-rep max by date
          </caption>
          <thead>
            <tr>
              <th scope="col">{t('chart.date')}</th>
              <th scope="col">{t('chart.estimated1rm')}</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point, index) => (
              <tr key={index}>
                <td>{point.date.toLocaleDateString()}</td>
                <td>{point.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </figure>
  );
}

/**
 * One point per training day: the best estimate of that session.
 *
 * Plotting every set would draw the warmup ramp as a sawtooth and bury the
 * trend that matters.
 */
function buildPoints(sets: HistorySet[]): Point[] {
  const byDay = new Map<string, Point>();

  for (const set of sets) {
    if (set.estimated_1rm === null) continue;
    const date = new Date(set.performed_at);
    const key = date.toISOString().slice(0, 10);
    const existing = byDay.get(key);
    if (!existing || set.estimated_1rm > existing.value) {
      byDay.set(key, {
        x: new Date(key).getTime(),
        y: 0,
        date,
        value: set.estimated_1rm,
      });
    }
  }

  return [...byDay.values()].sort((a, b) => a.x - b.x);
}
