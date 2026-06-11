import React from 'react';

// Styled text block; the brand kit style (e.g. {"size": 72}) drives the font size.
export const TextCard: React.FC<{
  value?: unknown;
  style?: Record<string, unknown>;
}> = ({value, style}) => {
  const size = typeof style?.size === 'number' ? style.size : 56;
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#FFFFFF',
        fontFamily: 'Inter, Arial, sans-serif',
        fontWeight: 700,
        fontSize: size,
        lineHeight: 1.1,
        textAlign: 'center',
        textShadow: '0 2px 12px rgba(0,0,0,0.6)',
      }}
    >
      {value == null ? '' : String(value)}
    </div>
  );
};
