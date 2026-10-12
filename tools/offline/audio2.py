"""Original music-box waltz (E minor -> E major), synced to the choreography. 120 bpm, 3/4, 15 s."""
import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve

SR = 44100
DUR = 30.0
BEAT = 0.5
N = int(SR * (DUR + 2.5))
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(3)
NAMES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def freq(n):
    k = NAMES[n[0]]; i = 1
    if n[1] == '#': k += 1; i = 2
    elif n[1] == 'b': k -= 1; i = 2
    octv = int(n[i:])
    return 440.0 * 2 ** ((12 * (octv + 1) + k - 69) / 12)


def put(sig, t0, pan=0.0, gain=1.0):
    i0 = int(t0 * SR)
    if i0 >= N: return
    sig = sig[: N - i0] * gain
    L[i0:i0 + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    R[i0:i0 + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def celesta(f, dur, vel):
    t = np.arange(int(SR * (dur + 1.8))) / SR
    d = 1.6 + 600 / f
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t * (1.0 / d * 2.2))
         + 0.38 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 5.0)
         + 0.14 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 8.0)
         + 0.09 * np.sin(2 * np.pi * 4.17 * f * t) * np.exp(-t * 14.0)
         + 0.05 * np.sin(2 * np.pi * 6.3 * f * t) * np.exp(-t * 30.0))
    env = np.minimum(1, t / 0.002) * np.where(t < dur, 1.0, np.exp(-(t - dur) * 3.0))
    return y * env * vel


def pluck(f, vel, length=1.4):
    t = np.arange(int(SR * length)) / SR
    y = np.zeros_like(t)
    for k in range(1, 11):
        if k * f > 9000: break
        y += np.sin(2 * np.pi * k * f * t + rng.uniform(0, 6.28)) / k ** 1.1 * np.exp(-t * (2.2 + 1.6 * k))
    return y * np.minimum(1, t / 0.004) * vel


def pad(freqs, t0, dur, vel):
    t = np.arange(int(SR * (dur + 0.8))) / SR
    env = np.minimum(1, t / 0.35) * np.where(t < dur, 1.0, np.exp(-(t - dur) * 4.0))
    y = np.zeros_like(t)
    for f in freqs:
        for det in (-0.0025, 0.0, 0.0028):
            for k in range(1, 7):
                y += np.sin(2 * np.pi * k * f * (1 + det) * t + k) * np.exp(-0.45 * k) / k
    put(y * env * vel / len(freqs), t0, pan=0.0)


def whoosh(t0, dur, vel, rise=True):
    n = int(SR * dur)
    x = rng.normal(0, 1, n)
    X = np.fft.rfft(x); fr = np.fft.rfftfreq(n, 1 / SR)
    X *= np.exp(-((np.log(fr + 1) - np.log(1800)) / 0.9) ** 2)
    y = np.fft.irfft(X, n)
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t) ** 2
    y = y / (np.abs(y).max() + 1e-9) * env * vel
    put(y, t0, pan=-0.3, gain=1.0); put(np.roll(y, 300), t0, pan=0.3, gain=0.8)


# 20 bars of 3/4 at 120 bpm, synced to the choreography
def mel(bar, items, vel=0.55):
    b0 = 3 * (bar - 1); x = 0.0
    for it in items:
        n, d = it[0], it[1]; v = it[2] if len(it) > 2 else vel
        if n != 'r':
            put(celesta(freq(n), d * BEAT, v), (b0 + x) * BEAT, pan=0.15)
        x += d

mel(1, [('r', 0.4), ('E5', .5, .32), ('G5', .5, .36), ('B5', .5, .4), ('E6', 1.1, .45)])
mel(2, [('B5', 1), ('G5', .5), ('A5', .5), ('B5', 1)], .6)
mel(3, [('C6', 1), ('B5', .5), ('A5', .5), ('E6', 1)], .6)
mel(4, [('D#6', .5), ('E6', .5), ('F#6', .5), ('E6', .5), ('D#6', .5), ('B5', .5)], .52)
mel(5, [('E6', 1.5), ('D6', .5), ('C6', .5), ('B5', .5)], .55)
mel(6, [('C6', 1), ('E6', .5), ('G6', .5), ('E6', 1)], .55)
mel(7, [('A5', .5), ('C6', .5), ('E6', .5), ('F#6', 1.5)], .58)
mel(8, [('F#5', .5)] + [(n, .25, .42 + .02 * k) for k, n in enumerate(['G5', 'A5', 'B5', 'C6', 'D#6', 'E6', 'F#6', 'G6', 'A6', 'B6'])])
mel(9, [('G6', 1.5, .7), ('F#6', .5), ('E6', 1)], .55)
mel(10, [('E6', .5), ('G6', .5), ('A6', .5), ('B6', 1.5, .7)], .58)
mel(11, [(n, .25, .45) for n in ['B6', 'A6', 'G6', 'F#6', 'G6', 'A6', 'B6', 'A6', 'G6', 'F#6', 'E6', 'D6']])
mel(12, [('D#6', .5), ('F#6', .5), ('B6', 1, .65), ('A6', .5), ('F#6', .5)], .55)
mel(13, [('E6', 1), ('B5', .5), ('E6', .5), ('G6', 1)], .58)
mel(14, [('A6', 1), ('G6', .5), ('F#6', .5), ('E6', 1)], .58)
mel(15, [('F#6', .5), ('D#6', .5), ('B5', .5), ('D#6', .5), ('F#6', .5), ('A6', .5)], .55)
mel(16, [('G6', .5), ('E6', .5), ('B6', .5), ('G6', .5), ('E6', .5), ('B5', .5)], .6)
mel(17, [('A6', .5), ('F#6', .5), ('D#6', .5), ('F#6', .5), ('A6', .5), ('B6', .5)], .62)
mel(18, [('E6', 1), ('G6', .5), ('B6', 1.5, .7)], .6)
mel(19, [('E6', 3, .75)])
put(celesta(freq('B5'), 4.5 * BEAT, .45), 54 * BEAT); put(celesta(freq('G#5'), 4.5 * BEAT, .45), 54 * BEAT)
for k, n in enumerate(['E5', 'G#5', 'B5', 'E6', 'G#6', 'B6', 'E7']):
    put(celesta(freq(n), 2.0 * BEAT, 0.3), (54 + 0.11 * k) * BEAT, pan=0.15)
