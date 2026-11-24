#!/usr/bin/env python3
"""Make light VP9 WebM copies of every video the reel uses, for the Studio preview only.

Browsers (and VS Code's built-in browser even more so) can't play iPhone HEVC or ProRes 4444,
so Remotion Studio shows "MediaPlaybackError: Code 4". This writes public/media/proxy/<name>.webm
(540x960; the speaker cutouts keep their alpha) and sets data.proxies = true. Reel.tsx swaps
to the proxies only inside Studio: renders and stills always use the originals.

Usage (from the project root): python3 -I scripts/proxies.py <slug> [--force]
Re-run after cutouts.py (new cutouts) or after adding video layers.
"""
import json, os, subprocess, sys

slug, force = sys.argv[1], '--force' in sys.argv
path = f'src/data/{slug}.json'
d = json.load(open(path))
media = os.path.realpath('public/media')
out_dir = os.path.join(media, 'proxy')
os.makedirs(out_dir, exist_ok=True)

srcs = {c['src']: 'opaque' for c in d['cuts']}
srcs.update({l['src']: 'opaque' for l in d.get('layers', []) if l.get('kind') == 'video'})
srcs.update({c['src']: 'alpha' for c in d.get('cutouts', [])})

for src, kind in srcs.items():
    name = os.path.basename(src)
    inp, out = os.path.join(media, name), os.path.join(out_dir, os.path.splitext(name)[0] + '.webm')
    if not force and os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(inp):
        print('ok  ', name)
        continue
    common = ['-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '40', '-deadline', 'realtime', '-cpu-used', '8',
              '-row-mt', '1', '-vf', 'scale=540:960', '-r', str(d.get('fps', 30))]
    if kind == 'alpha':
        args = common + ['-pix_fmt', 'yuva420p', '-auto-alt-ref', '0', '-an']
    else:
        args = common + ['-pix_fmt', 'yuv420p', '-c:a', 'libopus', '-b:a', '96k']
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', inp, *args, out], check=True)
    print('made', name, '->', os.path.relpath(out, media))

d['proxies'] = True
json.dump(d, open(path, 'w'), ensure_ascii=False, indent=1)
print(f'{len(srcs)} proxies -> public/media/proxy/ (used only in Studio)')
