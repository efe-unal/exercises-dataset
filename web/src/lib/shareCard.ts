/**
 * Renders a workout as an image the athlete can post anywhere.
 *
 * This is the part of the social layer that works on day one, before anybody
 * else has an account: the audience is already on WhatsApp and Instagram, so
 * the card goes to them rather than asking them to come here first. The
 * profile link on the card is the way back.
 *
 * Drawn on a canvas rather than rendered server-side because the app is a
 * static front end with no image renderer behind it, and because a canvas
 * lets the phone hand the file straight to the share sheet.
 */

const WIDTH = 1080;
const HEIGHT = 1350; // 4:5, the tallest ratio Instagram shows uncropped
const PADDING = 88;

export interface ShareCardData {
  dayName: string;
  caption: string | null;
  totalSets: number;
  totalVolumeKg: number;
  exercises: Array<{
    name: string;
    sets: number;
    best_weight_kg: number | null;
    total_reps: number;
  }>;
  username: string;
  displayName: string;
  profileUrl: string;
  /** Translated labels, so the card speaks the athlete's language. */
  labels: {
    sets: string;
    volume: string;
    exercises: string;
    andMore: string;
    reps: string;
  };
}

/** Card colours, fixed rather than themed: the card leaves the app. */
const INK = '#12120f';
const INK_SOFT = '#5c5b55';
const SURFACE = '#fcfcfb';
const ACCENT = '#2a78d6';

export async function renderShareCard(data: ShareCardData): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('this browser cannot draw the share card');

  ctx.fillStyle = SURFACE;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);

  // A block of accent along the top edge, so the card reads as one thing
  // rather than as a screenshot.
  ctx.fillStyle = ACCENT;
  ctx.fillRect(0, 0, WIDTH, 16);

  let y = PADDING + 40;

  ctx.fillStyle = INK_SOFT;
  ctx.font = '500 34px system-ui, -apple-system, sans-serif';
  ctx.fillText(data.displayName || `@${data.username}`, PADDING, y);

  y += 96;
  ctx.fillStyle = INK;
  ctx.font = '700 84px system-ui, -apple-system, sans-serif';
  y = wrapText(ctx, data.dayName, PADDING, y, WIDTH - PADDING * 2, 92);

  if (data.caption) {
    y += 56;
    ctx.fillStyle = INK_SOFT;
    ctx.font = '400 40px system-ui, -apple-system, sans-serif';
    y = wrapText(ctx, data.caption, PADDING, y, WIDTH - PADDING * 2, 52, 3);
  }

  // The two numbers worth reading at a glance.
  y += 96;
  drawStat(ctx, PADDING, y, String(data.totalSets), data.labels.sets);
  drawStat(ctx, WIDTH / 2, y, `${Math.round(data.totalVolumeKg).toLocaleString()} kg`,
           data.labels.volume);

  y += 150;
  ctx.strokeStyle = '#e2e2db';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(PADDING, y);
  ctx.lineTo(WIDTH - PADDING, y);
  ctx.stroke();

  y += 72;
  ctx.fillStyle = INK_SOFT;
  ctx.font = '600 30px system-ui, -apple-system, sans-serif';
  ctx.fillText(data.labels.exercises.toUpperCase(), PADDING, y);

  y += 62;
  // Six lines is what fits without the type having to shrink; the rest are
  // summarised rather than crammed in.
  const shown = data.exercises.slice(0, 6);
  for (const exercise of shown) {
    ctx.fillStyle = INK;
    ctx.font = '500 40px system-ui, -apple-system, sans-serif';
    const name = truncate(ctx, exercise.name, WIDTH - PADDING * 2 - 260);
    ctx.fillText(name, PADDING, y);

    ctx.fillStyle = INK_SOFT;
    ctx.font = '400 36px system-ui, -apple-system, sans-serif';
    // Bodyweight work has no load to show, so the reps carry the line —
    // "3 ×" on its own reads as a sentence cut in half.
    const detail = exercise.best_weight_kg
      ? `${exercise.sets} × ${exercise.best_weight_kg} kg`
      : `${exercise.sets} × ${exercise.total_reps} ${data.labels.reps}`;
    ctx.textAlign = 'right';
    ctx.fillText(detail, WIDTH - PADDING, y);
    ctx.textAlign = 'left';
    y += 62;
  }

  const remaining = data.exercises.length - shown.length;
  if (remaining > 0) {
    ctx.fillStyle = INK_SOFT;
    ctx.font = '400 34px system-ui, -apple-system, sans-serif';
    ctx.fillText(data.labels.andMore.replace('{count}', String(remaining)),
                 PADDING, y);
  }

  // The way back: the handle, bottom-left, where a reader looks last.
  ctx.fillStyle = ACCENT;
  ctx.font = '600 38px system-ui, -apple-system, sans-serif';
  ctx.fillText(`@${data.username}`, PADDING, HEIGHT - PADDING);

  ctx.fillStyle = INK_SOFT;
  ctx.font = '400 28px system-ui, -apple-system, sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(hostOf(data.profileUrl), WIDTH - PADDING, HEIGHT - PADDING);
  ctx.textAlign = 'left';

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('could not encode the card'))),
      'image/png',
    );
  });
}

