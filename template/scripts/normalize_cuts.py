#!/usr/bin/env python3
"""Even out the voice level cut by cut, so no clip sounds slightly louder than the next.

Measures each cut's integrated loudness (EBU R128) over the exact source range it uses and
writes a per-cut `gainDb` into src/data/<slug>.json that brings every cut to the same level
(TARGET_CUT LUFS). Reel.tsx uses cut.gainDb when present (else the global data.gainDb).
The final mix is then mastered by master.sh (linear gain + transparent peak limiter).

Usage: python3 -I scripts/normalize_cuts.py src/data/<slug>.json [--target -20]
"""
import json, os, re, subprocess, sys

p = sys.argv[1]
target = float(sys.argv[sys.argv.index('--target') + 1]) if '--target' in sys.argv else -20.0  # headroom: at -16 the quiet iPhone takes (+18 dB) hit 0 dBFS in the raw render
d = json.load(open(p)); fps = d['fps']; pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'public')
for k, c in enumerate(d['cuts']):
    src = os.path.join(pub, c['src'])
    r = subprocess.run(['ffmpeg', '-hide_banner', '-ss', f"{c['srcIn'] / fps:.3f}", '-t', f"{c['dur'] / fps:.3f}", '-i', src,
                        '-vn', '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r)
    lufs = float(m[-1]) if m else None
    if lufs is None or lufs < -60:  # silence or too short to measure: keep the global gain
        c.pop('gainDb', None); print(k, 'unmeasured'); continue
    c['gainDb'] = round(max(-6, min(30, target - lufs)), 1)  # clamp: never crush or blow up a cut
    print(k, f'{lufs:6.1f} LUFS -> gain {c["gainDb"]:+.1f} dB')
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=1)
