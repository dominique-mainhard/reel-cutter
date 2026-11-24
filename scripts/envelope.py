#!/usr/bin/env python3
"""Print a 20 ms loudness envelope of a 16-bit WAV between two times.

Use it to place a cut INSIDE a sentence (dropping a self-correction): look for
the dip of a stop consonant (k, p, t) or a breath between the words. Dips below
about -48 dB are safe cut points.

Usage: envelope.py <file.wav> <from_sec> <to_sec>
"""
import math, struct, sys, wave

w = wave.open(sys.argv[1])
sr, ch = w.getframerate(), w.getnchannels()
a, b = float(sys.argv[2]), float(sys.argv[3])
w.setpos(int(a * sr))
n = int((b - a) * sr)
data = struct.unpack(f'<{n * ch}h', w.readframes(n))[::ch]
step = int(sr * 0.02)
for i in range(0, len(data) - step, step):
    chunk = data[i:i + step]
    rms = math.sqrt(sum(x * x for x in chunk) / len(chunk)) + 1e-9
    db = 20 * math.log10(rms / 32768)
    print(f"{a + i / sr:7.2f} {db:6.1f} " + '#' * max(0, int((db + 60) / 1.5)))
