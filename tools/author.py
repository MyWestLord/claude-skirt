"""Authoring tool: choreographies + scores for every dance -> src/dances.data.js

    python3 tools/author.py          # writes src/dances.data.js and prints collision diagnostics
"""
import json, math, sys
import numpy as np
from rig import unit
import waltz_keys as WK
from waltz_keys import (A_T, A_LOW, A_FIRST, A_FIFTH, A_SECOND, A_DEMI, A_FWD, A_SIDEB, A_V, A_V2, A_JETE_B, A_BOW_UP,
                        L_FIRST, L_BOUR, L_CH, L_SUP, L_PASSE, L_BACK4, L_FRONT4, L_ARAB, L_JF, L_JB, L_TENDU, L_TSIDE,
                        L_SEC45, L_SUP2)
from timeline import Timeline, diagnose

IDLE = dict(rp=(0, 0, 0.995), yaw=0, pel=(0, 0, 0), chs=(0, 0, 0), head=(4, 0, 0), abd=(0, 0, 0),
            aL=A_LOW, aR=A_LOW, wL=(-30, 0, -20), wR=(-30, 0, -20), lL=L_FIRST, lR=L_FIRST,
            flap=(4, 1.2), bour=0, rip=0, spot=0, song=0, wag=0)

# ------------------------------------------------------------------ choreography builder
class Choreo:
    def __init__(s, bpm, meter):
        s.bpm, s.meter, s.spb = bpm, meter, 60.0 / bpm
        s.KD = {}; s.t = 0.0; s.pos = np.zeros(2); s.yaw = 0.0
        s.jumps, s.sparks, s.bursts, s.songs, s.marks = [], [], [], [], []
        s.key(0.0, True, **IDLE)

    def key(s, t, hold=False, **kw):
        t = round(float(t), 4)
        if t in s.KD:
            h, d = s.KD[t]; d.update(kw); s.KD[t] = (h or hold, d)
        else:
            s.KD[t] = (hold, dict(kw))

    def at(s, beats): return s.t + beats * s.spb
    def adv(s, beats): s.t += beats * s.spb
    def rp(s, z, p=None):
        p = s.pos if p is None else p
        return (round(float(p[0]), 4), round(float(p[1]), 4), z)
    def fwd(s):
        a = math.radians(s.yaw); return np.array([math.sin(a), -math.cos(a)])
    def mark(s, label): s.marks.append((round(s.t, 3), label))

    # ---- moves
    def wait(s, beats, **kw):
        s.adv(beats); s.key(s.t, **kw)

    def wake(s, beats=2):
        s.mark('wake')
        s.key(s.at(beats * 0.4), head=(-4, 5, -16), chs=(0, 0, -4), flap=(12, 3))
        s.key(s.at(beats), head=(6, -4, 10), chs=(2, 0, 3), flap=(5, 1.5))
        s.adv(beats)

    def port_de_bras(s, beats=3):
        s.mark('port de bras')
        s.key(s.at(beats * 0.4), aL=A_FIRST, aR=A_FIRST, wL=(-60, 0, -15), wR=(-60, 0, -15), head=(2, 0, 0))
        s.key(s.at(beats), aL=A_FIFTH, aR=A_FIFTH, chs=(-7, 0, 0), head=(-14, 0, 0), wL=(-80, 0, -20), wR=(-80, 0, -20))
        s.adv(beats)

    def bourree_turn(s, beats=3, turn=360, arms_end=A_SECOND):
        s.mark('bourrée turn')
        s.key(s.at(0.25), lL=L_BOUR, lR=L_BOUR, bour=1.0, rp=s.rp(0.99))
        s.key(s.at(beats * 0.5), yaw=s.yaw + turn / 2, aL=A_V, aR=A_V, chs=(-4, 0, 0), head=(-6, 0, 0), wL=(20, 0, -10), wR=(20, 0, -10))
        s.yaw += turn
        s.key(s.at(beats), yaw=s.yaw, aL=arms_end, aR=arms_end, chs=(0, 0, 0), head=(0, 0, -8), wL=(0, 0, -10), wR=(0, 0, -10))
        s.adv(beats)

    def bourree_path(s, pts, beats, ripple=True, arms=A_SECOND, yaw_end=None):
        s.mark('bourrée')
        n = len(pts); p0 = s.pos.copy()
        s.key(s.at(0.25), lL=L_BOUR, lR=L_BOUR, bour=1.0, rip=1.0 if ripple else 0.0, aL=arms, aR=arms,
              wL=(0, 0, -10), wR=(0, 0, -10), spot=0, song=0, wag=0, pel=(0, 0, 0), abd=(0, 0, 0))
        y0 = s.yaw; y1 = s.yaw if yaw_end is None else yaw_end
        for i, (dx, dy) in enumerate(pts):
            p = p0 + np.array([dx, dy])
            s.key(s.at(beats * (i + 1) / n), rp=s.rp(0.99, p), yaw=y0 + (y1 - y0) * (i + 1) / n,
                  head=(-2, 0, 9 if i % 2 == 0 else -9))
        s.pos = p0 + np.array(pts[-1]); s.yaw = y1
        s.adv(beats)

    def pirouette(s, turns=2, beats=3, prep=1.0):
        s.mark('pirouette x%d' % turns)
        s.key(s.at(prep * 0.8), rp=s.rp(0.94), lL=L_BACK4, lR=L_FRONT4, bour=0, rip=0, aL=A_SECOND, aR=A_FIRST,
              wL=(0, 0, -10), wR=(-60, 0, -15), chs=(2, 0, 0), head=(0, 0, 10), spot=0, pel=(0, 0, 0), abd=(0, 0, 0), song=0, wag=0)
        t1 = s.at(prep + 0.35)
        s.key(t1, rp=s.rp(0.995), lL=L_PASSE, lR=L_SUP, aL=A_FIRST, aR=A_FIRST, wL=(-60, 0, -15), wR=(-60, 0, -15),
              head=(0, 0, 0), chs=(0, 0, 0), flap=(16, 9), spot=1.0, yaw=s.yaw + 8)
        s.yaw += 360 * turns
        t2 = s.at(prep + beats)
        s.key(t2, yaw=s.yaw, spot=1.0)
        s.sparks.append((t1, t2, 75)); s.t = t2

    def open_side(s, beats=1.0):
        s.key(s.at(beats), rp=s.rp(0.97), aL=A_SECOND, aR=A_SECOND, lL=L_TSIDE, lR=L_SUP, spot=0, head=(-6, 0, -10),
              chs=(-4, 0, 0), wL=(0, 0, -10), wR=(0, 0, -10), flap=(8, 2))
        s.adv(beats)

    def close(s, beats=1.0):
        s.key(s.at(beats), rp=s.rp(0.995), lL=L_FIRST, lR=L_FIRST, pel=(0, 0, 0), chs=(0, 0, 0), abd=(0, 0, 0),
              aL=A_LOW, aR=A_LOW, wL=(-30, 0, -20), wR=(-30, 0, -20), head=(4, 0, 0), spot=0, bour=0, rip=0, song=0,
              wag=0, flap=(5, 1.5))
        s.adv(beats)

    def arabesque(s, beats_in=1.5, hold=2.0):
        s.mark('arabesque')
        s.key(s.at(beats_in), aR=A_FWD, aL=A_SIDEB, lR=L_SUP, lL=L_ARAB, pel=(14, 0, 0), chs=(6, 0, 0), head=(-10, 0, 0),
              rp=s.rp(0.995), abd=(12, 0, 42), wR=(0, 0, -5), wL=(0, 0, -8), flap=(6, 1.5), spot=0, bour=0, rip=0)
        s.key(s.at(beats_in + hold), aR=((0.03, -0.50, 0.19), (0.8, 0.2, 0.6)), aL=((0.48, 0.19, 0.10), (0, 1, 0.3)),
              pel=(17, 0, 0), chs=(8, 0, 0))
        s.adv(beats_in + hold)

    def jete(s, dist=1.1, beats=3.0, height=0.36):
        s.mark('grand jeté')
        f = s.fwd(); p0 = s.pos.copy()
        s.key(s.at(0.6), lL=('floor', (0.05, 0.12, 0), (0.8, -0.6, 0)), lR=('floor', (0.05, -0.10, 0), (0.8, -0.6, 0)),
              rp=s.rp(0.93), pel=(0, 0, 0), chs=(12, 0, 0), aL=A_LOW, aR=A_LOW, head=(4, 0, 0), abd=(0, 0, 0),
              flap=(10, 4), bour=0, rip=0, spot=0)
        tA = s.at(0.9); pA = p0 + f * 0.06
        s.key(tA, rp=s.rp(0.955, pA), lL=('floor', (0.05, 0.2, 0), (0.8, -0.6, 0)), lR=('hip', (0, -0.5, -0.6), (0, -0.3, 1)),
              chs=(6, 0, 0), aR=A_FIRST, aL=A_FIRST, flap=(28, 14), abd=(8, 0, 30))
        fl = beats - 1.5
        tM = s.at(0.9 + fl / 2); pM = p0 + f * dist * 0.5
        s.key(tM, rp=s.rp(0.97, pM), lR=L_JF, lL=L_JB, pel=(4, 0, 0), chs=(-6, 0, 0), head=(-12, 0, 0), aR=A_FWD,
              aL=A_JETE_B, abd=(10, 0, 40))
        tL = s.at(0.9 + fl); pL = p0 + f * dist
        s.key(tL, rp=s.rp(0.92, pL), lR=('floor', (0, -0.03, 0), (0.6, -0.8, 0)), lL=('hip', (0, 0.62, -0.62), (0, 0.3, -1)),
              pel=(6, 0, 0), chs=(10, 0, 0), head=(0, 0, 0), aR=A_SECOND, aL=A_SECOND, flap=(10, 3), abd=(6, 0, 30))
        s.jumps.append((round(tA, 4), round(tL, 4), height)); s.sparks.append((tA, tL, 50))
        s.pos = pL; s.t = tL
        s.key(s.at(0.6), rp=s.rp(0.995), lL=L_FIRST, lR=L_FIRST, pel=(0, 0, 0), chs=(0, 0, 0), abd=(0, 0, 0),
              aL=A_FIRST, aR=A_FIRST, wL=(-60, 0, -15), wR=(-60, 0, -15))
        s.adv(0.6)

    def chaines(s, turns=4, dist=1.4, beats=4, direction=None):
        s.mark('chaînés')
        d = s.fwd() if direction is None else unit(direction)
        t1 = s.at(0.4)
        s.key(t1, rp=s.rp(0.995), lL=L_CH, lR=L_CH, pel=(0, 0, 0), chs=(0, 0, 0), aL=A_FIRST, aR=A_FIRST, abd=(0, 0, 0),
              head=(0, 0, 0), flap=(14, 7), wL=(-60, 0, -15), wR=(-60, 0, -15), spot=1.0, bour=0, rip=0)
        s.yaw += 360 * turns; s.pos = s.pos + d * dist
        t2 = s.at(beats)
        s.key(t2, rp=s.rp(0.995), yaw=s.yaw, spot=1.0)
        s.sparks.append((t1, t2, 45)); s.t = t2

    def manege(s, turns=4, radius=0.8, beats_per=2.0):
        s.mark('manège')
        f = s.fwd()
        a0 = math.atan2(-f[0], f[1])
        C = s.pos - radius * np.array([math.cos(a0), math.sin(a0)])
        step = 360.0 / turns
        Y0 = s.yaw
        def onc(deg):
            a = a0 + math.radians(deg); return C + radius * np.array([math.cos(a), math.sin(a)])
        for k in range(turns):
            T = s.t + k * beats_per * s.spb
            Y = Y0 + (360 + step) * k
            p0, p1, p2 = onc(step * k), onc(step * k + step * 0.31), onc(step * k + step * 0.78)
            s.key(T, rp=s.rp(0.95, p0), yaw=Y, lL=L_BACK4, lR=L_FRONT4, aL=A_SECOND, aR=A_SECOND, wL=(0, 0, -10),
                  wR=(0, 0, -10), spot=0.0 if k == 0 else 0.7, chs=(3, 0, 0), flap=(12, 6), bour=0, rip=0)
            s.key(T + 0.2 / 0.85 * beats_per / 2 * s.spb * 2, rp=s.rp(0.995, p1), yaw=Y + 60, lL=L_PASSE, lR=L_SUP,
                  aL=A_FIRST, aR=A_FIRST, wL=(-60, 0, -15), wR=(-60, 0, -15), spot=0.7, chs=(0, 0, 0))
            s.key(T + 0.6 / 0.85 * beats_per * s.spb, rp=s.rp(0.995, p2), yaw=Y + 330)
        s.t += turns * beats_per * s.spb
        s.yaw = Y0 + (360 + step) * turns
        s.pos = onc(360.0)
        s.key(s.t, rp=s.rp(0.95), yaw=s.yaw, lL=L_BACK4, lR=L_FRONT4, aL=A_SECOND, aR=A_FIRST, chs=(2, 0, 0),
              wL=(0, 0, -10), wR=(-60, 0, -15), spot=0.0, head=(0, 0, 0))
        s.sparks.append((s.t - turns * beats_per * s.spb, s.t, 55))

    def fouettes(s, n=8, beats_each=1.0, double_last=True):
        s.mark('fouettés x%d' % n)
        t0 = s.t
        for k in range(n):
            T = s.t + k * beats_each * s.spb
            Y = s.yaw + 360 * k
            last = k == n - 1 and double_last
            s.key(T, rp=s.rp(0.93), yaw=Y, lL=L_SEC45, lR=L_SUP, aL=A_SECOND, aR=A_SECOND, wL=(0, 0, -10), wR=(0, 0, -10),
                  spot=1.0, flap=(18, 9), chs=(0, 0, 0), bour=0, rip=0, pel=(0, 0, 0), abd=(0, 0, 0))
            s.key(T + 0.4 * beats_each * s.spb, rp=s.rp(0.995), yaw=Y + (180 if last else 100), lL=L_PASSE,
                  aL=A_FIRST, aR=A_FIRST, wL=(-60, 0, -15), wR=(-60, 0, -15))
        s.yaw += 360 * (n - 1) + (720 if double_last else 360)
        tEnd = s.t + ((n - 1) * beats_each + 1.1 * beats_each) * s.spb
        s.key(tEnd, rp=s.rp(0.99), yaw=s.yaw, lL=L_PASSE, lR=L_SUP, spot=0.6)
        s.sparks.append((t0, tEnd, 170)); s.t = tEnd

    def tour_en_lair(s, beats=2.0, height=0.30):
        s.mark("tour en l'air")
        s.key(s.at(0.5), rp=s.rp(0.93), lL=L_FIRST, lR=L_FIRST, aL=A_LOW, aR=A_LOW, chs=(6, 0, 0), bour=0, rip=0, spot=0,
              pel=(0, 0, 0), abd=(0, 0, 0), song=0, wag=0)
        tA = s.at(0.75)
        s.key(tA, rp=s.rp(0.96), aL=A_FIRST, aR=A_FIRST, chs=(0, 0, 0), flap=(26, 13), wL=(-60, 0, -15), wR=(-60, 0, -15))
        tL = s.at(beats - 0.25)
        tM = (tA + tL) / 2
        s.key(tM, lL=('hip', (0.0, -0.02, -0.86), (0.3, -1, 0)), lR=('hip', (0.0, -0.02, -0.86), (0.3, -1, 0)),
              aL=A_FIFTH, aR=A_FIFTH, yaw=s.yaw + 180, spot=0.8, wL=(-80, 0, -20), wR=(-80, 0, -20))
        s.yaw += 360
        s.key(tL, rp=s.rp(0.93), yaw=s.yaw, lL=L_FIRST, lR=L_FIRST, aL=A_SECOND, aR=A_SECOND, spot=0, flap=(8, 2),
              wL=(0, 0, -10), wR=(0, 0, -10))
        s.jumps.append((round(tA, 4), round(tL, 4), height)); s.sparks.append((tA, tL, 40))
        s.t = tL
        s.key(s.at(0.25), rp=s.rp(0.995)); s.adv(0.25)

    def waggle(s, runs=2, run_len=0.9, beats_run=4, beats_ret=4, angle=0.0):
        s.mark('waggle dance')
        start = s.pos.copy()
        d = np.array([math.sin(math.radians(angle)), -math.cos(math.radians(angle))])
        s.yaw = s.yaw + (angle - ((s.yaw + 180) % 360 - 180))
        for r in range(runs):
            s.key(s.at(0.3), lL=L_BOUR, lR=L_BOUR, bour=1.0, wag=1.0, rp=s.rp(0.99, start), yaw=s.yaw, aL=A_SECOND,
                  aR=A_SECOND, wL=(0, 0, -10), wR=(0, 0, -10), flap=(30, 15), head=(-6, 0, 0), chs=(-4, 0, 0), spot=0,
                  rip=0, pel=(0, 0, 0), abd=(0, 0, 0))
            pe = start + d * run_len
            s.key(s.at(beats_run), rp=s.rp(0.99, pe), wag=1.0)
            s.adv(beats_run)
            side = 1 if r % 2 == 0 else -1
            perp = np.array([-d[1], d[0]]) * side
            c = start + d * run_len * 0.5; R = run_len * 0.5
            s.key(s.at(0.25), wag=0.0, flap=(8, 3), aL=A_V, aR=A_V, wL=(20, 0, -10), wR=(20, 0, -10))
            for j, u in enumerate((1 / 3, 2 / 3, 1.0)):
                p = c + R * (math.cos(math.pi * u) * d + math.sin(math.pi * u) * perp)
                s.key(s.at(beats_ret * u), rp=s.rp(0.99, p), yaw=s.yaw + 360 * u * side, head=(0, 0, -10 * side))
            s.yaw += 360 * side
            s.adv(beats_ret)
        s.pos = start

    def courtship(s, beats=6):
        s.mark('courtship song')
        t0 = s.at(0.6)
        s.key(t0, song=1.0, rp=s.rp(0.985), lL=L_TENDU, lR=L_SUP2, aL=((0.36, -0.12, 0.20), (0.2, 1, 0.4)), aR=A_LOW,
              wL=(20, 0, -10), wR=(-30, 0, -20), chs=(-3, 6, 0), head=(-6, 10, -18), abd=(4, 0, -10), bour=0, rip=0, spot=0,
              flap=(2, 1), pel=(0, 0, 0))
        t1 = s.at(beats - 0.5)
        s.key(t1, song=1.0, head=(-8, -6, -12), chs=(-4, 8, 4))
        s.key(s.at(beats), song=0.0, abd=(0, 0, 0))
        s.songs.append((round(t0, 3), round(t1, 3)))
        s.adv(beats)

    def glitch(s, n=4, beats_each=1.0):
        s.mark('glitch pops')
        poses = [dict(aL=A_T, aR=A_T, head=(0, 0, 20), chs=(0, 0, 10), wL=(0, 0, 0), wR=(0, 0, 0)),
                 dict(aL=A_V, aR=A_LOW, head=(-10, 0, -25), chs=(0, 8, -6), wL=(30, 0, -10), wR=(-30, 0, -20)),
                 dict(aL=A_FWD, aR=A_FWD, head=(5, 0, 0), chs=(8, 0, 0), wL=(0, 0, -5), wR=(0, 0, -5)),
                 dict(aL=A_SECOND, aR=A_V, head=(0, -10, 15), chs=(0, -6, 4), wL=(0, 0, -10), wR=(20, 0, -10)),
                 dict(aL=((0.2, -0.3, 0.3), (1, 0, 0)), aR=((0.2, -0.3, -0.2), (1, 0, 0)), head=(0, 0, -30), chs=(0, 0, -8),
                      wL=(0, 0, 0), wR=(0, 0, 0))]
        s.key(s.at(0.0), rp=s.rp(0.995), lL=L_FIRST, lR=L_FIRST, bour=0, rip=0, spot=0, pel=(0, 0, 0), abd=(0, 0, 0))
        for k in range(n):
            T = s.at(k * beats_each)
            P = dict(poses[(k + int(s.t * 7)) % len(poses)])
            s.key(T, True)
            s.key(T + 0.1, True, **P)
        s.adv(n * beats_each)
        s.key(s.t, True)

    def finale(s, beats=4):
        s.mark('finale')
        s.key(s.at(0.8), rp=s.rp(0.985), lL=L_TENDU, lR=L_SUP2, aL=A_V, aR=A_V, chs=(-9, 0, 0), head=(-16, 0, -12),
              wL=(30, 0, -10), wR=(30, 0, -10), flap=(10, 2), spot=0, bour=0, rip=0, song=0, wag=0, pel=(0, 0, 0), abd=(0, 0, 0))
        s.key(s.at(beats), aL=A_V2, aR=A_V2, chs=(-10, 0, 0), head=(-14, 0, -16))
        s.bursts.append(round(s.at(0.9), 3)); s.adv(beats)

    def bow(s, beats=3):
        s.mark('révérence')
        s.key(s.at(beats * 0.45), rp=s.rp(0.93), chs=(24, 0, 0), head=(22, 0, 0), aL=A_DEMI, aR=A_BOW_UP,
              lL=('floor', (0.08, 0.16, 0), (0.8, -0.6, 0)), lR=('floor', (0.0, -0.02, 0), (0.6, -0.8, 0)),
              wL=(0, 0, -10), wR=(10, 0, -10), spot=0, bour=0, rip=0, song=0, wag=0, pel=(0, 0, 0), abd=(0, 0, 0))
        s.key(s.at(beats), rp=s.rp(0.99), chs=(-6, 0, 0), head=(-8, 0, -10), aL=A_V2, aR=A_V2, lL=L_TENDU, lR=L_SUP2,
              wL=(30, 0, -10), wR=(30, 0, -10))
        s.adv(beats)

    def to_idle(s, beats=3):
        s.mark('home')
        home = 360.0 * round(s.yaw / 360.0)
        if np.linalg.norm(s.pos) > 0.05:
            s.key(s.at(0.35), lL=L_BOUR, lR=L_BOUR, bour=1.0, aL=A_LOW, aR=A_LOW, chs=(0, 0, 0), head=(4, 0, 0),
                  wL=(-30, 0, -20), wR=(-30, 0, -20), pel=(0, 0, 0), abd=(0, 0, 0), spot=0, rip=0, song=0, wag=0)
            s.key(s.at(beats * 0.75), rp=(0, 0, 0.99), yaw=home)
            s.pos = np.zeros(2)
        s.yaw = home
        d = dict(IDLE); d['yaw'] = home
        s.key(s.at(beats), True, **d)
        s.adv(beats)

    def export(s):
        ts = sorted(s.KD)
        keys = []
        for t in ts:
            h, kw = s.KD[t]
            keys.append({'t': t, 'h': 1 if h else 0, **{k: _js(v) for k, v in kw.items()}})
        return {'keys': keys, 'jumps': s.jumps, 'sparks': [(round(a, 3), round(b, 3), r) for a, b, r in s.sparks],
                'bursts': s.bursts, 'songs': s.songs, 'marks': s.marks, 'dur': round(s.t, 3)}


