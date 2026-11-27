#!/usr/bin/env python3
"""Generate an .srt for the EDITED timeline, timed word by word.

Each cut in spec.json is transcribed on its own (whisper word timestamps) and
shifted to where that cut sits on the timeline, so caption timing is anchored
to the real cut points instead of drifting. Words are grouped into cues of at
most `maxWords` (default 4), never crossing a sentence end, balanced so no cue
is left with one orphan word.

Usage: make_captions.py <spec.json> <out.srt> <workdir>

Optional keys in spec.json:
  "captions": {
    "maxWords": 4,
    "punctuation": "question",   # "question" = keep only "?" (default),
                                 # "none" = strip all, "keep" = as transcribed
    "lowercaseStart": false,      # true = every cue starts lowercase (except proper nouns)
    "fixes": [["open ai", "OpenAI"]]
  }
Global corrections that hold for EVERY video of this user (dialect forms, brand names)
live in "fixes" / "properNouns" of ../settings.local.json (copy settings.example.json) and are applied before
the spec's own "fixes"; add a mishearing there once instead of in each spec.

Timing rules (from Hainrixz/video-editor-architect, MIT, adapted 2026-11-20):
  - a cue prefers to end at a cut (strong bonus), so text rarely spans a jump cut
  - every cue enters `leadFrames` (default 1) before its first word
  - no cue is shorter than 4 frames (shorter can't be read)

"fixes" correct WHISPER mishearings so the caption matches what they actually
said. They are not edits to their words — confirm any doubtful one with them.
"""
import json, math, os, re, subprocess, sys

FPS_REAL = {23.976: 24000 / 1001, 24: 24, 25: 25, 29.97: 30000 / 1001, 30: 30, 50: 50, 59.94: 60000 / 1001, 60: 60}
MODEL = os.path.expanduser(os.environ.get('WHISPER_MODEL', '~/.whisper-models/ggml-large-v3-turbo.bin'))
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
VOCAB = os.path.join(_ROOT, 'settings.local.json')  # this user's own lang/fixes/properNouns (gitignored); see settings.example.json
MIN_FRAMES = 4
NOSPLIT = set()  # adjacent word pairs inside multi-word proper nouns, filled in main()
norm = lambda w: re.sub(r'[^\wáéíóúüñ]', '', w.lower())


def reel_lang():
    """Spoken language for whisper: $REEL_LANG, else "lang" in ../settings.local.json, else auto-detect."""
    if os.environ.get('REEL_LANG'):
        return os.environ['REEL_LANG']
    return (json.load(open(VOCAB)).get('lang') if os.path.exists(VOCAB) else None) or 'auto'


def words_for_cut(src, a, b, tmp):
    wav, base = tmp + '.wav', tmp
    key = f'{src}|{a}|{b}|{reel_lang()}|{os.path.basename(MODEL)}'  # language and model are part of the cache key
    if os.path.exists(base + '.json') and os.path.exists(base + '.key') and open(base + '.key').read() == key:
        segs = json.load(open(base + '.json'))['transcription']  # cached: same cut, same source
        return parse(segs, a, b)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{a}', '-to', f'{b}', '-i', src,
                    '-ar', '16000', '-ac', '1', '-af', 'apad=pad_dur=0.4', wav], check=True)
    subprocess.run(['whisper-cli', '-m', MODEL, '-l', reel_lang(), '-ml', '1', '-sow', '-ojf', '-of', base, '-f', wav],
                   capture_output=True)
    open(base + '.key', 'w').write(key)
    return parse(json.load(open(base + '.json'))['transcription'], a, b)


def parse(segs, a, b):
    out = []
    for s in segs:
        t = s['text'].strip()
        if not t:
            continue
        st, en = s['offsets']['from'] / 1000, s['offsets']['to'] / 1000
        if st >= b - a:
            continue
        out.append({'text': t, 'start': st, 'end': min(en, b - a)})
    return out


def apply_fixes(words, fixes):
    for frm, to in fixes:
        f, tw = frm.split(), to.split()
        i = 0
        while i <= len(words) - len(f):
            if [norm(w['text']) for w in words[i:i + len(f)]] == [norm(x) for x in f]:
                st, en = words[i]['start'], words[i + len(f) - 1]['end']
                trail = re.search(r'[.,?!…:;]+$', words[i + len(f) - 1]['text'])
                step = (en - st) / len(tw)
                new = [{'text': w, 'start': st + k * step, 'end': st + (k + 1) * step, 'cut': words[i].get('cut', 0)}
                       for k, w in enumerate(tw)]
                if trail:
                    new[-1]['text'] += trail.group(0)
                words[i:i + len(f)] = new
                i += len(tw)
            else:
                i += 1
    return words


