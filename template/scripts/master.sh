#!/bin/zsh
# Final loudness pass on a rendered reel: LINEAR gain to the target loudness (default -16 LUFS), then a
# transparent peak limiter at -1.5 dBFS (0.841 linear) that only touches the odd plosive. Video copied untouched, AAC 320k.
#   Usage: scripts/master.sh in.mp4 out.mp4 [target LUFS, default -16]
# Why not loudnorm: when it can't stay linear (target + true-peak don't fit) it silently switches to dynamic
# mode, a compressor that made the voice sound canned. -14 also felt too loud in testing.
in=$1; out=$2; target=${3:--16}
I=$(ffmpeg -hide_banner -i "$in" -af ebur128 -f null - 2>&1 | grep -E "^\s+I:" | tail -1 | awk '{print $2}')
gain=$(python3 -I -c "print(round($target - ($I), 2))")
ffmpeg -v error -y -i "$in" -c:v copy -af "volume=${gain}dB,alimiter=limit=0.841:attack=3:release=60:level=false,aresample=48000" -c:a aac -b:a 320k "$out"
echo "input $I LUFS, gain ${gain} dB"
ffmpeg -hide_banner -i "$out" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|LRA|Peak):"
