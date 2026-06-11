import React from 'react';
import {useCurrentFrame} from 'remotion';

export type Word = {word?: string; start: number; end: number; emphasis?: boolean};

// Word-timed caption: words carry ABSOLUTE timestamps (seconds) but useCurrentFrame()
// is Sequence-relative, so the scene start is added back to get wall-clock time.
// The word whose [start, end) contains the current time is highlighted.
export const KaraokeCaption: React.FC<{
  words?: Word[];
  sceneStart?: number;
  fps?: number;
  accent?: string | null;
}> = ({words, sceneStart, fps, accent}) => {
  const frame = useCurrentFrame();
  const t = (sceneStart ?? 0) + frame / (fps ?? 30);
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'Inter, Arial, sans-serif',
        fontWeight: 800,
        fontSize: 52,
        textShadow: '0 2px 10px rgba(0,0,0,0.8)',
      }}
    >
      {(words ?? []).map((w, i) => {
        const hot = t >= w.start && t < w.end;
        return (
          <span key={i} style={{color: hot ? (accent ?? '#00E5FF') : '#FFFFFF', margin: '0 10px'}}>
            {w.word ?? ''}
          </span>
        );
      })}
    </div>
  );
};