/**
 * Hand the card to the phone's share sheet, or fall back to a download.
 *
 * Returns how it was delivered, so the caller can tell the athlete what just
 * happened — a silent download on a desktop otherwise looks like nothing.
 */
export async function shareCard(
  blob: Blob,
  data: { username: string; profileUrl: string; dayName: string },
): Promise<'shared' | 'downloaded'> {
  const file = new File([blob], `workout-${data.username}.png`,
                        { type: 'image/png' });

  const canShareFiles =
    typeof navigator !== 'undefined' &&
    typeof navigator.canShare === 'function' &&
    navigator.canShare({ files: [file] });

  if (canShareFiles) {
    try {
      await navigator.share({
        files: [file],
        text: `${data.dayName} — ${data.profileUrl}`,
      });
      return 'shared';
    } catch (error) {
      // A cancelled share sheet is not a failure, and must not then dump a
      // file into the athlete's downloads folder behind their back.
      if (error instanceof DOMException && error.name === 'AbortError') {
        return 'shared';
      }
    }
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = file.name;
  link.click();
  URL.revokeObjectURL(url);
  return 'downloaded';
}

// --- drawing helpers --------------------------------------------------
function drawStat(ctx: CanvasRenderingContext2D, x: number, y: number,
                  value: string, label: string): void {
  ctx.fillStyle = INK;
  ctx.font = '700 72px system-ui, -apple-system, sans-serif';
  ctx.fillText(value, x, y);
  ctx.fillStyle = INK_SOFT;
  ctx.font = '400 32px system-ui, -apple-system, sans-serif';
  ctx.fillText(label, x, y + 46);
}

/** Draw wrapped text, returning the baseline after the last line. */
function wrapText(ctx: CanvasRenderingContext2D, text: string, x: number,
                  y: number, maxWidth: number, lineHeight: number,
                  maxLines = 2): number {
  const words = text.split(/\s+/);
  let line = '';
  let lines = 0;

  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (ctx.measureText(candidate).width > maxWidth && line) {
      lines += 1;
      if (lines === maxLines) {
        ctx.fillText(`${line}…`, x, y);
        return y;
      }
      ctx.fillText(line, x, y);
      y += lineHeight;
      line = word;
    } else {
      line = candidate;
    }
  }
  ctx.fillText(line, x, y);
  return y;
}

function truncate(ctx: CanvasRenderingContext2D, text: string,
                  maxWidth: number): string {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let cut = text;
  while (cut.length > 1 && ctx.measureText(`${cut}…`).width > maxWidth) {
    cut = cut.slice(0, -1);
  }
  return `${cut}…`;
}

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}
