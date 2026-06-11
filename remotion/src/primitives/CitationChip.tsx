import React from 'react';

// Small source-attribution chip (e.g. "Source: BLS").
export const CitationChip: React.FC<{value?: unknown}> = ({value}) => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      maxWidth: '100%',
      height: '100%',
      padding: '0 18px',
      borderRadius: 999,
      backgroundColor: 'rgba(255,255,255,0.12)',
      color: '#E6EAF0',
      fontFamily: 'Inter, Arial, sans-serif',
      fontSize: 24,
      whiteSpace: 'nowrap',
      overflow: 'hidden',
    }}
  >
    {value == null ? '' : String(value)}
  </div>
);