def _js(v):
    if isinstance(v, tuple) and len(v) == 3 and isinstance(v[0], str):
        return [v[0], [float(x) for x in v[1]], [float(x) for x in v[2]]]
    if isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], tuple):
        return [[float(x) for x in v[0]], [float(x) for x in v[1]]]
    if isinstance(v, (tuple, list, np.ndarray)):
        return [round(float(x), 4) for x in v]
    return round(float(v), 4)

# ------------------------------------------------------------------ music
NAMES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def hz(n):
    k = NAMES[n[0]]; i = 1
    if n[1] == '#': k += 1; i = 2
    elif n[1] == 'b': k -= 1; i = 2
    return 440.0 * 2 ** ((12 * (int(n[i:]) + 1) + k - 69) / 12)


class Score:
    def __init__(s, bpm, offset=0.0):
        s.spb = 60.0 / bpm; s.off = offset; s.ev = []
    def T(s, beat): return round(s.off + beat * s.spb, 4)
    def D(s, beats): return round(beats * s.spb, 4)
    def add(s, beat, inst, *args): s.ev.append([s.T(beat), inst, *args])
    def cel(s, b, d, n, v=0.55, pan=0.15): s.add(b, 'cel', round(hz(n), 2), s.D(d), v, pan)
    def plk(s, b, d, n, v=0.5, pan=-0.2): s.add(b, 'plk', round(hz(n), 2), s.D(d), v, pan)
    def harp(s, b, d, n, v=0.35, pan=-0.3): s.add(b, 'harp', round(hz(n), 2), s.D(d), v, pan)
    def lead(s, b, d, n, v=0.5): s.add(b, 'lead', round(hz(n), 2), s.D(d), v)
    def buzz(s, b, d, n, v=0.4): s.add(b, 'buzz', round(hz(n), 2), s.D(d), v)
    def pad(s, b, d, notes, v=0.06): s.add(b, 'pad', [round(hz(n), 2) for n in notes], s.D(d), v)
    def brass(s, b, d, notes, v=0.3): s.add(b, 'brass', [round(hz(n), 2) for n in notes], s.D(d), v)
    def bass(s, b, d, n, v=0.5): s.add(b, 'bass', round(hz(n), 2), s.D(d), v)
    def kick(s, b, v=0.9): s.add(b, 'kick', v)
    def hat(s, b, v=0.25): s.add(b, 'hat', v)
    def snare(s, b, v=0.45): s.add(b, 'snare', v)
    def wood(s, b, v=0.4, f=900): s.add(b, 'wood', v, f)
    def timp(s, b, n, v=0.7): s.add(b, 'timp', round(hz(n), 2), v)
    def crash(s, b, v=0.5): s.add(b, 'crash', v)
    def whoosh(s, b, d, v=0.2): s.add(b, 'whoosh', s.D(d), v)
    def song(s, t0, t1): s.ev.append([round(t0, 4), 'song', round(t1 - t0, 4)])
    def chime(s, t, n, v=0.08): s.ev.append([round(t, 4), 'cel', round(hz(n), 2), 0.08, v, float(np.random.uniform(-0.8, 0.8))])

    def melody(s, bar_beats, bar, items, v=0.55, inst='cel'):
        b0 = bar_beats * (bar - 1); x = 0.0
        for it in items:
            n, d = it[0], it[1]; vv = it[2] if len(it) > 2 else v
            if n != 'r':
                getattr(s, inst)(b0 + x, d, n, vv)
            x += d


