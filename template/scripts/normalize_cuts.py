#!/usr/bin/env python3
"""Even out the voice level cut by cut, so no clip sounds slightly louder than the next.

Measures each take's integrated loudness (consecutive pieces of one take are grouped) (EBU R128) over the exact source range it uses and
writes a per-cut `gainDb` into src/data/<slug>.json that brings every cut to the same level
(TARGET_CUT LUFS). Reel.tsx uses cut.gainDb when present (else the global data.gainDb).
The final mix is then mastered by master.sh (linear gain + transparent peak limiter).

Usage: python3 -I scripts/normalize_cuts.py src/data/<slug>.json [--target -20]
"""
import json, os, re, subprocess, sys

p = sys.argv[1]
target = float(sys.argv[sys.argv.index('--target') + 1]) if '--target' in sys.argv else -20.0  # headroom: at -16 the quiet iPhone takes (+18 dB) hit 0 dBFS in the raw render
d = json.load(open(p)); fps = d['fps']; pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'public')
# Consecutive pieces of ONE take (same source, next piece starts < 1.5 s after the previous one ends, e.g. after
# tighten.py) share ONE gain measured over the whole take: per-piece gains on 1 s pieces made the level jump.
groups = []
for c in d['cuts']:
    g = groups[-1] if groups else None
    if g and g[-1]['src'] == c['src'] and 0 <= c['srcIn'] - (g[-1]['srcIn'] + g[-1]['dur']) < 1.5 * fps:
        g.append(c)
    else:
        groups.append([c])
for k, g in enumerate(groups):
    a = min(c['srcIn'] for c in g); b = max(c['srcIn'] + c['dur'] for c in g)
    src = os.path.join(pub, g[0]['src'])
    r = subprocess.run(['ffmpeg', '-hide_banner', '-ss', f"{a / fps:.3f}", '-t', f"{(b - a) / fps:.3f}", '-i', src,
                        '-vn', '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r)
    lufs = float(m[-1]) if m else None
    if lufs is None or lufs < -60:  # silence or too short to measure: keep the global gain
        for c in g: c.pop('gainDb', None)
        print(k, 'unmeasured'); continue
    gain = round(max(-6, min(30, target - lufs)), 1)  # clamp: never crush or blow up a cut
    for c in g: c['gainDb'] = gain
    print(k, f'{len(g)} piece(s) {lufs:6.1f} LUFS -> gain {gain:+.1f} dB')
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=1)
