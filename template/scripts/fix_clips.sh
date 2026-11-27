#!/bin/zsh
# Review clip of ONLY the corrected spots, instead of a full draft: full drafts of a long reel take minutes at
# every core and make a laptop's fans loud, and most review rounds change only a few spots.
# Each range gets 1 s of context on each side, half res, 2 render threads at low priority (quieter, slower),
# joined in order and mastered. Times are TIMELINE seconds of the edited reel (as in the .srt).
#   Usage (project root): ./scripts/fix_clips.sh <slug> <out.mp4> <from>-<to> [<from>-<to> ...]
#   e.g.  ./scripts/fix_clips.sh my-reel "<video folder>/my-reel-FIXES.mp4" 41.2-43.5 117-119
set -e
slug=$1; out=$2; shift 2
data=src/data/$slug.json
read fps total < <(python3 -I -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['fps'],d['durationInFrames'])" "$data")
tmp=$(mktemp -d); list=$tmp/list.txt; i=0
for r in "$@"; do
  a=${r%-*}; b=${r#*-}
  read fa fb < <(python3 -I -c "import sys;a,b,f,t=map(float,sys.argv[1:]);print(max(0,round((a-1)*f)),min(int(t)-1,round((b+1)*f)))" $a $b $fps $total)
  i=$((i+1))
  echo "clip $i: ${a}-${b} s (frames $fa-$fb)"
  nice -n 15 npx remotion render "$slug" "$tmp/c$i.mp4" --frames=$fa-$fb --scale=0.5 --crf=23 --concurrency=2 --log=error
  echo "file '$tmp/c$i.mp4'" >> "$list"
done
ffmpeg -v error -y -f concat -safe 0 -i "$list" -c copy "$tmp/joined.mp4"
"${0:A:h}/master.sh" "$tmp/joined.mp4" "$out"
rm -rf "$tmp"
echo "-> $out"