def sorted_events(sc):
    return sorted(sc.ev, key=lambda e: e[0])

# ------------------------------------------------------------------ dance 1: Bee Waltz (the original video routine)
def dance_waltz():
    off = 0.6
    KD = {}
    for t, (h, kw) in WK.KD.items():
        KD[round(t + off, 4)] = (h, dict(kw))
    d0 = dict(IDLE)
    KD[0.0] = (True, d0)
    for t in list(KD):
        if t > 26.0 + off:
            del KD[t]
    c = Choreo(120, 3)
    c.KD = KD
    c.t = 26.45 + off
    c.pos = np.array([-0.3, 0.25]); c.yaw = 7905.0
    c.key(c.t, rp=(-0.3, 0.25, 0.985), lL=L_TENDU, lR=L_SUP2, aL=A_V, aR=A_V, chs=(-9, 0, 0), head=(-16, 0, -12),
          wL=(30, 0, -10), wR=(30, 0, -10), flap=(10, 2), spot=0.0, yaw=7905)
    c.key(27.1 + off, aL=A_V2, aR=A_V2, chs=(-10, 0, 0), head=(-14, 0, -16))
    c.t = 27.3 + off
    c.bow(beats=3)
    c.to_idle(beats=3)
    c.jumps = [(round(14.45 + off, 4), round(15.25 + off, 4), 0.36)]
    c.sparks = [(a + off, b + off, r) for a, b, r in ((10.95, 12.45, 80), (14.45, 15.2, 60), (15.6, 17.2, 55),
                                                     (18.0, 21.4, 60), (21.9, 25.95, 170))]
    c.bursts = [round(26.0 + off, 3)]
    c.marks = [(0.6, 'T-pose'), (2.3, 'wake'), (4.9, 'bourrée'), (11.2, 'pirouette'), (13.8, 'arabesque'),
               (15.0, 'grand jeté'), (16.2, 'chaînés'), (18.6, 'manège'), (22.5, 'fouettés'), (27.0, 'finale')]
    ex = c.export()
    sc = Score(120, offset=off)
    BB = 3
    M = sc.melody
    M(BB, 1, [('r', 0.4), ('E5', .5, .32), ('G5', .5, .36), ('B5', .5, .4), ('E6', 1.1, .45)])
    M(BB, 2, [('B5', 1), ('G5', .5), ('A5', .5), ('B5', 1)], .6)
    M(BB, 3, [('C6', 1), ('B5', .5), ('A5', .5), ('E6', 1)], .6)
    M(BB, 4, [('D#6', .5), ('E6', .5), ('F#6', .5), ('E6', .5), ('D#6', .5), ('B5', .5)], .52)
    M(BB, 5, [('E6', 1.5), ('D6', .5), ('C6', .5), ('B5', .5)], .55)
    M(BB, 6, [('C6', 1), ('E6', .5), ('G6', .5), ('E6', 1)], .55)
    M(BB, 7, [('A5', .5), ('C6', .5), ('E6', .5), ('F#6', 1.5)], .58)
    M(BB, 8, [('F#5', .5)] + [(n, .25, .42 + .02 * k) for k, n in enumerate(['G5', 'A5', 'B5', 'C6', 'D#6', 'E6', 'F#6', 'G6', 'A6', 'B6'])])
    M(BB, 9, [('G6', 1.5, .7), ('F#6', .5), ('E6', 1)], .55)
    M(BB, 10, [('E6', .5), ('G6', .5), ('A6', .5), ('B6', 1.5, .7)], .58)
    M(BB, 11, [(n, .25, .45) for n in ['B6', 'A6', 'G6', 'F#6', 'G6', 'A6', 'B6', 'A6', 'G6', 'F#6', 'E6', 'D6']])
    M(BB, 12, [('D#6', .5), ('F#6', .5), ('B6', 1, .65), ('A6', .5), ('F#6', .5)], .55)
    M(BB, 13, [('E6', 1), ('B5', .5), ('E6', .5), ('G6', 1)], .58)
    M(BB, 14, [('A6', 1), ('G6', .5), ('F#6', .5), ('E6', 1)], .58)
    M(BB, 15, [('F#6', .5), ('D#6', .5), ('B5', .5), ('D#6', .5), ('F#6', .5), ('A6', .5)], .55)
    M(BB, 16, [('G6', .5), ('E6', .5), ('B6', .5), ('G6', .5), ('E6', .5), ('B5', .5)], .6)
    M(BB, 17, [('A6', .5), ('F#6', .5), ('D#6', .5), ('F#6', .5), ('A6', .5), ('B6', .5)], .62)
    M(BB, 18, [('E6', 1), ('G6', .5), ('B6', 1.5, .7)], .6)
    M(BB, 19, [('E6', 3, .75)])
    sc.cel(54, 4.5, 'B5', .45); sc.cel(54, 4.5, 'G#5', .45)
    for k, n in enumerate(['E5', 'G#5', 'B5', 'E6', 'G#6', 'B6', 'E7']):
        sc.cel(54 + 0.11 * k, 2.0, n, 0.3)
    M(BB, 20, [('B6', 1, .45), ('E7', 2, .4)])
    M(BB, 21, [('E6', 1.5, .35), ('B5', 1.5, .3)])
    M(BB, 22, [('E5', 3, .3)])
    CH = {1: ('E2', ['E3', 'B3', 'G4']), 2: ('E2', ['E4', 'G4', 'B4']), 3: ('A2', ['A3', 'C4', 'E4']),
          4: ('B2', ['B3', 'D#4', 'F#4', 'A4']), 5: ('E2', ['E4', 'G4', 'B4']), 6: ('C3', ['C4', 'E4', 'G4']),
          7: ('A2', ['A3', 'C4', 'E4'], 'D3', ['D4', 'F#4', 'A4']), 8: ('B2', ['B3', 'D#4', 'F#4', 'A4']),
          9: ('E2', ['E4', 'G4', 'B4']), 10: ('C3', ['C4', 'E4', 'G4'], 'D3', ['D4', 'F#4', 'A4']),
          11: ('G2', ['G3', 'B3', 'D4']), 12: ('B2', ['B3', 'D#4', 'F#4', 'A4']), 13: ('E2', ['E4', 'G4', 'B4']),
          14: ('A2', ['A3', 'C4', 'E4']), 15: ('B2', ['B3', 'D#4', 'F#4', 'A4']), 16: ('E2', ['E4', 'G4', 'B4']),
          17: ('B2', ['B3', 'D#4', 'F#4', 'A4']), 18: ('C3', ['C4', 'E4', 'G4'], 'B2', ['B3', 'D#4', 'F#4', 'A4']),
          19: ('E2', ['E4', 'G#4', 'B4']), 20: ('E2', ['E4', 'G#4', 'B4']), 21: ('E2', ['E4', 'G#4', 'B4']), 22: ('E2', ['E4', 'G#4', 'B4'])}
    for bar, ch in CH.items():
        b0 = (bar - 1) * 3
        if bar == 1:
            sc.pad(0, 3, ch[1], 0.05); continue
        sc.plk(b0, 2.5, ch[0], 0.6, -0.1)
        if len(ch) > 2:
            sc.plk(b0 + 1.5, 1.5, ch[2], 0.5, -0.1)
        n2 = ch[3] if len(ch) > 2 else ch[1]
        if bar < 20:
            for bt, nn in ((1, ch[1]), (2, n2)):
                for n in nn:
                    sc.plk(b0 + bt, 1.2, n, 0.16, -0.35)
        sc.pad(b0, 3, ch[1], 0.045 if bar < 19 else 0.06)
    for b, d in ((8.6, 3.6), (20.6, 3.4), (27.7, 2.0), (31.1, 3.5)):
        sc.whoosh(b, d, 0.2)
    for k in range(4):
        sc.whoosh(36.3 + 1.7 * k, 1.5, 0.13)
    for k in range(8):
        sc.whoosh(43.96 + k, 0.9, 0.14)
    rng = np.random.default_rng(5)
    for t0, t1, cnt in ((11.6, 13.1, 6), (16.2, 17.8, 6), (22.5, 26.5, 16), (26.6, 29.5, 10)):
        for _ in range(cnt):
            sc.chime(float(rng.uniform(t0, t1)), str(rng.choice(['E7', 'B6', 'G#7', 'E7', 'B7'])))
    ex['music'] = sorted_events(sc)
    ex['beats'] = [round(off + 2 * 1.5 + 0.5 * k, 3) for k in range(int((26.5 - 3.0) / 0.5))]
    ex['cam'] = [[round(c[0] + off, 3), *c[1:]] for c in WK.CAM]
    return ex

