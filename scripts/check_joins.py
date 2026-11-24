#!/usr/bin/env python3
"""Hear the edit before rendering: concatenate the audio of every cut in a
spec.json and transcribe the result.

A dropped or doubled word at a join ("the the", a missing "not") shows up here.
Fix it with envelope.py and re-run.

Usage: check_joins.py <spec.json> <workdir>
"""
import json, os, subprocess, sys
def reel_lang():
    """Spoken language for whisper: $REEL_LANG, else "lang" in ../settings.local.json, else auto-detect."""
    if os.environ.get('REEL_LANG'):
        return os.environ['REEL_LANG']
    v = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'settings.local.json')
    return (json.load(open(v)).get('lang') if os.path.exists(v) else None) or 'auto'


spec, workdir = json.load(open(sys.argv[1])), sys.argv[2]
os.makedirs(workdir, exist_ok=True)
srcs = list(spec['sources'].items())
idx = {k: n for n, (k, _) in enumerate(srcs)}
parts, labels = [], []
for k, c in enumerate(spec['cuts']):
    parts.append(f"[{idx[c['src']]}:a]atrim={c['in']}:{c['out']},asetpts=PTS-STARTPTS[x{k}]")
    labels.append(f'[x{k}]')
graph = ';'.join(parts) + ';' + ''.join(labels) + f'concat=n={len(labels)}:v=0:a=1,aresample=16000,pan=mono|c0=c0[out]'
out = os.path.join(workdir, 'joins.wav')
cmd = ['ffmpeg', '-v', 'error', '-y']
for _, p in srcs:
    cmd += ['-i', p]
subprocess.run(cmd + ['-filter_complex', graph, '-map', '[out]', out], check=True)
model = next((m for m in [os.path.expanduser(os.environ.get('WHISPER_MODEL', '~/.whisper-models/ggml-large-v3-turbo.bin')),
                           os.path.expanduser('~/.cache/hyperframes/whisper/models/ggml-small.bin')] if os.path.exists(m)), None) or sys.exit('no whisper model: run scripts/doctor.sh')
print(subprocess.run(['whisper-cli', '-m', model, '-l', reel_lang(), '-f', out],
                     capture_output=True, text=True).stdout)
