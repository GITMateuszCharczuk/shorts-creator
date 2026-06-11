import React from 'react';

// Small persistent brand bug (logo box) in its projected corner region.
export const BrandOverlay: React.FC<{accent?: string | null}> = ({accent}) => (
  <div
    style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: 12,
      border: `3px solid ${accent ?? '#00E5FF'}`,
      color: accent ?? '#00E5FF',
      backgroundColor: 'rgba(11,15,20,0.55)',
      fontFamily: 'Inter, Arial, sans-serif',
      fontWeight: 800,
      fontSize: 28,
      letterSpacing: 2,
    }}
  >
    SC
  </div>
);
