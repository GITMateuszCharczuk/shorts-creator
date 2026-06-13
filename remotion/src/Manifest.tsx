import React from 'react';
import {AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

import {Badge} from './primitives/Badge';
import {BrandOverlay} from './primitives/BrandOverlay';
import {CTABump} from './primitives/CTABump';
import {CitationChip} from './primitives/CitationChip';
import {ChartSpec, DataVizSlot} from './primitives/DataVizSlot';
import {KaraokeCaption, Word} from './primitives/KaraokeCaption';
import {MediaZone} from './primitives/MediaZone';
import {TextCard} from './primitives/TextCard';

export type Rect = {x: number; y: number; w: number; h: number};

export type Region = {
  name: string;
  primitive: {type: string; params?: Record<string, unknown>};
  rect: Rect;
  z: number;
  enter: string;
  exit: string;
  value: unknown;
  style?: Record<string, unknown>;
  src?: string | null; // MediaZone only: the visual lane's chosen clip (assets.json join)
};

export type Scene = {start: number; end: number; kind: string; regions: Region[]};

export type RenderManifest = {
  schema_version?: string;
  fps: number;
  width?: number;
  height?: number;
  seed?: number;
  accent?: string | null;
  safe_rect?: Rect;
  markers?: Record<string, number>;
  scenes: Scene[];
};

const ENTER_FRAMES = 10;

// Enter animation by name, evaluated on the Sequence-relative frame. count_up_stagger and
// riser_reveal map to plain fade for M2 — per-element stagger/reveal refinement is M3.
const useEnter = (enter: string, fps: number): {style: React.CSSProperties; progress: number} => {
  const frame = useCurrentFrame();
  const name = enter === 'count_up_stagger' || enter === 'riser_reveal' ? 'fade' : enter;
  const p = interpolate(frame, [0, ENTER_FRAMES], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  switch (name) {
    case 'fade':
      return {style: {opacity: p}, progress: p};
    case 'pop':
      return {style: {transform: `scale(${spring({frame, fps})})`}, progress: p};
    case 'slide_in_up':
      return {style: {transform: `translateY(${(1 - p) * 60}px)`, opacity: p}, progress: p};
    case 'slide_in_down':
      return {style: {transform: `translateY(${(p - 1) * 60}px)`, opacity: p}, progress: p};
    case 'count_up': // no transform — the numeric value itself tweens (see RegionView)
      return {style: {}, progress: p};
    default: // 'none' and unknown names render fully visible immediately
      return {style: {}, progress: 1};
  }
};

const Primitive: React.FC<{region: Region; value: unknown; scene: Scene; accent: string | null}> = ({
  region,
  value,
  scene,
  accent,
}) => {
  const {fps} = useVideoConfig();
  const params = region.primitive.params ?? {};
  switch (region.primitive.type) {
    case 'MediaZone':
      return <MediaZone src={region.src ?? null} />;
    case 'TextCard':
      return <TextCard value={value} style={region.style ?? {}} />;
    case 'Badge':
      return <Badge value={value} params={params} accent={accent} />;
    case 'KaraokeCaption':
      return (
        <KaraokeCaption
          words={(Array.isArray(value) ? value : []) as Word[]}
          sceneStart={scene.start}
          fps={fps}
          accent={accent}
        />
      );
    case 'DataVizSlot':
      return <DataVizSlot spec={(value ?? null) as ChartSpec | null} accent={accent} />;
    case 'CitationChip':
      return <CitationChip value={value} />;
    case 'CTABump':
      return <CTABump verb={typeof params.verb === 'string' ? params.verb : 'Follow'} accent={accent} />;
    case 'BrandOverlay':
      return <BrandOverlay accent={accent} />;
    default:
      return null; // unknown primitive types render nothing rather than crash the frame
  }
};

const RegionView: React.FC<{region: Region; scene: Scene; accent: string | null}> = ({
  region,
  scene,
  accent,
}) => {
  const {fps} = useVideoConfig();
  const {style: enterStyle, progress} = useEnter(region.enter, fps);
  // count_up: tween the displayed number itself (one decimal) when the bound value is numeric.
  const value =
    region.enter === 'count_up' && typeof region.value === 'number'
      ? Math.round(region.value * progress * 10) / 10
      : region.value;
  return (
    <div
      style={{
        position: 'absolute', // rects are ALREADY-PROJECTED pixel boxes (resolve did grid->px)
        left: region.rect.x,
        top: region.rect.y,
        width: region.rect.w,
        height: region.rect.h,
        zIndex: region.z,
        ...enterStyle,
      }}
    >
      <Primitive region={region} value={value} scene={scene} accent={accent} />
    </div>
  );
};

export const Manifest: React.FC<RenderManifest> = (manifest) => {
  const fps = manifest.fps ?? 30;
  const accent = manifest.accent ?? null;
  return (
    <AbsoluteFill style={{backgroundColor: '#0B0F14'}}>
      {(manifest.scenes ?? []).map((scene, i) => (
        <Sequence
          key={i}
          from={Math.round(scene.start * fps)}
          durationInFrames={Math.max(1, Math.round((scene.end - scene.start) * fps))}
        >
          {[...scene.regions]
            .sort((a, b) => a.z - b.z)
            .map((r) => (
              <RegionView key={r.name} region={r} scene={scene} accent={accent} />
            ))}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