def clean(text, mode):
    if mode == 'keep':
        return text
    text = text.replace('¿', '').replace('¡', '').replace('…', '').replace('...', '')
    keep = '?' if mode == 'question' else ''
    return re.sub(r'[.,!:;"]' if keep else r'[.,!?:;"]', '', text).strip()


# Words a line should not END on: articles, prepositions, conjunctions, clitics,
# possessives and the subject "vos" (it belongs with its verb).
WEAK = set('a al el la los las un una unos unas de del en con por para que y o u ni '
           'tu tus su sus mi mis le les lo me te se nos vos si pero como cuando porque a'.split()
           + 'the an of to in on at for with by from and or but nor so if as than my your his her its our their i'.split())
PROPER = {'meta', 'instagram', 'ia', 'ai', 'tiktok', 'youtube', 'claude', 'chatgpt', 'gemini', 'openai', 'google',
          'i', 'im', 'ive', 'ill', 'id'}  # English "I" forms always keep their capital; add names in properNouns


def fix_case(words, proper, lower_start=False):
    # lower_start: every line starts lowercase unless it's a proper noun (a style option, off by default)
    for k, w in enumerate(words):
        start = (not lower_start) and (k == 0 or re.search(r'[.?!]$', words[k - 1]['text']))
        t = w['text']
        m = re.match(r'[¿¡"(]*', t)
        p, body = t[:m.end()], t[m.end():]  # case applies after a leading ¿ ¡ " (
        if start:
            w['text'] = p + body[:1].upper() + body[1:]
        elif (body[:1].isupper() and (k == 0 or re.search(r'[.?!]$', words[k - 1]['text']) or words[k - 1].get('cut') != w.get('cut'))
              and (len(body.rstrip('.,;:?!')) == 1 or not body.isupper()) and norm(body) not in proper):
            # only a sentence-initial capital is lowered: mid-sentence capitals are names (New York, John)
            w['text'] = p + body[:1].lower() + body[1:]
    return words


def split_sentence(s, max_words, breaks=()):
    """Pick line breaks by dynamic programming: lines of 2..max words, close to
    max, breaking after commas when possible and never after a weak word.
    `breaks` are manual "left words|right words" rules: a break exactly there
    is strongly preferred (use them after reviewing the cue list)."""
    n = len(s)
    if n <= max_words:
        return [s]
    toks = [norm(w['text']) for w in s]
    def forced(j):  # is there a manual break rule between s[j-1] and s[j]?
        for rule in breaks:
            left, right = ([norm(x) for x in p.split()] for p in rule.split('|'))
            if toks[max(0, j - len(left)):j] == left and toks[j:j + len(right)] == right:
                return True
        return False
    def brk(j):
        w = s[j - 1]
        if forced(j):
            return -10.0  # a manual break wins over line-length balance
        if (toks[j - 1], toks[j]) in NOSPLIT:
            return 8.0  # never split a brand/name ("Daddy | Issues")
        weak = norm(w['text']) in WEAK
        cost = 0.0 if re.search(r'[,;:]$', w['text']) else (4.0 if weak else 1.0)
        if s[j - 1].get('cut') != s[j].get('cut'):
            cost -= 2.5  # the line changes where the picture cuts
        return cost
    best = [math.inf] * (n + 1)
    prev = [0] * (n + 1)
    best[0] = 0.0
    for j in range(1, n + 1):
        for size in range(1, max_words + 1):
            i = j - size
            if i < 0 or best[i] == math.inf:
                continue
            if size == 1 and not ((i == 0 or forced(i)) and (j == n or forced(j))):
                continue  # a one-word line only when manual breaks isolate it on both sides ("OpenAI")
            cost = best[i] + 0.3 * (max_words - size) ** 2 + (brk(j) if j < n else 0)
            if cost < best[j]:
                best[j], prev[j] = cost, i
    out, j = [], n
    while j > 0:
        out.append(s[prev[j]:j])
        j = prev[j]
    return out[::-1]


