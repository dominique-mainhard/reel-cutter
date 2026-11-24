#!/usr/bin/env python3
"""Move hand-placed visuals to a new cut after re-cutting.

`from_spec.py` keeps layers when re-run, but with their OLD frame numbers: change any cut's in/out and
everything after it is off by the difference. Save a copy of the data JSON before re-running from_spec.py, then:

  python3 -I <skill>/scripts/remap_timeline.py <old-data.json> src/data/<slug>.json

Every frame is mapped through the cut it falls in (same cut index, same offset inside it, clamped to the new
cut's length), so the cut list must keep the same number of cuts. Clears cutouts (re-run cutouts.py --force).
"""
import json, sys

old_p, new_p = sys.argv[1], sys.argv[2]
old, d = json.load(open(old_p)), json.load(open(new_p))
oc, nc = old['cuts'], d['cuts']
if len(oc) != len(nc):
    sys.exit(f'cut count changed ({len(oc)} -> {len(nc)}): remap by hand')
ON, NN = old['durationInFrames'], d['durationInFrames']


def m(f):
    if f >= ON: return NN
    k = max(i for i, c in enumerate(oc) if c['from'] <= f)
    return nc[k]['from'] + min(f - oc[k]['from'], nc[k]['dur'])


for o in old.get('layers', []):
    a, b = m(o['from']), m(o['from'] + o['dur'])
    o['from'], o['dur'] = a, max(1, b - a)
if 'layers' in old: d['layers'] = old['layers']
if 'clickVolume' in old: d['clickVolume'] = old['clickVolume']
d['cutouts'] = []
json.dump(d, open(new_p, 'w'), ensure_ascii=False, indent=1)
print(f'remapped {len(d.get("layers", []))} layers; {ON} -> {NN} frames. Next: normalize_cuts.py, cutouts.py --force')
