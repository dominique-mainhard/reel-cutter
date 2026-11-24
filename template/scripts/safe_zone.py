#!/usr/bin/env python3
"""Instagram safe zone check (1080x1920). Instagram covers the edges of a reel:
  - top ~260 px: the header (profile name, back arrow, "+") when the reel is seen in feed or reshared to a story;
  - sides ~55 px: the reel is scaled to fill the height and the sides get cropped;
  - right column x > 915 from y ~1040 down: like / comment / share / save buttons;
  - bottom from y ~1700: username, caption text, audio.
Nothing that must be read goes there. Visuals keep top >= 260, left >= 70, right <= 1010,
bottom <= 1040 if they reach x > 915, and bottom <= 1700.

Usage (project root): python3 -I scripts/safe_zone.py src/data/<slug>.json [--fix]
--fix moves each group of visuals that are on screen together DOWN by the same amount (keeps their layout) so
its highest item starts at TOP, and slides items left so they end at RIGHT.
Re-check the result on a contact sheet: moving things down can put text behind the head.
"""
import json, sys

TOP, LEFT, RIGHT, BOTTOM = 260, 70, 1010, 1700
BTN_X, BTN_Y = 915, 1040  # right-side buttons column


def boxes(l):
    return [l['box']] if l.get('box') else []


def problems(d):
    out = []
    for l in d.get('layers', []):
        for b in boxes(l):
            r, bot = b['left'] + b['width'], b['top'] + b['height']
            name = f"{l['from']:>5} {l.get('kind')} {str(l.get('src', ''))[-36:]}"
            if b['top'] < TOP: out.append(f'{name}: top {b["top"]} < {TOP} (under the Instagram header)')
            if b['left'] < LEFT: out.append(f'{name}: left {b["left"]} < {LEFT} (side crop)')
            if r > RIGHT: out.append(f'{name}: right edge {r} > {RIGHT} (side crop)')
            if bot > BOTTOM: out.append(f'{name}: bottom {bot} > {BOTTOM} (username / caption)')
            if r > BTN_X and bot > BTN_Y: out.append(f'{name}: reaches x {r}, y {bot}: under the like/comment buttons')
    return out


def fix(d):
    ls = sorted(d.get('layers', []), key=lambda l: l['from'])
    groups, cur, end = [], [], -1
    for l in ls:  # layers that overlap in time form a group (they are on screen together)
        if cur and l['from'] >= end:
            groups.append(cur); cur = []
        cur.append(l); end = max(end if cur[:-1] else -1, l['from'] + l['dur'])
    if cur: groups.append(cur)
    for g in groups:
        tops = [b['top'] for l in g for b in boxes(l)]
        dy = max(0, TOP - min(tops)) if tops else 0
        for l in g:
            for b in boxes(l):
                b['top'] += dy
                if b['left'] + b['width'] > RIGHT: b['left'] = max(LEFT, RIGHT - b['width'])
                if b['left'] < LEFT: b['left'] = LEFT


p = sys.argv[1]
d = json.load(open(p))
if '--fix' in sys.argv:
    fix(d); json.dump(d, open(p, 'w'), ensure_ascii=False, indent=1)
left = problems(d)
print('\n'.join(left) if left else 'safe zone OK')
