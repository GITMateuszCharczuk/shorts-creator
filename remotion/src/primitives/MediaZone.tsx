import React from 'react';
import {Img, OffthreadVideo} from 'remotion';

const BRAND_DARK = '#0B0F14';
const IMAGE_EXT = /\.(png|jpe?g|webp|gif|bmp|avif)$/i;

// Cover-fit media region. Falls back to a solid brand-dark panel when the visual
// lane chose no clip for this beat (src === null) — never an empty/broken frame.
export const MediaZone: React.FC<{src?: string | null}> = ({src}) => {
  if (!src) {
    return <div style={{width: '100%', height: '100%', backgroundColor: BRAND_DARK}} />;
  }
  const fit: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover'};
  return IMAGE_EXT.test(src) ? (
    <Img src={src} style={fit} />
  ) : (
    <OffthreadVideo src={src} style={fit} muted />
  );
};
