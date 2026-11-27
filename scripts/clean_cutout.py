#!/usr/bin/env python3
"""Clean a person cutout (`hyperframes remove-background` .mov) so it floats cleanly over other footage.

Use it for the speaker small over a screen or B-roll (picture-in-picture): a raw cutout keeps background haze,
furniture and holes, and reads as "the background is still there". Four fixes, all applied here:
1. --crop: crop the cutout ABOVE the table/rug/chair, so no furniture survives at the bottom (anchor the result
   to the frame's bottom edge; the straight crop line is then hidden by the frame edge).
2. Alpha cleanup: semi-transparent background haze -> transparent, body -> fully opaque (contrast curve),
   1 px erosion (kills the light halo of the wall), slight blur (soft edge).
3. Holes: anything fully enclosed by the person (left/right/top border seeds the fill; the bottom is the frame
   edge, the body continues there) becomes opaque. --mouth x0,y0,x1,y1 also makes DARK pixels next to the person
   opaque inside that box: a black handheld mic was read as background and showed the footage through it.
4. Colours come from the SOURCE clip, not from the cutout: remove-background stores garbage colour (green) in
   the pixels it made transparent, so filling a hole there showed a green blob.

Usage: python3 -I clean_cutout.py <cutout.mov> <source clip, same frames/size> <out.mov>
           [--crop W:H:X:Y] [--mouth x0,y0,x1,y1]   (box in cropped pixels)
Check the result over a flat green (ffmpeg color=0x00ff00 + overlay) on several frames before using it.
"""
import os, subprocess, sys, tempfile
from collections import deque

cut, src, out = sys.argv[1:4]
arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
w0, h0 = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                  '-of', 'csv=p=0', cut], capture_output=True, text=True).stdout.strip().split(','))
crop = arg('--crop') or f'{w0}:{h0}:0:0'
W, H = map(int, crop.split(':')[:2]); W -= W % 4; H -= H % 4
crop = f'{W}:{H}:' + ':'.join(crop.split(':')[2:])
w, h = W // 4, H // 4
mouth = [int(v) // 4 for v in arg('--mouth').split(',')] if arg('--mouth') else None
tmp = tempfile.mkdtemp(prefix='cleancut-')
A, AQ, NQ, LQ, MQ = (os.path.join(tmp, n) for n in ('a.raw', 'aq.raw', 'nq.raw', 'lq.raw', 'mq.raw'))
ff = lambda *a: subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True)

alpha = f"crop={crop},alphaextract,lut=y='clip((val-0.35*maxval)*2.6\\,0\\,maxval)'"
ff('-i', cut, '-vf', f'{alpha},erosion,gblur=sigma=0.8,format=gray', '-f', 'rawvideo', A)
ff('-i', cut, '-vf', f'{alpha},scale={w}:{h},dilation,dilation,erosion,erosion,format=gray', '-f', 'rawvideo', AQ)  # closed
ff('-i', cut, '-vf', f'{alpha},scale={w}:{h},' + 'dilation,' * 4 + 'format=gray', '-f', 'rawvideo', NQ)           # "near her"
ff('-i', src, '-vf', f'crop={crop},scale={w}:{h},format=gray', '-f', 'rawvideo', LQ)

n = w * h
with open(AQ, 'rb') as fa, open(NQ, 'rb') as fn, open(LQ, 'rb') as fl, open(MQ, 'wb') as fo:
    while True:
        aq, nq, lq = fa.read(n), fn.read(n), fl.read(n)
        if len(aq) < n or len(lq) < n: break
        seen = bytearray(n); q = deque()
        for x in range(w):
            if aq[x] <= 100: seen[x] = 1; q.append(x)
        for y in range(h):
            for x in (0, w - 1):
                i = y * w + x
                if aq[i] <= 100 and not seen[i]: seen[i] = 1; q.append(i)
        while q:
            i = q.popleft(); x = i % w
            for j in (i - 1 if x else -1, i + 1 if x < w - 1 else -1, i - w, i + w):
                if 0 <= j < n and not seen[j] and aq[j] <= 100: seen[j] = 1; q.append(j)
        m = bytearray(n)
        for i in range(n):
            if aq[i] <= 100 and not seen[i]: m[i] = 255                     # enclosed hole
        if mouth:
            x0, y0, x1, y1 = mouth
            for y in range(max(0, y0), min(h, y1)):
                for x in range(max(0, x0), min(w, x1)):
                    i = y * w + x
                    if lq[i] < 95 and nq[i] > 200: m[i] = 255               # dark object held next to the face
        fo.write(m)

ff('-i', src, '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{W}x{H}', '-r', '30', '-i', A,
   '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{w}x{h}', '-r', '30', '-i', MQ,
   '-filter_complex', f'[2]scale={W}:{H},dilation,gblur=sigma=2[m];[1][m]blend=all_mode=lighten,format=gray[al];'
                      f'[0]crop={crop},format=yuva444p10le[c];[c][al]alphamerge',
   '-an', '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-shortest', out)
print('clean cutout ->', out)
