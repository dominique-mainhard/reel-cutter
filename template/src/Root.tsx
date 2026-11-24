import React from "react";
import {Composition} from "remotion";
import {Reel, ReelData} from "./Reel";
import {reels} from "./data";

// "<slug>-base" = the reframed cut only (no visuals, no cutouts):
// the plate the speaker cutout is made from (scripts/cutouts.py).
const plain = (d: ReelData): ReelData => ({...d, layers: undefined, cutouts: undefined});

export const RemotionRoot: React.FC = () => (
  <>
    {reels.flatMap(({id, data}) => [{id, data}, {id: `${id}-base`, data: plain(data)}]).map(({id, data}) => (
      <Composition key={id} id={id} component={Reel} defaultProps={{data}}
        durationInFrames={data.durationInFrames} fps={data.fps} width={data.width} height={data.height} />
    ))}
  </>
);