# ------------------------------------------------------------------ dance 2: Swan Bourrée
def dance_swan():
    c = Choreo(84, 3)
    c.port_de_bras(3)
    c.bourree_turn(3, 360, A_SECOND)
    c.bourree_path([(-0.35, -0.2), (-0.8, -0.25), (-1.2, 0.0), (-1.4, 0.35)], 6, ripple=True, yaw_end=c.yaw - 20)
    c.arabesque(1.5, 2.5)
    c.close(1)
    c.bourree_path([(0.45, -0.25), (0.9, -0.3), (1.25, -0.05), (1.45, 0.2)], 6, ripple=True, yaw_end=c.yaw + 25)
    c.pirouette(2, 3, 1.0)
    c.open_side(1)
    c.bow(4)
    c.to_idle(3)
    ex = c.export()
    sc = Score(84)
    BB = 3
    M = lambda bar, items, v=0.5: sc.melody(BB, bar, items, v, 'lead')
    M(1, [('F#5', 2), ('G5', .5), ('F#5', .5)])
    M(2, [('E5', 1.5), ('D5', .5), ('C#5', 1)])
    M(3, [('C#5', 1), ('D5', .5), ('E5', .5), ('A#4', 1)])
    M(4, [('B4', 3)])
    M(5, [('D5', 1), ('G5', 1), ('F#5', 1)])
    M(6, [('E5', 1.5), ('G5', .5), ('B5', 1)])
    M(7, [('A5', 1), ('G5', .5), ('E5', .5), ('C#5', 1)])
    M(8, [('F#5', 2), ('E5', .5), ('A#4', .5)])
    M(9, [('B4', 1), ('D5', 1), ('F#5', 1)])
    M(10, [('B5', 1.5), ('A5', .5), ('G5', .5), ('F#5', .5)])
    M(11, [('E5', 1), ('C#5', 1), ('A#4', 1)])
    M(12, [('B4', 3)])
    M(13, [('r', 1), ('F#5', 1, .35), ('B5', 1, .3)])
    total_beats = ex['dur'] / sc.spb
    CH = ['Bm', 'Em', 'F#7', 'Bm', 'G', 'Em', 'C#dim', 'F#7', 'Bm', 'Em', 'F#7', 'Bm', 'Bm']
    CN = {'Bm': ['B3', 'D4', 'F#4'], 'Em': ['E3', 'G3', 'B3'], 'F#7': ['F#3', 'A#3', 'C#4', 'E4'], 'G': ['G3', 'B3', 'D4'],
          'C#dim': ['C#4', 'E4', 'G4'], }
    BASS = {'Bm': 'B2', 'Em': 'E2', 'F#7': 'F#2', 'G': 'G2', 'C#dim': 'C#3'}
    nbars = int(math.ceil(total_beats / 3))
    for bar in range(1, nbars + 1):
        ch = CH[min(bar - 1, len(CH) - 1)]
        b0 = (bar - 1) * 3
        sc.pad(b0, 3, CN[ch], 0.05)
        sc.plk(b0, 3, BASS[ch], 0.45, -0.1)
        for k in range(6):
            n = (CN[ch] * 3)[k]
            n = n[:-1] + str(int(n[-1]) + 1)
            sc.harp(b0 + 0.5 * k, 1.2, n, 0.22 if bar < nbars else 0.15)
    pir = [m for m in ex['marks'] if m[1].startswith('pirouette')][0][0] / sc.spb
    sc.whoosh(3, 3, 0.1); sc.whoosh(pir + 1, 3, 0.15)
    ex['music'] = sorted_events(sc)
    ex['beats'] = [round(k * sc.spb, 3) for k in range(3, int(total_beats) - 3)]
    return ex

