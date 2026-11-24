#!/usr/bin/env python3
"""Make the speaker cutout (person on a transparent background) wherever something must sit BEHIND the head:
every visual layer in src/data/<slug>.json (except front: true ones, which sit over the person).

1. Renders the clean plate ("<slug>-base": cut + zooms, nothing on top).
2. Merges the layer windows (±6 frames, joining gaps < 30 frames).
3. Cuts each window out of the plate and runs `npx hyperframes remove-background` (local, ~80 ms/frame on
   Apple silicon) -> public/media/<slug>-cutout-<from>-<to>.mov (ProRes 4444 with alpha).
4. Writes the windows into data["cutouts"].

Re-run it after ANY change to cuts or zooms (the plate changes). Windows whose .mov already
exists are reused unless --force (use --force when the plate changed).

Usage (project root): python3 -I scripts/cutouts.py <slug> [--force]
"""
import json, os, subprocess, sys, tempfile

slug, force = sys.argv[1], '--force' in sys.argv
p = f'src/data/{slug}.json'
d = json.load(open(p))
N = d['durationInFrames']
# front: true items are drawn over the person, so they need no cutout
spans = sorted([(max(0, x['from'] - 6), min(N, x['from'] + x['dur'] + 6)) for x in d.get('layers', []) if not x.get('front')])
win = []
for a, b in spans:
    if win and a - win[-1][1] < 30:
        win[-1][1] = max(win[-1][1], b)
    else:
        win.append([a, b])
if not win:
    sys.exit('nothing behind the head (no layers without front): no cutout needed')

names = [f'{slug}-cutout-{a}-{b}.mov' for a, b in win]
todo = [(a, b, n) for (a, b), n in zip(win, names) if force or not os.path.exists(f'public/media/{n}')]
if todo:
    tmp = tempfile.mkdtemp(prefix='cutouts-')
    plate = os.path.join(tmp, 'base.mp4')
    subprocess.run(['npx', 'remotion', 'render', f'{slug}-base', plate, '--codec=h264', '--crf=12', '--jpeg-quality=95', '--muted'], check=True)
    for a, b, n in todo:
        seg = os.path.join(tmp, f'seg_{a}.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', plate, '-vf', f'trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS',
                        '-an', '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', seg], check=True)
        subprocess.run(['npx', '--yes', 'hyperframes@0.9.68', 'remove-background', seg, '-o', f'public/media/{n}'], check=True)
        print('cutout', a, b, '->', n)
d['cutouts'] = [{'src': f'media/{n}', 'from': a, 'dur': b - a} for (a, b), n in zip(win, names)]
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=1)
print(f'{len(win)} cutout windows ({len(todo)} rendered) -> {p}')
