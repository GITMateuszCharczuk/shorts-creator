import React from 'react';

// Circle/stamp badge: shows the bound value, or the authored params.content for static binds.
export const Badge: React.FC<{
  value?: unknown;
  params?: Record<string, unknown>;
  accent?: string | null;
}> = ({value, params, accent}) => {
  const text = value ?? params?.content ?? '';
  return (
    <div
      style={{
        height: '100%',
        aspectRatio: '1 / 1',
        margin: '0 auto',
        borderRadius: '50%',
        backgroundColor: accent ?? '#00E5FF',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#0B0F14',
        fontFamily: 'Inter, Arial, sans-serif',
        fontWeight: 800,
        fontSize: 44,
      }}
    >
      {String(text)}
    </div>
  );
};
