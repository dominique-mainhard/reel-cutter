#!/usr/bin/env python3
"""Checks a reel's data for mistakes that are easy to miss by eye (run before EVERY draft render).

Usage (project root): python3 -I scripts/qa_check.py src/data/<slug>.json

Problems (exit code 1):
1. SHORT    caption cues shorter than 6 frames: whisper collapsed the timestamps (after a shot change, over music),
            the cue flashes and reads as missing. Re-time it from the audio (envelope.py).
2. PAN      a jump zoom that also moves the frame: two pieces of one continuous take with different zooms must keep
            the same source point at the centre of the screen (same `center`, and not pushed off by the edge clamp).
3. MISSING  a cut, layer or hold whose file is not in public/media.
4. LOW      the caption line sits too low: two wrapped lines would go under the platform's bottom UI (y > 1700).
Reminders (printed, not counted):
5. OVER     a caption on screen while a visual covers the caption band: check that neither hides the other.
6. GAP      more than 10 s without a visual (zooms and captions don't count).
"""
import json, os, sys

d = json.load(open(sys.argv[1]))
fps = d.get('fps', 30)
cuts, layers, caps = d['cuts'], d.get('layers', []), d.get('captions', [])
bad = 0

for c in caps:
    if c['to'] - c['from'] < 6:
        bad += 1
        print(f"SHORT    cue {c['from']}-{c['to']} '{c['text']}' lasts {c['to'] - c['from']} frames -> re-time it from the audio")


def eff_center(c):  # the source point that ends up at the centre of the screen (Reel.tsx clamps it to avoid black edges)
    z = c['zoom']
    return tuple(round(min(max(v, 0.5 / z), 1 - 0.5 / z), 3) for v in c['center'])


for a, b in zip(cuts, cuts[1:]):
    continuous = a['src'] == b['src'] and abs(a['srcIn'] + a['dur'] - b['srcIn']) <= 1
    if continuous and abs(a['zoom'] - b['zoom']) > 0.01 and eff_center(a) != eff_center(b):
        bad += 1
        print(f"PAN      cuts at {a['from']} and {b['from']}: zoom {a['zoom']} -> {b['zoom']} also moves the frame "
              f"({eff_center(a)} -> {eff_center(b)}) -> same center on both pieces, or [0.5, 0.5]")

media = os.path.join('public', 'media')
srcs = [c['src'] for c in cuts] + [l['src'] for l in layers if l.get('src')] + ([d['hold']['src']] if d.get('hold') else [])
for s in sorted(set(srcs)):
    if not os.path.exists(os.path.join('public', s)):
        bad += 1
        print(f"MISSING  {s} (public/media -> {os.path.realpath(media)})")

top = d.get('captionTop', 1240)
if caps and top + 2 * 65 > 1700:
    bad += 1
    print(f"LOW      captionTop {top}: a 2-line cue ends at ~{top + 130}, under the bottom UI (y > 1700)")

for c in caps:
    ct = c.get('top', top)
    for l in layers:
        b = l.get('box') or {}
        if l['from'] < c['to'] and l['from'] + l['dur'] > c['from'] and b and b['top'] < ct + 130 and b['top'] + b['height'] > ct:
            print(f"OVER     cue {c['from']} '{c['text']}' and visual {l.get('src')} ({l['from']}-{l['from'] + l['dur']}) share the caption band")
            break

marks = sorted((l['from'], l['from'] + l['dur']) for l in layers)
t, end = 0, d['durationInFrames']
for a, b in marks + [(end, end)]:
    if a - t > 10 * fps:
        print(f"GAP      {t / fps:.1f}-{a / fps:.1f} s without a visual ({(a - t) / fps:.1f} s)")
    t = max(t, b)

print('qa OK' if not bad else f'{bad} problem(s)')
sys.exit(1 if bad else 0)