def _joined(words, k, joins):
    # manual "left|right" rule that keeps two words in the same cue across a short pause ("reveló|que")
    for rule in joins:
        left, right = ([norm(x) for x in p.split()] for p in rule.split('|'))
        lt = [norm(w['text']) for w in words[max(0, k + 1 - len(left)):k + 1]]
        rt = [norm(w['text']) for w in words[k + 1:k + 1 + len(right)]]
        if lt == left and rt == right:
            return True
    return False


def group(words, max_words, breaks=(), gap=0.4, joins=()):
    # gap: a pause longer than this always starts a new cue, so a cue never shows words before they're said
    # (0.7 let one cue span a pause and show the next phrase early).
    sentences, cur = [], []
    for k, w in enumerate(words):
        cur.append(w)
        nxt = words[k + 1] if k + 1 < len(words) else None
        # whisper often stretches a word's end over the following silence, so also use start-to-start:
        # no single word takes more than ~1 s to say.
        paused = nxt is not None and (nxt['start'] - w['end'] > gap or nxt['start'] - w['start'] > 1.0) and not _joined(words, k, joins)
        if re.search(r'[.?!]$', w['text']) or nxt is None or paused:
            sentences.append(cur)
            cur = []
    cues = []
    for s in sentences:
        cues += split_sentence(s, max_words, breaks)
    return cues


def ts(sec):
    ms = int(round(sec * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def main():
    spec, out_srt, workdir = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
    os.makedirs(workdir, exist_ok=True)
    fps = FPS_REAL.get(spec.get('fps', 30), spec.get('fps', 30))
    cfg = spec.get('captions', {})
    fr = lambda s: int(round(s * fps))
    words, t = [], 0
    for k, c in enumerate(spec['cuts']):
        i, o = fr(c['in']), fr(c['out'])
        if c.get('noCaptions'):  # silent B-roll (e.g. a sped-up demo): whisper hallucinates "gracias" on silence
            t += o - i
            continue
        for w in words_for_cut(spec['sources'][c['src']], i / fps, o / fps, os.path.join(workdir, f'cut{k:02d}')):
            words.append({'text': w['text'], 'start': t / fps + w['start'], 'end': t / fps + w['end'], 'cut': k})
        t += o - i
    total = t / fps
    vocab = json.load(open(VOCAB)) if os.path.exists(VOCAB) else {}
    words = apply_fixes(words, vocab.get('fixes', []) + cfg.get('fixes', []))
    proper = vocab.get('properNouns', []) + cfg.get('properNouns', [])
    for p in proper + [to for _, to in vocab.get('fixes', []) + cfg.get('fixes', []) if to[:1].isupper()]:
        t = [norm(x) for x in p.split()]
        NOSPLIT.update(zip(t, t[1:]))
    words = fix_case(words, PROPER | {norm(x) for p in proper for x in p.split()}, cfg.get('lowercaseStart', False))
    json.dump([{'text': w['text'], 'frame': fr(w['start']), 'cut': w['cut']} for w in words],
              open(os.path.join(workdir, 'words.json'), 'w'), ensure_ascii=False, indent=0)  # timeline frame of every word (to place visuals on a word)
    cues = group(words, cfg.get('maxWords', 4), cfg.get('breaks', []), joins=cfg.get('joins', []))
    lead = cfg.get('leadFrames', 1)
    starts = []  # in frames, each entering `lead` frames early but never before the previous cue's first word
    for n, cue in enumerate(cues):
        f = max(0, fr(cue[0]['start']) - lead)
        if starts:
            f = max(f, starts[-1] + MIN_FRAMES)
        starts.append(f)
    lines = []
    for n, cue in enumerate(cues):
        sf = starts[n]
        ef = fr(cue[-1]['end'] + 0.25)
        if n + 1 < len(cues):
            nf = starts[n + 1]
            ef = nf if (nf - ef) / fps < 0.35 else min(ef, nf)
        ef = min(max(ef, sf + MIN_FRAMES), fr(total))
        st, en = sf / fps, ef / fps
        text = clean(' '.join(w['text'] for w in cue), cfg.get('punctuation', 'question'))
        lines.append(f'{n + 1}\n{ts(st)} --> {ts(en)}\n{text}\n')
        print(f'{ts(st)}  {len(cue)}w  {text}')
    open(out_srt, 'w').write('\n'.join(lines))
    print(f'{len(cues)} cues -> {out_srt}')


if __name__ == '__main__':
    main()
