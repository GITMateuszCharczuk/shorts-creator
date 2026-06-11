import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';

import {Manifest, RenderManifest} from './Manifest';
import {Badge} from './primitives/Badge';
import {BrandOverlay} from './primitives/BrandOverlay';
import {CTABump} from './primitives/CTABump';
import {CitationChip} from './primitives/CitationChip';
import {DataVizSlot} from './primitives/DataVizSlot';
import {KaraokeCaption} from './primitives/KaraokeCaption';
import {MediaZone} from './primitives/MediaZone';
import {TextCard} from './primitives/TextCard';

const FPS = 30;
const WIDTH = 1080;
const HEIGHT = 1920;
const DEFAULT_FRAMES = 300; // fallback when props carry no scenes (e.g. Studio preview)

// Duration comes from the manifest itself: ceil(max scene end * fps).
const calculateManifestMetadata: CalculateMetadataFunction<RenderManifest> = ({props}) => {
  const fps = props.fps ?? FPS;
  const maxEnd = Math.max(0, ...(props.scenes ?? []).map((s) => s.end));
  return {fps, durationInFrames: maxEnd > 0 ? Math.ceil(maxEnd * fps) : DEFAULT_FRAMES};
};

const size = {width: WIDTH, height: HEIGHT, fps: FPS, durationInFrames: DEFAULT_FRAMES};

// "Manifest" is the full LayoutEngine; each primitive is ALSO registered standalone so 01e
// can render e.g. a single DataVizSlot through the SAME component the Manifest mounts for
// stat_bars — one engine, shared components (ADR 0007a §1/§4).
export const Root: React.FC = () => (
  <>
    <Composition
      id="Manifest"
      component={Manifest}
      {...size}
      defaultProps={{fps: FPS, width: WIDTH, height: HEIGHT, scenes: []}}
      calculateMetadata={calculateManifestMetadata}
    />
    <Composition id="MediaZone" component={MediaZone} {...size} defaultProps={{src: null}} />
    <Composition
      id="TextCard"
      component={TextCard}
      {...size}
      defaultProps={{value: 'Headline', style: {size: 72}}}
    />
    <Composition
      id="Badge"
      component={Badge}
      {...size}
      defaultProps={{value: '#1', params: {}, accent: '#00E5FF'}}
    />
    <Composition
      id="KaraokeCaption"
      component={KaraokeCaption}
      {...size}
      defaultProps={{
        words: [{word: 'Hello', start: 0, end: 1}, {word: 'world', start: 1, end: 2}],
        sceneStart: 0,
        fps: FPS,
        accent: '#00E5FF',
      }}
    />
    <Composition
      id="DataVizSlot"
      component={DataVizSlot}
      {...size}
      defaultProps={{
        spec: {kind: 'bar', series: [{label: 'a', value: 3.2}, {label: 'b', value: 4.5}]},
        accent: '#00E5FF',
      }}
    />
    <Composition
      id="CitationChip"
      component={CitationChip}
      {...size}
      defaultProps={{value: 'Source: BLS'}}
    />
    <Composition
      id="CTABump"
      component={CTABump}
      {...size}
      defaultProps={{verb: 'Follow', accent: '#00E5FF'}}
    />
    <Composition
      id="BrandOverlay"
      component={BrandOverlay}
      {...size}
      defaultProps={{accent: '#00E5FF'}}
    />
  </>
);
