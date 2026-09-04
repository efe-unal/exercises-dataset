/**
 * Render a load suggestion in the reader's language.
 *
 * The API also sends `reason` as English prose. That stays the fallback: the
 * structured fields — action, weight, rep range — are what a localized
 * sentence is actually built from, so the wording belongs to the client.
 */

import type { Suggestion } from '@exercises/api-client';

import type { Translate } from './i18n';

export function suggestionText(
  t: Translate,
  suggestion: Suggestion,
  loadStepKg: number,
): string {
  const { action, weight_kg, rep_min, rep_max } = suggestion;

  // A bodyweight movement has no load to prescribe, whatever the action.
  if (weight_kg === null && action !== 'establish') {
    return t('suggestion.bodyweight');
  }

  switch (action) {
    case 'establish':
      return t('suggestion.establish', { margin: rep_max - rep_min + 1 });
    case 'add_load':
      return t('suggestion.add_load', {
        repMax: rep_max,
        repMin: rep_min,
        step: loadStepKg,
      });
    case 'deload':
      return t('suggestion.deload', { weight: weight_kg ?? 0 });
    case 'repeat':
      return t('suggestion.repeat', { repMax: rep_max });
    default:
      return suggestion.reason;
  }
}
