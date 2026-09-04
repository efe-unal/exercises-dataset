/**
 * The animation for one exercise.
 *
 * Shows the still thumbnail until it is tapped, then swaps in the GIF. The
 * animations are far heavier than the thumbnails, and a session lists six to
 * eight of them, so loading every one up front would cost several megabytes
 * on a phone connection for movements the athlete already knows.
 *
 * The Gym visual attribution required by NOTICE.md is attached to the media
 * itself, so it travels with the image wherever this component is used.
 */

import { useState } from 'react';

import { api } from '../lib/api';

const ATTRIBUTION = '© Gym visual — https://gymvisual.com/';

interface Props {
  exercise: { id: string; name: string; image: string; gif_url: string };
  size?: number;
}

export function ExerciseMedia({ exercise, size = 96 }: Props) {
  const [playing, setPlaying] = useState(false);

  return (
    <button
      type="button"
      className="exercise-media"
      style={{ width: size, height: size }}
      onClick={() => setPlaying((current) => !current)}
      aria-label={
        playing
          ? `Stop the animation for ${exercise.name}`
          : `Play the animation for ${exercise.name}`
      }
      title={ATTRIBUTION}
    >
      <img
        src={api.mediaUrl(playing ? exercise.gif_url : exercise.image)}
        alt={exercise.name}
        width={size}
        height={size}
        loading="lazy"
        decoding="async"
      />
      {!playing && <span className="play-hint" aria-hidden="true">▶</span>}
    </button>
  );
}
