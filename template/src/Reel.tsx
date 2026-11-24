// Talking-head reel, 1080×1920. Everything is driven by src/data/<slug>.json (see the ReelData type).
// Paint order, back to front: footage cuts → visual layers (screenshots, recordings, images) → speaker cutout → front layers.
// The speaker cutout (alpha .mov of the person, made from the "<slug>-base" plate by scripts/cutouts.py) is what
// puts the visuals BEHIND the head.
import React from "react";
import {AbsoluteFill, Audio, Easing, getRemotionEnvironment, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from "remotion";

// Studio preview only: browsers can't play iPhone HEVC or ProRes 4444, so scripts/proxies.py makes
// light WebM copies in media/proxy/ and sets data.proxies. Renders and stills always use the originals.
let USE_PROXIES = false;
const videoFile = (src: string) =>
  staticFile(USE_PROXIES && getRemotionEnvironment().isStudio ? src.replace(/^media\//, "media/proxy/").replace(/\.[^./]+$/, ".webm") : src);

// zoom/center: base framing of the cut. zoomTo/zoomFrames: a subtle push-in WITHIN the cut (zoom -> zoomTo, eased).
// zoomEase "out": a fast emphasis punch instead of a slow push-in.
export type Cut = {src: string; from: number; dur: number; srcIn: number; zoom: number; zoomTo?: number; zoomFrames?: number; zoomEase?: "inOut" | "out"; center: [number, number]; gainDb?: number};
type Box = {left: number; top: number; width: number; height: number; objectPosition?: string};
export type Crop = {x: number; y: number; w: number; h: number};
// front: drawn OVER the person (no cutout needed). anim "none": cuts in/out raw (memes, jokes). click: override the sound.
export type Layer = {kind: "image" | "video"; src: string; from: number; dur: number; box: Box; crop?: Crop;
  look?: "collage" | "card" | "plain"; anim?: "pop" | "none"; click?: "main" | "soft" | "none"; front?: boolean};
export type ReelData = {
  fps: number; width: number; height: number; durationInFrames: number;
  cuts: Cut[]; layers?: Layer[]; cutouts?: {src: string; from: number; dur: number}[];
  gainDb?: number; proxies?: boolean; clickVolume?: number;
};

const CLICK_VOLUME = 0.5; // noticeable but discreet next to a −16 LUFS voice; 0.2 is inaudible

// Clicks when visuals appear (scripts/make_click.sh): sfx/click.wav = a real mouse click, for a visual that appears
// on its own; sfx/click-soft.wav = a subtler click, the SAME one for every item of a run (3+ visuals each within 2 s
// of the previous), because the viewer hears it several times in a row. Layer.click overrides ("main" | "soft" | "none").
const Click: React.FC<{at: number; volume: number; soft?: boolean}> = ({at, volume, soft}) => (
  <Sequence from={at} durationInFrames={12}><Audio src={staticFile(soft ? "sfx/click-soft.wav" : "sfx/click.wav")} volume={soft ? volume * 0.8 : volume} /></Sequence>
);
const clickKinds = (layers: Layer[], fps = 30): ("main" | "soft" | "none")[] => {
  const order = layers.map((l, i) => [l.from, i]).sort((a, b) => a[0] - b[0]).map(([, i]) => i);
  const kind: ("main" | "soft" | "none")[] = layers.map(() => "main");
  let run: number[] = [];
  const flush = () => { if (run.length >= 3) run.forEach((i) => (kind[i] = "soft")); run = []; };
  for (const i of order) {
    if (run.length && layers[i].from - layers[run[run.length - 1]].from > 2 * fps) flush();
    run.push(i);
  }
  flush();
  return layers.map((l, i) => l.click ?? (l.anim === "none" ? "none" : kind[i]));
};

const fadeOut = (f: number, dur: number) => interpolate(f, [dur - 6, dur], [1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});

// One cut of the footage, reframed. Plain cuts only (no transitions).
const CutClip: React.FC<{cut: Cut; W: number; H: number; gain: number}> = ({cut, W, H, gain}) => {
  const f = useCurrentFrame();
  // Base framing: zoom around center, clamped so the frame stays covered (no black edges).
  const z = cut.zoom;
  const cx = Math.min(Math.max(cut.center[0], 0.5 / z), 1 - 0.5 / z), cy = Math.min(Math.max(cut.center[1], 0.5 / z), 1 - 0.5 / z);
  // Push-in = a pure SCALE around the centre point (the face), never a pan: moving the frame while zooming
  // looks like a handheld camera. zoomFrames 0/1 = already pushed in (hold the same framing on the next cuts).
  const k = !cut.zoomTo ? 1
    : (cut.zoomFrames ?? 60) <= 1 ? cut.zoomTo / z
    : interpolate(f, [0, cut.zoomFrames ?? 60], [1, cut.zoomTo / z], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: cut.zoomEase === "out" ? Easing.out(Easing.cubic) : Easing.inOut(Easing.sin)});
  // A little blur while a fast emphasis punch moves sells the speed.
  const punchBlur = cut.zoomEase === "out" && cut.zoomTo ? Math.sin(Math.PI * Math.min(1, Math.max(0, f / (cut.zoomFrames ?? 8)))) * 6 : 0;
  const left = W / 2 - cx * W * z, top = H / 2 - cy * H * z;
  return (
    <AbsoluteFill style={{overflow: "hidden"}}>
      <OffthreadVideo
        src={videoFile(cut.src)}
        startFrom={cut.srcIn}
        volume={gain}
        style={{position: "absolute", width: W * z, height: H * z, left, top, transform: k !== 1 ? `scale(${k})` : undefined,
          filter: punchBlur > 0.3 ? `blur(${punchBlur.toFixed(1)}px)` : undefined,
          transformOrigin: `${cut.center[0] * W * z}px ${cut.center[1] * H * z}px`}}
      />
    </AbsoluteFill>
  );
};

// Visual layers. Default look "collage": square corners, no frame, faint shadow, uneven sizes/positions (hand-made feel).
// "card": white rounded card with a strong shadow. "plain": images with their own shape and transparency (no box,
// a drop-shadow that follows the shape).
const COLLAGE: React.CSSProperties = {position: "absolute", overflow: "hidden", boxShadow: "0 8px 24px rgba(0,0,0,.18)"};
const PLAIN: React.CSSProperties = {position: "absolute", filter: "drop-shadow(0 10px 24px rgba(0,0,0,.28))"};
const CARD: React.CSSProperties = {position: "absolute", borderRadius: 36, overflow: "hidden", boxShadow: "0 24px 70px rgba(0,0,0,.45)", background: "#fff"};

// A layer pops in (8 frames: scale .9 -> 1, fade in) and fades out (6 frames).
const Pop: React.FC<{dur: number; children: React.ReactNode}> = ({dur, children}) => {
  const f = useCurrentFrame();
  const inP = interpolate(f, [0, 8], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const scale = 0.9 + 0.1 * (1 - Math.pow(1 - inP, 3));
  return <AbsoluteFill style={{opacity: Math.min(inP, fadeOut(f, dur)), transform: `scale(${scale})`, transformOrigin: "50% 25%"}}>{children}</AbsoluteFill>;
};
const Raw: React.FC<{dur: number; children: React.ReactNode}> = ({children}) => <AbsoluteFill>{children}</AbsoluteFill>;

const LayerView: React.FC<{l: Layer}> = ({l}) => {
  const Wrap = l.anim === "none" ? Raw : Pop;
  const {box, crop} = l;
  // crop = normalized source rect shown (zooms into the useful part of a screen recording)
  const style: React.CSSProperties = crop
    ? {position: "absolute", width: box.width / crop.w, height: box.height / crop.h, left: -crop.x * box.width / crop.w, top: -crop.y * box.height / crop.h, objectFit: "fill"}
    : {width: "100%", height: "100%", objectFit: "cover", objectPosition: box.objectPosition ?? "50% 0%"};
  return (
    <Wrap dur={l.dur}>
      <div style={{...(l.look === "card" ? CARD : l.look === "plain" ? PLAIN : COLLAGE), left: box.left, top: box.top, width: box.width, height: box.height}}>
        {l.kind === "video" ? <OffthreadVideo src={videoFile(l.src)} muted style={style} /> : <Img src={staticFile(l.src)} style={style} />}
      </div>
    </Wrap>
  );
};

export const Reel: React.FC<{data: ReelData}> = ({data}) => {
  const {width: W, height: H, cuts} = data;
  USE_PROXIES = !!data.proxies;
  const click = data.clickVolume ?? CLICK_VOLUME;
  const layers = data.layers ?? [];
  const kinds = clickKinds(layers, data.fps ?? 30);
  return (
    <AbsoluteFill style={{backgroundColor: "black"}}>
      {cuts.map((c, k) => (
        <Sequence key={k} from={c.from} durationInFrames={c.dur} premountFor={30}>
          <CutClip cut={c} W={W} H={H} gain={Math.pow(10, (c.gainDb ?? data.gainDb ?? 0) / 20)} />
        </Sequence>
      ))}
      {layers.map((l, k) => l.front ? null : (
        <Sequence key={`l${k}`} from={l.from} durationInFrames={l.dur} premountFor={30}><LayerView l={l} /></Sequence>
      ))}
      {(data.cutouts ?? []).map((c, k) => (
        <Sequence key={`k${k}`} from={c.from} durationInFrames={c.dur} premountFor={30}>
          <AbsoluteFill><OffthreadVideo src={videoFile(c.src)} muted transparent style={{width: W, height: H}} /></AbsoluteFill>
        </Sequence>
      ))}
      {layers.map((l, k) => l.front ? (
        <Sequence key={`lf${k}`} from={l.from} durationInFrames={l.dur} premountFor={30}><LayerView l={l} /></Sequence>
      ) : null)}
      {layers.map((l, k) => kinds[k] === "none" ? null : <Click key={`s${k}`} at={l.from} volume={click} soft={kinds[k] === "soft"} />)}
    </AbsoluteFill>
  );
};