# ------------------------------------------------------------------ dance 3: Fouetté Storm
def dance_storm():
    c = Choreo(150, 2)
    c.wait(2)
    c.pirouette(2, 3, 1)
    c.chaines(4, 1.3, 6, direction=(-1, 0))
    c.open_side(2)
    c.tour_en_lair(3)
    c.manege(4, 0.75, 2.0)
    c.fouettes(16, 1.0, True)
    c.finale(4)
    c.bow(3)
    c.to_idle(4)
    ex = c.export()
    sc = Score(150)
    tb = ex['dur'] / sc.spb
    A = [['E5', 'A5', 'C6', 'A5'], ['B5', 'G#5', 'E5', 'G#5'], ['C6', 'B5', 'A5', 'E5'], ['D6', 'C6', 'B5', 'G#5'],
         ['F5', 'A5', 'D6', 'A5'], ['E6', 'C6', 'A5', 'C6'], ['B5', 'D6', 'G#5', 'B5'], ['A5', 'r', 'E5', 'r']]
    CHA = ['Am', 'E7', 'Am', 'E7', 'Dm', 'Am', 'E7', 'Am']
    CN = {'Am': ('A2', ['A3', 'C4', 'E4']), 'E7': ('E2', ['G#3', 'B3', 'D4']), 'Dm': ('D2', ['D4', 'F4', 'A4']),
          'A': ('A2', ['A3', 'C#4', 'E4']), 'E': ('E2', ['G#3', 'B3', 'E4'])}
    nb = int(math.ceil(tb / 2))
    fstart = [m for m in ex['marks'] if m[1].startswith('fouett')][0][0] / sc.spb
    fend = fstart + 16
    for bar in range(nb):
        b0 = bar * 2
        if b0 < 2:
            for k in range(8):
                sc.snare(b0 + 0.25 * k, 0.12 + 0.05 * k)
            continue
        if b0 >= tb - 8:
            ch = 'A' if b0 < tb - 4 else 'A'
            if b0 < tb - 6:
                sc.brass(b0, 2, ['A3', 'C#4', 'E4', 'A4'], 0.25); sc.timp(b0, 'A2', 0.8); sc.crash(b0, 0.4)
            sc.pad(b0, 2, CN[ch][1], 0.05)
            continue
        if fstart - 0.01 <= b0 < fend:
            k = int((b0 - fstart) // 2)
            ch = ['Am', 'Am', 'Dm', 'Dm', 'E7', 'E7', 'Am', 'E7'][k % 8]
            base = {'Am': ['A5', 'C6', 'E6', 'C6', 'A5', 'C6', 'E6', 'A6'], 'Dm': ['D6', 'F6', 'A6', 'F6', 'D6', 'F6', 'A6', 'D6'],
                    'E7': ['B5', 'D6', 'E6', 'G#6', 'B5', 'D6', 'E6', 'B6']}[ch]
            for j, n in enumerate(base):
                sc.cel(b0 + 0.25 * j, 0.3, n, 0.42)
            sc.snare(b0 + 0.5, 0.35); sc.snare(b0 + 1.5, 0.35); sc.hat(b0 + 1, 0.2)
            sc.whoosh(b0, 0.9, 0.12); sc.whoosh(b0 + 1, 0.9, 0.12)
        else:
            k = (bar - 1) % 8
            ch = CHA[k]
            for j, n in enumerate(A[k]):
                if n != 'r':
                    sc.cel(b0 + 0.5 * j, 0.5, n, 0.5)
            sc.snare(b0 + 0.5, 0.2); sc.snare(b0 + 1.5, 0.2)
        bass, notes = CN[ch]
        sc.plk(b0, 0.9, bass, 0.6, -0.1); sc.plk(b0 + 1, 0.9, bass[:-1] + str(int(bass[-1]) + 1), 0.4, -0.1)
        for n in notes:
            sc.plk(b0 + 0.5, 0.4, n, 0.16, -0.35); sc.plk(b0 + 1.5, 0.4, n, 0.16, -0.35)
        sc.pad(b0, 2, notes, 0.035)
    rng = np.random.default_rng(9)
    for _ in range(26):
        sc.chime(float(rng.uniform(fstart * sc.spb, fend * sc.spb)), str(rng.choice(['A6', 'E7', 'C7', 'A7'])))
    ex['music'] = sorted_events(sc)
    ex['beats'] = [round(k * sc.spb, 3) for k in range(2, int(tb) - 6)]
    return ex

# ------------------------------------------------------------------ dance 4: Waggle Dance (honeybee)
def dance_waggle():
    c = Choreo(112, 4)
    c.wake(2)
    c.waggle(2, 0.95, 4, 4, angle=0)
    c.tour_en_lair(3)
    c.yaw += 90 - ((c.yaw + 180) % 360 - 180)
    c.key(c.at(0.8), yaw=c.yaw); c.adv(0.8)
    c.jete(1.05, 3)
    c.yaw += 180
    c.key(c.at(1.0), yaw=c.yaw, rp=c.rp(0.995)); c.adv(1.0)
    c.jete(1.05, 3)
    c.yaw += 90
    c.key(c.at(0.8), yaw=c.yaw); c.adv(0.8)
    c.waggle(2, 0.8, 4, 4, angle=35)
    c.finale(3)
    c.bow(3)
    c.to_idle(3)
    ex = c.export()
    sc = Score(112)
    tb = ex['dur'] / sc.spb
    nb = int(math.ceil(tb / 4))
    CH = ['D', 'G', 'A7', 'D', 'Bm', 'G', 'A7', 'D']
    CN = {'D': ('D2', ['D4', 'F#4', 'A4']), 'G': ('G2', ['G3', 'B3', 'D4']), 'A7': ('A2', ['A3', 'C#4', 'G4']),
          'Bm': ('B2', ['B3', 'D4', 'F#4'])}
    RIFF = {'D': ['F#5', 'A5', 'D6', 'A5', 'B5', 'A5', 'F#5', 'E5'], 'G': ['G5', 'B5', 'D6', 'B5', 'C6', 'B5', 'G5', 'D5'],
            'A7': ['E5', 'A5', 'C#6', 'E6', 'G5', 'E5', 'C#5', 'A4'], 'Bm': ['F#5', 'B5', 'D6', 'B5', 'C#6', 'B5', 'F#5', 'D5']}
    wag_t = [(k['t']) for k in ex['keys'] if k.get('wag', 0) == 1.0]
    for bar in range(nb):
        b0 = bar * 4; ch = CH[bar % 8]
        bass, notes = CN[ch]
        sc.bass(b0, 1.6, bass, 0.55); sc.bass(b0 + 2, 1.6, bass[:-1] + str(int(bass[-1]) + 1) if ch != 'A7' else 'E2', 0.45)
        sc.wood(b0 + 1, 0.35); sc.wood(b0 + 3, 0.35); sc.hat(b0 + 0.66, 0.12); sc.hat(b0 + 2.66, 0.12)
        sc.pad(b0, 4, notes, 0.035)
        if b0 >= tb - 6:
            sc.brass(b0, 4, [n.replace('4', '4') for n in notes], 0.2); continue
        t_sec = b0 * sc.spb
        waggling = any(abs(t_sec - w) < 2.2 for w in wag_t)
        if bar == 0:
            continue
        for j, n in enumerate(RIFF[ch]):
            sw = 0.66 if j % 2 else 0.0
            sc.buzz(b0 + (j // 2) + sw, 0.42, n, 0.33 if not waggling else 0.4)
        if waggling:
            for j in range(16):
                sc.cel(b0 + 0.25 * j, 0.2, ['D6', 'E6'][j % 2], 0.18)
    ex['music'] = sorted_events(sc)
    ex['beats'] = [round(k * sc.spb, 3) for k in range(4, int(tb) - 4)]
    return ex

# ------------------------------------------------------------------ dance 5: Fly Brain Freestyle (6 variants)
def dance_freestyle(seed):
    rng = np.random.default_rng(seed)
    c = Choreo(124, 4)
    c.glitch(4, 1.0)
    blocks = ['pir', 'song', 'glitch', 'chaines', 'tour', 'waggle', 'jete', 'fouettes', 'bturn']
    order = list(rng.permutation(blocks))
    order = ['song'] + [b for b in order if b != 'song']
    used = 0
    for b in order:
        if c.t > 30.0:
            break
        if b == 'pir':
            c.pirouette(int(rng.integers(2, 4)), 3, 1); c.open_side(1)
        elif b == 'song':
            c.courtship(8)
        elif b == 'glitch':
            c.glitch(4, 1.0)
        elif b == 'chaines':
            ang = float(rng.uniform(0, 2 * np.pi)); d = np.array([math.cos(ang), math.sin(ang)])
            if np.linalg.norm(c.pos + d * 1.2) > 1.6: d = -d
            c.chaines(4, 1.2, 4, direction=d); c.open_side(1)
        elif b == 'tour':
            c.tour_en_lair(3)
        elif b == 'waggle':
            c.waggle(1, 0.8, 4, 4, angle=float(rng.uniform(-40, 40)))
        elif b == 'jete':
            f = c.fwd()
            if np.linalg.norm(c.pos + f * 1.0) > 1.6:
                c.yaw += 180; c.key(c.at(1), yaw=c.yaw); c.adv(1)
            c.jete(1.0, 3)
        elif b == 'fouettes':
            c.fouettes(8, 1.0, True)
        elif b == 'bturn':
            c.bourree_turn(4, 360 * int(rng.choice([-1, 1])), A_SECOND)
        used += 1
    c.finale(3)
    c.to_idle(3)
    ex = c.export()
    sc = Score(124)
    tb = ex['dur'] / sc.spb
    nb = int(math.ceil(tb / 4))
    CH = ['Fm', 'Db', 'Eb', 'Cm']
    CN = {'Fm': ('F2', ['F3', 'Ab3', 'C4']), 'Db': ('Db2', ['Db3', 'F3', 'Ab3']), 'Eb': ('Eb2', ['Eb3', 'G3', 'Bb3']),
          'Cm': ('C2', ['C3', 'Eb3', 'G3'])}
    LEAD = ['C5', 'Eb5', 'F5', 'Ab5', 'G5', 'F5', 'Eb5', 'C5']
    songs = ex['songs']
    for bar in range(nb):
        b0 = bar * 4; ch = CH[bar % 4]; bass, notes = CN[ch]
        tsec = b0 * sc.spb
        in_song = any(a - 0.2 <= tsec <= b for a, b in songs)
        last = b0 >= tb - 5
        for j in range(4):
            sc.kick(b0 + j, 0.8 if not in_song else 0.5)
            if not in_song:
                sc.hat(b0 + j + 0.5, 0.18)
        if not in_song:
            sc.snare(b0 + 1, 0.3); sc.snare(b0 + 3, 0.3)
        for j in range(8):
            sc.bass(b0 + 0.5 * j, 0.4, bass if j % 2 == 0 else bass[:-1] + str(int(bass[-1]) + 1), 0.38)
        sc.pad(b0, 4, notes, 0.03)
        if bar >= 1 and not in_song and not last:
            for j, n in enumerate(LEAD):
                if (bar + j) % 3 != 2:
                    sc.buzz(b0 + 0.5 * j, 0.35, n, 0.24)
        if last:
            sc.crash(b0, 0.4); sc.brass(b0, 4, ['F3', 'Ab3', 'C4', 'F4'], 0.18)
    for a, b in songs:
        sc.song(a, b)
    ex['music'] = sorted_events(sc)
    ex['beats'] = [round(k * sc.spb, 3) for k in range(4, int(tb) - 4)]
    return ex


DANCES = [
    ('waltz', 'Bee Waltz', 'The routine from the trailer: T-pose to 8 fouettés.', 120, 3, 'E minor music box', dance_waltz),
    ('swan', 'Swan Bourrée', 'Tiny steps on pointe and rippling swan arms.', 84, 3, 'B minor, oboe and harp', dance_swan),
    ('storm', 'Fouetté Storm', 'Chaînés, a manège and sixteen fouettés.', 150, 2, 'A minor galop', dance_storm),
    ('waggle', 'Waggle Dance', 'The honeybee figure-eight, with jetés.', 112, 4, 'D major, buzz kazoo', dance_waggle),
]


def main():
    out = {'dances': [], 'freestyle': []}
    for did, name, sub, bpm, meter, music, fn in DANCES:
        ex = fn()
        ex.update({'id': did, 'name': name, 'sub': sub, 'bpm': bpm, 'meter': meter, 'musicName': music})
        out['dances'].append(ex)
    for seed in range(6):
        ex = dance_freestyle(100 + seed)
        ex.update({'id': 'free', 'name': 'Fly Brain Freestyle', 'sub': 'Improvised: a new set of moves every time.',
                   'bpm': 124, 'meter': 4, 'musicName': 'F minor techno, fly pulse song'})
        out['freestyle'].append(ex)
    js = '// Generated by tools/author.py. Do not edit by hand.\nexport const DANCES = ' + json.dumps(out, separators=(',', ':')) + ';\n'
    open('../src/dances.data.js', 'w').write(js)
    print('wrote %.1f KB' % (len(js) / 1024))
    if '--check' in sys.argv:
        for ex in out['dances'] + out['freestyle'][:2]:
            KD = {k['t']: (bool(k['h']), {kk: _py(vv) for kk, vv in k.items() if kk not in ('t', 'h')}) for k in ex['keys']}
            tl = Timeline(KD, [tuple(j) for j in ex['jumps']])
            fr = tl.frames(15)
            print('%-22s dur %5.1fs keys %3d music %4d beats %3d' % (ex['name'], ex['dur'], len(ex['keys']), len(ex['music']), len(ex['beats'])))
            for line in diagnose(fr, 15):
                print(line)


def _py(v):
    if isinstance(v, list) and len(v) == 3 and isinstance(v[0], str):
        return (v[0], tuple(v[1]), tuple(v[2]))
    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], list):
        return (tuple(v[0]), tuple(v[1]))
    if isinstance(v, list):
        return tuple(v)
    return v


if __name__ == '__main__':
    main()
