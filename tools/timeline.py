"""Key-framed choreography evaluator (reference implementation of src/anim.js) + collision checks."""
import math
import numpy as np
from rig import (Rx, Rz, eul, M4, unit, mir, PIV, L1A, L2A, L1L, L2L, ik, arm_frames, leg_frames, fk, herm, bone_pt)

FIELDS = ['rp', 'yaw', 'pel', 'chs', 'head', 'abd', 'flap', 'bour', 'rip', 'spot', 'song', 'wag']


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def spot_rz(rel):
    if abs(rel) <= 75:
        return -rel
    f = (rel - 75) / 210.0 if rel > 75 else (rel + 360 - 75) / 210.0
    return -75 + 150 * f


class Timeline:
    def __init__(self, KD, jumps=(), defaults=None):
        self.TS = np.array(sorted(KD))
        self.HOLDS, self.STATES = [], []
        cur = dict(defaults or {})
        for t in self.TS:
            h, kw = KD[round(float(t), 4)]
            cur = dict(cur); cur.update(kw)
            self.STATES.append(cur); self.HOLDS.append(h)
        for k in ('song', 'wag'):
            for s in self.STATES:
                s.setdefault(k, 0.0)
        self.ARR = {}
        for fld in FIELDS:
            self.ARR[fld] = [np.atleast_1d(np.array(s[fld], float)) for s in self.STATES]
        self.ARR['wL'] = [np.array(s['wL'], float) for s in self.STATES]
        self.ARR['wR'] = [np.array([s['wR'][0], -s['wR'][1], -s['wR'][2]], float) for s in self.STATES]
        self.ARR['aLo'] = [np.array(s['aL'][0], float) for s in self.STATES]
        self.ARR['aLp'] = [unit(s['aL'][1]) for s in self.STATES]
        self.ARR['aRo'] = [mir(s['aR'][0]) for s in self.STATES]
        self.ARR['aRp'] = [mir(unit(s['aR'][1])) for s in self.STATES]
        self.jumps = list(jumps)
        self.dur = float(self.TS[-1])

    def ev(self, fld, t):
        return herm(self.TS, self.ARR[fld], t, self.HOLDS)

    def leg_target(self, spec, side, rp, yaw, Wpel_inv, Rpel_w, t, bour):
        mode, v, pole = spec
        v = np.array(v, float); pole = unit(pole)
        if side == 'R':
            v = mir(v); pole = mir(pole)
        if mode == 'floor':
            if bour > 0:
                ph = 2 * math.pi * 7 * t + (0 if side == 'L' else math.pi)
                v[1] += bour * 0.024 * math.sin(ph)
                v[2] += bour * 0.012 * max(0.0, math.sin(ph))
            wpt = np.array([rp[0], rp[1], 0.0]) + Rz(yaw) @ v
            loc = (Wpel_inv @ np.append(wpt, 1.0))[:3]
            pl = Rpel_w.T @ (Rz(yaw) @ pole)
        else:
            loc = (PIV['thigh' + side] - PIV['pelvis']) + v
            pl = pole
        return loc, pl

    def pose_at(self, t, cam_az=0.0):
        rp = self.ev('rp', t).copy(); yaw = float(self.ev('yaw', t)[0])
        bour = float(np.clip(self.ev('bour', t)[0], 0, 1)); rip = float(np.clip(self.ev('rip', t)[0], 0, 1))
        spot = float(np.clip(self.ev('spot', t)[0], 0, 1))
        for t0, t1, h in self.jumps:
            if t0 <= t <= t1:
                s = (t - t0) / (t1 - t0)
                rp[2] += h * 4 * s * (1 - s)
        rp[2] += bour * 0.004 * math.sin(2 * math.pi * 14 * t)
        loc = {}
        Wroot = M4(Rz(yaw), rp)
        loc['pelvis'] = eul(self.ev('pel', t))
        Wpel = Wroot @ M4(loc['pelvis'], PIV['pelvis'] - PIV['root'])
        Wpel_inv = np.linalg.inv(Wpel)
        loc['chest'] = eul(self.ev('chs', t))
        hd = self.ev('head', t).copy()
        if spot > 0:
            hd[2] = (1 - spot) * hd[2] + spot * spot_rz(wrap180(yaw + cam_az))
        loc['head'] = eul(hd)
        wag = float(np.clip(self.ev('wag', t)[0], 0, 1))
        loc['abdomen'] = eul(self.ev('abd', t)) @ Rz(wag * 22 * math.sin(2 * math.pi * 7 * t))
        wv = math.sin(2 * math.pi * 0.9 * t)
        for s in 'LR':
            off = self.ev('a%so' % s, t).copy(); pole = self.ev('a%sp' % s, t).copy()
            if rip > 0:
                off[2] += rip * 0.075 * wv
                pole[2] += rip * 0.7 * math.sin(2 * math.pi * 0.9 * t - 0.9)
            pole = unit(pole)
            S = PIV['upper' + s] - PIV['chest']
            d1, d2, b = ik(S, S + off, L1A, L2A, pole)
            loc['upper' + s], loc['fore' + s] = arm_frames(d1, d2, b, s)
            we = self.ev('w' + s, t).copy()
            if rip > 0:
                we[1] += rip * 28 * math.sin(2 * math.pi * 0.9 * t - 1.8) * (1 if s == 'L' else -1)
            loc['hand' + s] = eul(we)
            tg = [self.leg_target(st['l' + s], s, rp, yaw, Wpel_inv, Wpel[:3, :3], t, bour) for st in self.STATES]
            T_ = herm(self.TS, [a for a, _ in tg], t, self.HOLDS)
            P_ = unit(herm(self.TS, [b_ for _, b_ in tg], t, self.HOLDS))
            S = PIV['thigh' + s] - PIV['pelvis']
            d1, d2, b = ik(S, T_, L1L, L2L, P_)
            loc['thigh' + s], loc['shin' + s] = leg_frames(d1, d2, b)
        return rp, yaw, loc

    def frames(self, fps=30):
        out = []
        n = int(self.dur * fps) + 1
        for i in range(n):
            t = i / fps
            rp, yaw, loc = self.pose_at(t)
            out.append({'t': t, 'rp': rp, 'yaw': yaw, 'W': fk(rp, yaw, loc)})
        return out


def seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / (ab @ ab + 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def cap_dist(c1, c2, n=9):
    a, b, r1 = c1; c, d, r2 = c2
    P = a + np.linspace(0, 1, n)[:, None] * (b - a)
    return float(seg_dist(P, c, d).min()) - r1 - r2


def limb_caps(Wm):
    caps = {}
    for s, sg in (('L', 1), ('R', -1)):
        caps['gaunt' + s] = (bone_pt(Wm, 'fore' + s, (sg * 0.385, 0, 1.37)), bone_pt(Wm, 'fore' + s, (sg * 0.625, 0, 1.37)), 0.064)
        caps['hand' + s] = (bone_pt(Wm, 'hand' + s, (sg * 0.68, 0, 1.37)), bone_pt(Wm, 'hand' + s, (sg * 0.79, 0, 1.37)), 0.03)
        caps['thigh' + s] = (Wm['thigh' + s][:3, 3], Wm['shin' + s][:3, 3], 0.068)
        caps['shin' + s] = (Wm['shin' + s][:3, 3], bone_pt(Wm, 'shin' + s, (sg * 0.075, 0, 0.02)), 0.06)
    caps['torso'] = (bone_pt(Wm, 'chest', (0, 0, 1.21)), bone_pt(Wm, 'chest', (0, 0, 1.38)), 0.1)
    caps['pelvis'] = (bone_pt(Wm, 'pelvis', (0, 0, 0.97)), bone_pt(Wm, 'pelvis', (0, 0, 1.10)), 0.09)
    caps['head'] = (bone_pt(Wm, 'head', (0, 0, 1.57)), bone_pt(Wm, 'head', (0, 0, 1.63)), 0.16)
    return caps


def diagnose(frames, fps=30, thresh=-0.015):
    pairs = []
    for s in 'LR':
        o = 'R' if s == 'L' else 'L'
        for part in ('gaunt', 'hand'):
            for b in ('torso', 'pelvis', 'head', 'thighL', 'thighR', 'shinL', 'shinR', 'gaunt' + o, 'hand' + o):
                pairs.append((part + s, b))
    seen, uniq = set(), []
    for p in pairs:
        k = tuple(sorted(p))
        if k not in seen:
            seen.add(k); uniq.append(p)
    report = {}
    for fr in frames:
        caps = limb_caps(fr['W'])
        for a, b in uniq:
            d = cap_dist(caps[a], caps[b])
            if d < thresh:
                report.setdefault((a, b), []).append((fr['t'], d))
    lines = []
    for (a, b), lst in sorted(report.items(), key=lambda kv: kv[1][0][0]):
        ts = [x[0] for x in lst]; worst = min(x[1] for x in lst)
        lines.append('  %-7s x %-7s %6.2f-%6.2fs n=%3d worst %.3f' % (a, b, ts[0], ts[-1], len(ts), worst))
    return lines
