#!/usr/bin/env python3
"""Cut products (bags, garments, shoes…) out of a FLAT studio background, one PNG per item, trimmed.

Use it for a grid of product shots that should float on screen, slightly scattered, without their background.
`hyperframes remove-background` is a PERSON model: on bags it erases handles and keeps pieces of wall. A colour key on the flat background works instead:
- background colour = median of the 4 corners of each cell; distance = max channel difference;
- pixels within BGT of it, connected to the cell border, are background;
- enclosed background islands smaller than MAXH px are filled (highlights inside a glossy bag), bigger
  ones stay transparent (the gap between a strap and the bag);
- soft alpha ramp, then a 3x3 median and a 1 px erosion (no light fringe on dark backgrounds).
Light/metallic items that are close to the background colour (a silver bag) need --strong <cells>: a tighter key
and a bigger hole fill.

Usage: python3 -I cutout_products.py <image> <outdir> [--grid COLSxROWS] [--strong 3,5] [--prefix item]
Writes <outdir>/<prefix>-<n>.png (n = 1.. in reading order). Look at them over a coloured background before use.
Place them as layers with look "plain", box.rotate ±2–5°, uneven offsets, a few frames apart, leaving together.
"""
import os, subprocess, sys
from collections import deque

img, outdir = sys.argv[1], sys.argv[2]
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
cols, rows = map(int, arg('--grid', '1x1').split('x'))
strong = {int(v) for v in arg('--strong', '').split(',') if v}
prefix = arg('--prefix', 'item')
os.makedirs(outdir, exist_ok=True)
W, H = map(int, subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', img],
                               capture_output=True, text=True).stdout.strip().split(','))
rgb = subprocess.run(['ffmpeg', '-v', 'error', '-i', img, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
cw, ch = W // cols, H // rows

for r in range(rows):
    for c in range(cols):
        n = r * cols + c + 1
        MAXH, BGT, LO, GAIN = (20000, 4, 2, 60) if n in strong else (2500, 9, 6, 18)
        px = lambda x, y: rgb[3 * ((r * ch + y) * W + c * cw + x):3 * ((r * ch + y) * W + c * cw + x) + 3]
        corners = [px(3, 3), px(cw - 4, 3), px(3, ch - 4), px(cw - 4, ch - 4)]
        bg = [sorted(p[i] for p in corners)[1] for i in range(3)]
        D = [max(abs(v - bg[i]) for i, v in enumerate(px(x, y))) for y in range(ch) for x in range(cw)]
        isbg = [d <= BGT for d in D]; seen = bytearray(cw * ch); fill = bytearray(cw * ch)
        for s in range(cw * ch):
            if not isbg[s] or seen[s]: continue
            comp, edge, q = [], False, deque([s]); seen[s] = 1
            while q:
                i = q.popleft(); comp.append(i); x, y = i % cw, i // cw
                if x in (0, cw - 1) or y in (0, ch - 1): edge = True
                for j in ((i - 1) if x else -1, (i + 1) if x < cw - 1 else -1, i - cw, i + cw):
                    if 0 <= j < cw * ch and isbg[j] and not seen[j]: seen[j] = 1; q.append(j)
            if not edge and len(comp) < MAXH:
                for i in comp: fill[i] = 1
        A = bytes(255 if fill[i] else max(0, min(255, (D[i] - LO) * GAIN)) for i in range(cw * ch))
        xs = [i % cw for i in range(cw * ch) if A[i] > 40]; ys = [i // cw for i in range(cw * ch) if A[i] > 40]
        if not xs: print(n, 'empty cell'); continue
        x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
        rgba = bytearray()
        for y in range(ch):
            for x in range(cw):
                rgba += px(x, y) + bytes([A[y * cw + x]])
        out = os.path.join(outdir, f'{prefix}-{n}.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{cw}x{ch}', '-i', '-',
                        '-filter_complex', f'[0]split[c][a];[a]alphaextract,median=radius=1,erosion[al];[c][al]alphamerge,'
                                           f'crop={x1 - x0}:{y1 - y0}:{x0}:{y0}', '-frames:v', '1', out], input=bytes(rgba), check=True)
        print(n, out, f'{x1 - x0}x{y1 - y0}')