mel(20, [('B6', 1, .45), ('E7', 2, .4)])

CHORDS = {1: ('E2', ['E3', 'B3', 'G4']), 2: ('E2', ['E4', 'G4', 'B4']), 3: ('A2', ['A3', 'C4', 'E4']),
          4: ('B2', ['B3', 'D#4', 'F#4', 'A4']), 5: ('E2', ['E4', 'G4', 'B4']), 6: ('C3', ['C4', 'E4', 'G4']),
          7: ('A2', ['A3', 'C4', 'E4'], 'D3', ['D4', 'F#4', 'A4']), 8: ('B2', ['B3', 'D#4', 'F#4', 'A4']),
          9: ('E2', ['E4', 'G4', 'B4']), 10: ('C3', ['C4', 'E4', 'G4'], 'D3', ['D4', 'F#4', 'A4']),
          11: ('G2', ['G3', 'B3', 'D4']), 12: ('B2', ['B3', 'D#4', 'F#4', 'A4']), 13: ('E2', ['E4', 'G4', 'B4']),
          14: ('A2', ['A3', 'C4', 'E4']), 15: ('B2', ['B3', 'D#4', 'F#4', 'A4']), 16: ('E2', ['E4', 'G4', 'B4']),
          17: ('B2', ['B3', 'D#4', 'F#4', 'A4']), 18: ('C3', ['C4', 'E4', 'G4'], 'B2', ['B3', 'D#4', 'F#4', 'A4']),
          19: ('E2', ['E4', 'G#4', 'B4']), 20: ('E2', ['E4', 'G#4', 'B4'])}
for bar, ch in CHORDS.items():
    t0 = (bar - 1) * 3 * BEAT
    if bar == 1:
        pad([freq(n) for n in ch[1]], 0.0, 1.5, 0.05)
        continue
    bass, notes = ch[0], ch[1]
    notes2 = ch[3] if len(ch) > 2 else notes
    put(pluck(freq(bass), 0.6), t0, pan=-0.1)
    if len(ch) > 2:
        put(pluck(freq(ch[2]), 0.5), t0 + 1.5 * BEAT, pan=-0.1)
    if bar < 20:
        for bt, nn in ((1, notes if len(ch) == 2 else notes), (2, notes2)):
            for n in nn:
                put(pluck(freq(n), 0.16, 0.6), t0 + bt * BEAT, pan=-0.35)
    pad([freq(n) for n in notes], t0, 3 * BEAT if bar < 19 else 3.2, 0.045 if bar < 19 else 0.065)

whoosh(4.3, 1.8, 0.12); whoosh(10.9, 1.7, 0.22); whoosh(14.35, 1.0, 0.2); whoosh(15.55, 1.75, 0.2)
for k in range(4):
    whoosh(18.15 + 0.85 * k, 0.75, 0.13)
for k in range(8):
    whoosh(21.98 + 0.5 * k, 0.45, 0.14)
whoosh(25.9, 0.6, 0.12); whoosh(27.25, 0.9, 0.1)
for t0, t1, cnt in ((11.0, 12.5, 6), (15.6, 17.2, 6), (21.9, 25.9, 16), (26.0, 29.5, 12)):
    for _ in range(cnt):
        n = rng.choice(['E7', 'B6', 'G#7', 'E7', 'B7'])
        put(celesta(freq(n), 0.15, 0.08), rng.uniform(t0, t1), pan=rng.uniform(-0.8, 0.8))

dry = np.stack([L, R], 1)
tt = np.arange(int(SR * 2.2)) / SR
irL = rng.normal(0, 1, len(tt)) * np.exp(-tt / 0.42); irR = rng.normal(0, 1, len(tt)) * np.exp(-tt / 0.42)
irL[:int(0.012 * SR)] = 0; irR[:int(0.017 * SR)] = 0
irL /= np.sqrt((irL ** 2).sum()); irR /= np.sqrt((irR ** 2).sum())
wetL = fftconvolve(L, irL)[:N]; wetR = fftconvolve(R, irR)[:N]
out = dry + 0.32 * np.stack([wetL, wetR], 1)
out = out[: int(SR * DUR)]
fade = np.ones(len(out)); nf = int(0.25 * SR); fade[-nf:] = np.linspace(1, 0, nf) ** 2
out *= fade[:, None]
out = out / np.abs(out).max() * 0.89
wavfile.write('audio2.wav', SR, (out * 32767).astype(np.int16))
print('audio ok', out.shape)
