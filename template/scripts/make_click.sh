#!/bin/zsh
# The two clicks played when visuals appear (see Click in src/Reel.tsx). Use REAL recorded clicks: synthesized ones
# sound fake. Sound files are not shipped with the skill (licenses): download them yourself (e.g. a free mouse-click
# sound from Pixabay) and check the license allows use in published videos.
#   sfx/click.wav      a mouse click, for a visual that appears on its own
#   sfx/click-soft.wav a subtler click, for runs of 3+ visuals in a row (defaults to the same file; Reel.tsx plays it softer)
# Usage (project root): ./scripts/make_click.sh <main click file> [<soft click file>]
cd "$(dirname "$0")/.." && mkdir -p public/sfx
MAIN=${1:?give a real mouse-click sound file (e.g. one from pixabay.com)}
SOFT=${2:-$MAIN}
mk() { ffmpeg -v error -y -i "$1" -ar 48000 -ac 2 -af "loudnorm=I=-20:TP=-3,atrim=0:0.4" "public/sfx/$2.wav" && echo "public/sfx/$2.wav <- $1"; }
mk "$MAIN" click && mk "$SOFT" click-soft
