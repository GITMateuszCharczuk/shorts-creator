import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';

export type ChartSpec = {
  kind?: string;
  series?: {label: string; value: number}[];
  accent?: string;
};

const FONT = 'Inter, Arial, sans-serif';

// Bar chart from a chart_spec {series:[{label,value}], accent}. Bars are scaled to the max
// |value| and count up via interpolate on the frame — deterministic (no Date.now/random).
export const DataVizSlot: React.FC<{spec?: ChartSpec | null; accent?: string | null}> = ({
  spec,
  accent,
}) => {
  const frame = useCurrentFrame();
  const grow = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const series = spec?.series ?? [];
  const max = Math.max(1e-9, ...series.map((s) => Math.abs(s.value)));
  const color = spec?.accent ?? accent ?? '#00E5FF';
  const row: React.CSSProperties = {
    width: '100%', height: '100%', display: 'flex', alignItems: 'flex-end',
    gap: 28, padding: 16, boxSizing: 'border-box',
  };
  const col: React.CSSProperties = {
    flex: 1, height: '100%', display: 'flex', flexDirection: 'column',
    justifyContent: 'flex-end', alignItems: 'center', color: '#FFFFFF', fontFamily: FONT,
  };
  return (
    <div style={row}>
      {series.map((s) => (
        <div key={s.label} style={col}>
          <div style={{fontSize: 30, fontWeight: 800}}>{Math.round(s.value * grow * 10) / 10}</div>
          <div
            style={{
              width: '60%',
              height: `${(Math.abs(s.value) / max) * grow * 68}%`,
              backgroundColor: color,
              borderRadius: 8,
              marginTop: 6,
            }}
          />
          <div style={{fontSize: 24, marginTop: 8, opacity: 0.85}}>{s.label}</div>
        </div>
      ))}
    </div>
  );
};
