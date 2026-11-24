#!/usr/bin/env python3
"""Map every take in one or more raw clips.

For each video: probe it, extract 16 kHz mono audio, find speech regions with
ffmpeg silencedetect, and transcribe EACH region on its own with whisper-cli.
Per-region transcription is deliberate: whisper's timestamps over a whole file
drift by 1-2 s after long pauses, but a region's start/end comes from the
waveform, so it is exact.

Usage: takes.py <workdir> <video> [<video> ...]
Writes <workdir>/<name>.wav and <workdir>/takes.json; prints a table sorted by
recording time (the last take of a line is the latest one in that order).
"""
import json, os, subprocess, sys
def reel_lang():
    """Spoken language for whisper: $REEL_LANG, else "lang" in ../settings.local.json, else auto-detect."""
    if os.environ.get('REEL_LANG'):
        return os.environ['REEL_LANG']
    v = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'settings.local.json')
    return (json.load(open(v)).get('lang') if os.path.exists(v) else None) or 'auto'


MODELS = [os.path.expanduser(os.environ.get('WHISPER_MODEL', '~/.whisper-models/ggml-large-v3-turbo.bin')),
          os.path.expanduser('~/.cache/hyperframes/whisper/models/ggml-small.bin')]
NOISE_DB, MIN_SIL = -35, 0.35


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    out = json.loads(run(['ffprobe', '-v', 'error', '-show_entries',
                          'format=duration:format_tags=creation_time,com.apple.quicktime.creationdate:'
                          'stream=codec_type,width,height,r_frame_rate,channels,sample_rate',
                          '-of', 'json', path]).stdout)
    v = next((s for s in out['streams'] if s['codec_type'] == 'video'), {})
    a = next((s for s in out['streams'] if s['codec_type'] == 'audio'), {})
    tags = out['format'].get('tags', {})
    num, den = (v.get('r_frame_rate') or '30/1').split('/')
    return {'path': path, 'duration': float(out['format']['duration']),
            'width': v.get('width'), 'height': v.get('height'), 'fps': round(int(num) / int(den), 3),
            'audioChannels': a.get('channels'), 'audioRate': a.get('sample_rate'),
            'recorded': tags.get('creation_time') or tags.get('com.apple.quicktime.creationdate') or ''}


def speech_regions(wav, dur):
    err = run(['ffmpeg', '-hide_banner', '-i', wav, '-af',
               f'silencedetect=n={NOISE_DB}dB:d={MIN_SIL}', '-f', 'null', '-']).stderr
    regions, start = [], 0.0
    for line in err.splitlines():
        if 'silence_start:' in line:
            s = float(line.split('silence_start:')[1].split()[0])
            if s - start > 0.15:
                regions.append((start, s))
        elif 'silence_end:' in line:
            start = float(line.split('silence_end:')[1].split()[0])
    if dur - start > 0.15:
        regions.append((start, dur))
    return regions


def transcribe(wav, a, b, model, tmp):
    run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{a}', '-to', f'{b}', '-i', wav,
         '-af', 'apad=pad_dur=0.4', tmp])
    out = run(['whisper-cli', '-m', model, '-l', reel_lang(), '-nt', '-np', '-f', tmp]).stdout
    return ' '.join(out.split())


def main():
    workdir, videos = sys.argv[1], sys.argv[2:]
    os.makedirs(workdir, exist_ok=True)
    model = next((m for m in MODELS if os.path.exists(m)), None)
    if not model:
        sys.exit('No whisper model found in ' + ', '.join(MODELS))
    clips = []
    for path in videos:
        info = probe(path)
        name = os.path.splitext(os.path.basename(path))[0].replace(' ', '_')
        wav = os.path.join(workdir, name + '.wav')
        run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-ar', '16000', '-ac', '1', wav])
        info['wav'] = wav
        info['regions'] = [{'start': round(a, 2), 'end': round(b, 2),
                            'text': transcribe(wav, a, b, model, os.path.join(workdir, '_seg.wav'))}
                           for a, b in speech_regions(wav, info['duration'])]
        clips.append(info)
    clips.sort(key=lambda c: c['recorded'])
    json.dump(clips, open(os.path.join(workdir, 'takes.json'), 'w'), ensure_ascii=False, indent=1)
    for c in clips:
        print(f"\n===== {os.path.basename(c['path'])}  recorded {c['recorded']}  "
              f"{c['width']}x{c['height']} {c['fps']}fps  {c['duration']:.1f}s")
        for r in c['regions']:
            print(f"{r['start']:8.2f}-{r['end']:8.2f} | {r['text']}")


if __name__ == '__main__':
    main()
