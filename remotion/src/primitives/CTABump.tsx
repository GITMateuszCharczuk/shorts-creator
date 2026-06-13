import React from 'react';

// Mid-roll call-to-action pill; the verb comes from the region's primitive params.
export const CTABump: React.FC<{verb?: string; accent?: string | null}> = ({verb, accent}) => (
  <div
    style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}
  >
    <div
      style={{
        padding: '14px 44px',
        borderRadius: 999,
        backgroundColor: accent ?? '#00E5FF',
        color: '#0B0F14',
        fontFamily: 'Inter, Arial, sans-serif',
        fontWeight: 800,
        fontSize: 44,
      }}
    >
      {verb ?? 'Follow'}
    </div>
  </div>
);
