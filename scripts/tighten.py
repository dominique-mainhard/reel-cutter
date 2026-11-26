#!/usr/bin/env python3
"""Remove pauses and breaths INSIDE each take (not only between takes), without clipping a word.

Splitting the takes into lines leaves the pauses inside each take: 0.3–0.6 s gaps and audible breaths,
which make the reel feel slow. This splits every cut at its internal gaps and keeps only a consonant-safe
tail and a short pre-roll:

- gap  = level (10 ms RMS) under min(floor + 22 dB, -40 dB) for >= 0.25 s. The -40 ceiling catches breaths,
         which sit well above the noise floor but far below speech. floor = 10th percentile of the cut.
- tail = from the gap start, until the level stays under floor + 8 dB for 60 ms, + 40 ms (max 0.2 s):
         final s/t/d/r fade slowly and a fixed tail clipped them.
- pre  = 80 ms before the next onset.
A gap is cut only if that removes >= 0.1 s. A gap at the start of a cut is trimmed to the pre-roll; a gap at
the end is trimmed to the tail (except the last cut with --keep-last-end, e.g. to hold an end CTA).

Each piece keeps its cut's zoom/center/label (".0", ".1", …).
Cuts with "zoomTo" (a push-in within the cut) or "noTighten": true are left as they are.
normalize_cuts.py gives consecutive pieces of one take ONE gain, so levels don't jump between pieces.
Always run check_joins.py afterwards and read the transcript: no word may be lost.

Usage: python3 -I tighten.py <spec.json> <workdir> [--out spec-tight.json] [--keep-last-end]
"""
import array, json, math, os, subprocess, sys

spec_path, work = sys.argv[1], sys.argv[2]
out_path = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else spec_path
keep_last_end = '--keep-last-end' in sys.argv
spec = json.load(open(spec_path))
SR = 16000; HOP = SR // 100

levels = {}
def level(src):
    if src not in levels:
        wav = os.path.join(work, 'tight-' + os.path.basename(src) + '.raw')
        if not os.path.exists(wav):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vn', '-ac', '1', '-ar', str(SR), '-f', 's16le', wav], check=True)
        a = array.array('h'); a.frombytes(open(wav, 'rb').read())
        levels[src] = [20 * math.log10(math.sqrt(sum(x * x for x in a[i:i + HOP]) / HOP) / 32768 + 1e-9)
                       for i in range(0, len(a) - HOP, HOP)]
    return levels[src]

cuts, saved = [], 0.0
for n, c in enumerate(spec['cuts']):
    if c.get('zoomTo') or c.get('noTighten'):
        cuts.append(c); continue
    lv = level(spec['sources'][c['src']])
    L = lambda t: lv[min(len(lv) - 1, max(0, int(round(t * 100))))]
    cin, cout = c['in'], c['out']
    seg = lv[int(cin * 100):int(cout * 100)]
    if len(seg) < 30:
        cuts.append(c); continue
    floor = sorted(seg)[len(seg) // 10]; T = min(floor + 22, -40)
    runs, st = [], None
    for j, v in enumerate(seg + [99]):
        if v < T and st is None: st = j
        elif v >= T and st is not None:
            if j - st >= 25 or st == 0: runs.append((cin + st / 100, cin + j / 100))
            st = None
    keep, cur = [], cin
    for g0, g1 in runs:
        if g0 <= cin + 0.01:                                   # silence/breath at the start of the cut
            cur = max(cur, round(g1 - 0.08, 2)); continue
        t, A = g0, None
        while t < min(g1, g0 + 0.2):
            if all(L(t + k * 0.01) < floor + 8 for k in range(6)): A = t + 0.04; break
            t += 0.01
        A = round(min(A if A is not None else g0 + 0.2, g1), 2)
        if g1 >= cout - 0.01:                                  # silence at the end of the cut
            if not (keep_last_end and n == len(spec['cuts']) - 1):
                keep.append([cur, A]); cur = None
            break
        B = round(g1 - 0.08, 2)
        if B - A >= 0.1:
            keep.append([cur, A]); cur = B
    if cur is not None: keep.append([cur, cout])
    saved += (cout - cin) - sum(b - a for a, b in keep)
    for k, (a, b) in enumerate(keep):
        p = {key: v for key, v in c.items() if key != 'transition' or k == 0}
        p.update({'in': a, 'out': b})
        if len(keep) > 1: p['label'] = f"{c.get('label', n)} .{k}"
        cuts.append(p)
    print(f"cut {n}: {len(keep)} piece(s), -{(cout - cin) - sum(b - a for a, b in keep):.2f} s")

spec['cuts'] = cuts
json.dump(spec, open(out_path, 'w'), ensure_ascii=False, indent=1)
print(f'{len(cuts)} cuts, {saved:.2f} s of pauses/breaths removed -> {out_path}. Now run check_joins.py and read every line.')
