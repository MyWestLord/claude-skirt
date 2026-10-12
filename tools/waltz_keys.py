"""30-second choreography, secondary motion, skirt collision and diagnostics."""
import math
import numpy as np
from rig import (Rx, Ry, Rz, eul, M4, unit, mir, PIV, ORDER, L1A, L2A, L1L, L2L, ANT_TIP,
                 ik, arm_frames, leg_frames, fk, herm, bone_pt)
import geo

FPS, DUR = 30, 30.0
NF = int(FPS * DUR)
rng = np.random.default_rng(11)

# ---------------------------------------------------------------- vocabulary (left-side convention)
A_T = ((0.542, 0.0, 0.0), (0, 1, 0))
A_LOW = ((0.06, -0.41, -0.21), (1, 0.3, 0.1))
A_FIRST = ((0.045, -0.34, -0.12), (1, 0.2, 0.35))
A_FIFTH = ((0.025, -0.11, 0.49), (1, 0.25, 0.0))
A_SECOND = ((0.49, -0.16, -0.08), (0, 1, 0.4))
A_DEMI = ((0.42, -0.2, -0.27), (0, 1, 0.3))
A_FWD = ((0.03, -0.51, 0.13), (0.8, 0.2, 0.6))
A_SIDEB = ((0.48, 0.17, 0.05), (0, 1, 0.3))
A_V = ((0.33, -0.11, 0.41), (0.3, 1, 0.3))
A_V2 = ((0.34, -0.11, 0.43), (0.3, 1, 0.3))
A_JETE_B = ((0.45, 0.11, 0.22), (0, 1, 0.5))
A_BOW_UP = ((0.36, -0.25, 0.12), (0.3, 1, 0.3))

L_T = ('floor', (0.075, 0.0, 0.0), (0, -1, 0))
L_FIRST = ('floor', (0.045, -0.01, 0.0), (0.7, -0.7, 0))
L_BOUR = ('floor', (0.044, -0.005, 0.0), (0.6, -0.8, 0))
L_CH = ('floor', (0.04, -0.005, 0.0), (0.6, -0.8, 0))
L_SUP = ('floor', (0.0, 0.0, 0.0), (0.5, -0.85, 0))
L_PASSE = ('floor', (-0.045, -0.06, 0.56), (1, -0.3, 0.25))
L_BACK4 = ('floor', (0.06, 0.11, 0.0), (0.8, -0.6, 0))
L_FRONT4 = ('floor', (0.05, -0.10, 0.0), (0.8, -0.6, 0))
L_ARAB = ('hip', (0.02, 0.83, 0.38), (1, 0, 0))
L_JF = ('hip', (0.0, -0.84, -0.32), (0, -0.2, 1))
L_JB = ('hip', (0.0, 0.82, -0.30), (0, 0.2, -1))
L_TENDU = ('floor', (0.07, -0.36, 0.0), (0.6, -0.8, 0))
L_TSIDE = ('floor', (0.40, -0.02, 0.02), (0.2, -0.4, 1))
L_SEC45 = ('hip', (0.62, -0.06, -0.62), (0, -0.3, 1))
L_SUP2 = ('floor', (0.02, 0.04, 0.0), (0.6, -0.8, 0))

KD = {}


def key(t, hold=False, **kw):
    t = round(float(t), 4)
    if t in KD:
        h, d = KD[t]; d.update(kw); KD[t] = (h or hold, d)
    else:
        KD[t] = (hold, dict(kw))


JUMP = (14.45, 15.25, 0.36)

# ---- intro: exactly the screenshot T-pose, then she wakes up
key(0.0, True, rp=(0, 0, 1.0), yaw=0, pel=(0, 0, 0), chs=(0, 0, 0), head=(0, 0, 0), abd=(0, 0, 0), aL=A_T, aR=A_T,
    wL=(0, 0, 0), wR=(0, 0, 0), lL=L_T, lR=L_T, flap=(3, 1.0), bour=0, rip=0, spot=0)
key(1.0, True)
key(1.6, head=(-4, 5, -16), chs=(0, 0, -4), flap=(10, 2.5))
key(2.8, aL=A_LOW, aR=A_LOW, wL=(-30, 0, -20), wR=(-30, 0, -20), lL=L_FIRST, lR=L_FIRST, rp=(0, 0, 0.995),
    head=(10, 0, -6), chs=(4, 0, 0), flap=(5, 1.2))
key(3.3, rp=(0, 0, 0.955), head=(14, 0, 0), chs=(6, 0, 0))
key(3.75, aL=A_FIRST, aR=A_FIRST, rp=(0, 0, 0.995), head=(2, 0, 0), chs=(0, 0, 0), wL=(-60, 0, -15), wR=(-60, 0, -15))
key(4.3, aL=A_FIFTH, aR=A_FIFTH, chs=(-7, 0, 0), head=(-14, 0, 0), wL=(-80, 0, -20), wR=(-80, 0, -20),
    lL=L_BOUR, lR=L_BOUR, bour=1.0, rp=(0, 0, 0.99))
# ---- bourrée turn in place, arms bloom open
key(5.15, yaw=180, aL=A_V, aR=A_V, chs=(-4, 0, 0), head=(-6, 0, 0), wL=(20, 0, -10), wR=(20, 0, -10))
key(6.0, yaw=360, aL=A_SECOND, aR=A_SECOND, chs=(0, 0, 0), head=(0, 0, -8), wL=(0, 0, -10), wR=(0, 0, -10))
# ---- bourrée travelling on pointe across the grid, rippling swan arms
for t, x, y in ((6.0, 0.0, 0.0), (7.1, 0.55, -0.28), (8.2, 1.15, -0.34), (9.3, 1.62, -0.06), (10.3, 1.85, 0.3)):
    key(t, rp=(x, y, 0.99))
key(6.6, rip=1.0, yaw=368, head=(-2, 0, 10))
key(8.2, yaw=378, head=(-4, 0, -12))
key(9.8, rip=1.0, yaw=384, head=(0, 0, 8))
# ---- pirouette 2.7 turns -> arabesque facing -X
key(10.55, rp=(1.85, 0.3, 0.94), lL=L_BACK4, lR=L_FRONT4, bour=0, rip=0, aL=A_SECOND, aR=A_FIRST, wL=(0, 0, -10),
    wR=(-60, 0, -15), chs=(2, 0, 0), head=(0, 0, 10), yaw=384)
key(10.95, rp=(1.85, 0.3, 0.995), lL=L_PASSE, lR=L_SUP, aL=A_FIRST, aR=A_FIRST, wL=(-60, 0, -15), head=(0, 0, 0),
    chs=(0, 0, 0), flap=(16, 9), spot=1.0, yaw=392)
key(12.45, yaw=1350, spot=1.0)
key(13.15, aR=A_FWD, aL=A_SIDEB, lR=L_SUP, lL=L_ARAB, pel=(14, 0, 0), chs=(6, 0, 0), head=(-10, 0, 0),
    rp=(1.85, 0.3, 0.995), yaw=1356, abd=(12, 0, 42), wR=(0, 0, -5), wL=(0, 0, -8), flap=(6, 1.5), spot=0.0)
key(13.85, aR=((0.03, -0.50, 0.19), (0.8, 0.2, 0.6)), aL=((0.48, 0.19, 0.10), (0, 1, 0.3)), pel=(17, 0, 0),
    chs=(8, 0, 0), yaw=1352)
# ---- grand jeté towards -X
key(14.2, lL=('floor', (0.05, 0.12, 0), (0.8, -0.6, 0)), lR=('floor', (0.05, -0.10, 0), (0.8, -0.6, 0)),
    rp=(1.85, 0.3, 0.93), pel=(0, 0, 0), chs=(12, 0, 0), aL=A_LOW, aR=A_LOW, head=(4, 0, 0), yaw=1350,
    abd=(0, 0, 0), flap=(10, 4))
key(14.45, rp=(1.78, 0.3, 0.955), lL=('floor', (0.05, 0.2, 0), (0.8, -0.6, 0)), lR=('hip', (0, -0.5, -0.6), (0, -0.3, 1)),
    chs=(6, 0, 0), aR=A_FIRST, aL=A_FIRST, flap=(28, 14), abd=(8, 0, 30))
key(14.85, rp=(1.2, 0.3, 0.97), lR=L_JF, lL=L_JB, pel=(4, 0, 0), chs=(-6, 0, 0), head=(-12, 0, 0), aR=A_FWD,
    aL=A_JETE_B, abd=(10, 0, 40))
key(15.25, rp=(0.62, 0.3, 0.92), lR=('floor', (0, -0.03, 0), (0.6, -0.8, 0)), lL=('hip', (0, 0.62, -0.62), (0, 0.3, -1)),
    pel=(6, 0, 0), chs=(10, 0, 0), head=(0, 0, 0), aR=A_SECOND, aL=A_SECOND, flap=(10, 3), abd=(6, 0, 30))
# ---- chaînés: four fast turns travelling on pointe
key(15.6, rp=(0.5, 0.3, 0.995), lL=L_CH, lR=L_CH, pel=(0, 0, 0), chs=(0, 0, 0), aL=A_FIRST, aR=A_FIRST,
    abd=(0, 0, 0), yaw=1350, head=(0, 0, 0), flap=(14, 7), wL=(-60, 0, -15), wR=(-60, 0, -15), spot=1.0)
key(17.2, rp=(-0.95, 0.25, 0.995), yaw=2790, spot=1.0)
key(17.7, rp=(-0.95, 0.25, 0.97), yaw=2880, aL=A_SECOND, aR=A_SECOND, lL=L_TSIDE, lR=L_SUP, head=(-6, 0, -10),
    chs=(-4, 0, 0), spot=0.0, wL=(0, 0, -10), wR=(0, 0, -10), flap=(8, 2))
# ---- manège: four piqué turns running around a circle
C0, RAD = np.array([0.0, 0.35]), 0.95
for k in range(4):
    T = 18.0 + 0.85 * k
    Y = 2880 + 450 * k
    def onc(deg):
        a = math.radians(deg); p = C0 + RAD * np.array([math.cos(a), math.sin(a)]); return p
    p0, p1, p2 = onc(180 + 90 * k), onc(180 + 90 * k + 28), onc(180 + 90 * k + 70)
    key(T, rp=(p0[0], p0[1], 0.95), yaw=Y, lL=L_BACK4, lR=L_FRONT4, aL=A_SECOND, aR=A_SECOND, wL=(0, 0, -10),
        wR=(0, 0, -10), spot=0.0 if k == 0 else 0.7, chs=(3, 0, 0), flap=(12, 6))
    key(T + 0.2, rp=(p1[0], p1[1], 0.995), yaw=Y + 60, lL=L_PASSE, lR=L_SUP, aL=A_FIRST, aR=A_FIRST,
        wL=(-60, 0, -15), wR=(-60, 0, -15), spot=0.7, chs=(0, 0, 0))
    key(T + 0.6, rp=(p2[0], p2[1], 0.995), yaw=Y + 330)
key(21.4, rp=(-0.95, 0.35, 0.95), yaw=4680, lL=L_BACK4, lR=L_FRONT4, aL=A_SECOND, aR=A_FIRST, chs=(2, 0, 0),
    wL=(0, 0, -10), wR=(-60, 0, -15), spot=0.0, head=(0, 0, 0))
key(21.65, rp=(-0.62, 0.3, 0.99), lL=L_BOUR, lR=L_BOUR, aL=A_SECOND, aR=A_SECOND, wR=(0, 0, -10))
# ---- fouettés: 7 singles + a double, sparkles flying
for k in range(8):
    T = 21.9 + 0.5 * k
    Y = 4680 + 360 * k
    key(T, rp=(-0.3, 0.25, 0.93), yaw=Y, lL=L_SEC45, lR=L_SUP, aL=A_SECOND, aR=A_SECOND, wL=(0, 0, -10),
        wR=(0, 0, -10), spot=1.0, flap=(18, 9), chs=(0, 0, 0))
    key(T + 0.2, rp=(-0.3, 0.25, 0.995), yaw=Y + (100 if k < 7 else 180), lL=L_PASSE, aL=A_FIRST, aR=A_FIRST,
        wL=(-60, 0, -15), wR=(-60, 0, -15))
key(25.95, rp=(-0.3, 0.25, 0.99), yaw=7905, lL=L_PASSE, lR=L_SUP, spot=0.6)
# ---- finale: she pops a "CLAUDE SKIRT" banner into her paws, curtsies, holds it high
key(26.45, rp=(-0.3, 0.25, 0.985), lL=L_TENDU, lR=L_SUP2, aL=A_V, aR=A_V, chs=(-9, 0, 0), head=(-16, 0, -12),
    yaw=7905, wL=(30, 0, -10), wR=(30, 0, -10), flap=(10, 2), spot=0.0)
key(27.1, chs=(-10, 0, 0), aL=A_V2, aR=A_V2, head=(-14, 0, -16))
key(27.9, rp=(-0.3, 0.25, 0.935), chs=(8, 0, 0), head=(6, 12, -10), lL=('floor', (0.08, 0.16, 0), (0.8, -0.6, 0)),
    lR=('floor', (0.0, -0.02, 0), (0.6, -0.8, 0)), aL=A_V2, aR=A_V2)
key(28.7, rp=(-0.3, 0.25, 0.99), chs=(-10, 0, 0), head=(-16, 0, -12), aL=A_V2, aR=A_V2, lL=L_TENDU, lR=L_SUP2)
key(30.0, True, chs=(-11, 0, 0))

BANNER_T0 = 26.4


def banner_scale(t):
    x = (t - BANNER_T0) / 0.32
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    y = x - 1
    return 1 + 2.70158 * y ** 3 + 1.70158 * y ** 2


def banner_frame(Wm):
    """Centre, right-axis (viewer left->right), up-axis, normal of the banner held between the paws."""
    pl = bone_pt(Wm, 'handL', (0.708, 0, 1.37)); pr = bone_pt(Wm, 'handR', (-0.708, 0, 1.37))
    X = unit(pl - pr)
    up0 = Wm['chest'][:3, :3] @ np.array([0, 0, 1.0])
    U = unit(up0 - (up0 @ X) * X)
    N = np.cross(X, U)
    width = float(np.linalg.norm(pl - pr)) + 0.07
    return (pl + pr) / 2 + U * 0.09, X, U, N, width


TS = np.array(sorted(KD))
HOLDS, STATES = [], []
_cur = {}
for _t in TS:
    h, kw = KD[round(float(_t), 4)]
    _cur = dict(_cur); _cur.update(kw)
    STATES.append(_cur); HOLDS.append(h)

ARR = {}
for fld in ['rp', 'yaw', 'pel', 'chs', 'head', 'abd', 'flap', 'bour', 'rip', 'spot']:
    ARR[fld] = [np.atleast_1d(np.array(s[fld], float)) for s in STATES]
ARR['wL'] = [np.array(s['wL'], float) for s in STATES]
ARR['wR'] = [np.array([s['wR'][0], -s['wR'][1], -s['wR'][2]], float) for s in STATES]
ARR['aLo'] = [np.array(s['aL'][0], float) for s in STATES]
ARR['aLp'] = [unit(s['aL'][1]) for s in STATES]
ARR['aRo'] = [mir(s['aR'][0]) for s in STATES]
ARR['aRp'] = [mir(unit(s['aR'][1])) for s in STATES]


def ev(fld, t):
    return herm(TS, ARR[fld], t, HOLDS)

# ---------------------------------------------------------------- camera
#        t    az  el  dist  tz  follow fx   fy  hold
CAM = [(0.0, 25, 3, 4.3, 1.03, 1, 0, 0, 1), (1.0, 25, 3, 4.3, 1.03, 1, 0, 0, 1),
       (3.0, 14, 6, 4.3, 1.05, 1, 0, 0, 0), (6.0, -4, 8, 4.9, 1.0, 1, 0, 0, 0), (8.5, 6, 9, 5.2, 1.0, 1, 0, 0, 0),
       (10.5, 10, 5, 4.5, 1.02, 1, 0, 0, 0), (12.4, 18, 2, 4.0, 1.05, 1, 0, 0, 0), (13.9, 2, 4, 4.3, 1.02, 1, 0, 0, 0),
       (15.3, -12, 6, 5.0, 1.02, 1, 0, 0, 0), (17.3, -24, 8, 5.2, 1.02, 1, 0, 0, 0),
       (18.6, -5, 10, 5.6, 1.0, 0.3, 0, 0.35, 0), (20.4, 20, 11, 5.8, 1.0, 0.3, 0, 0.35, 0),
       (21.8, 24, 6, 4.6, 1.04, 1, 0, 0, 0), (24.0, 55, 1, 4.0, 1.06, 1, 0, 0, 0), (25.95, 32, 4, 4.2, 1.08, 1, 0, 0, 0),
       (27.3, 22, 5, 4.7, 1.25, 1, 0, 0, 0), (28.5, 18, 6, 4.9, 1.3, 1, 0, 0, 0), (30.0, 14, 7, 4.8, 1.3, 1, 0, 0, 1)]
CT = np.array([c[0] for c in CAM]); CV = [np.array(c[1:8], float) for c in CAM]; CH = [bool(c[8]) for c in CAM]


def cam_params(t):
    return herm(CT, CV, t, CH, tension=0.8)


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def spot_rz(rel):
    if abs(rel) <= 75:
        return -rel
    f = (rel - 75) / 210.0 if rel > 75 else (rel + 360 - 75) / 210.0
    return -75 + 150 * f

# ---------------------------------------------------------------- pose evaluation
def leg_target(spec, side, rp, yaw, Wpel_inv, Rpel_w, t, bour):
    mode, v, pole = spec
    v = np.array(v, float); pole = unit(pole)
    if side == 'R':
        v = mir(v); pole = mir(pole)
    if mode == 'floor':
        if bour > 0:
            v[1] += bour * 0.024 * math.sin(2 * math.pi * 7 * t + (0 if side == 'L' else math.pi))
            v[2] += bour * 0.012 * max(0.0, math.sin(2 * math.pi * 7 * t + (0 if side == 'L' else math.pi)))
        wpt = np.array([rp[0], rp[1], 0.0]) + Rz(yaw) @ v
        loc = (Wpel_inv @ np.append(wpt, 1.0))[:3]
        pl = Rpel_w.T @ (Rz(yaw) @ pole)
    else:
        loc = (PIV['thigh' + side] - PIV['pelvis']) + v
        pl = pole
    return loc, pl


def pose_at(t):
    rp = ev('rp', t).copy(); yaw = float(ev('yaw', t)[0])
    bour = float(np.clip(ev('bour', t)[0], 0, 1)); rip = float(np.clip(ev('rip', t)[0], 0, 1))
    spot = float(np.clip(ev('spot', t)[0], 0, 1))
    if JUMP[0] <= t <= JUMP[1]:
        s = (t - JUMP[0]) / (JUMP[1] - JUMP[0])
        rp[2] += JUMP[2] * 4 * s * (1 - s)
    rp[2] += bour * 0.004 * math.sin(2 * math.pi * 14 * t)
    loc = {}
    Wroot = M4(Rz(yaw), rp)
    loc['pelvis'] = eul(ev('pel', t))
    Wpel = Wroot @ M4(loc['pelvis'], PIV['pelvis'] - PIV['root'])
    Wpel_inv = np.linalg.inv(Wpel)
    loc['chest'] = eul(ev('chs', t))
    hd = ev('head', t).copy()
    if spot > 0:
        az = cam_params(t)[0]
        hd[2] = (1 - spot) * hd[2] + spot * spot_rz(wrap180(yaw - (-az)))
    loc['head'] = eul(hd)
    loc['abdomen'] = eul(ev('abd', t))
    wv = math.sin(2 * math.pi * 0.9 * t)
    for s in 'LR':
        off = ev('a%so' % s, t).copy(); pole = ev('a%sp' % s, t).copy()
        if rip > 0:
            off[2] += rip * 0.075 * wv
            pole[2] += rip * 0.7 * math.sin(2 * math.pi * 0.9 * t - 0.9)
        pole = unit(pole)
        S = PIV['upper' + s] - PIV['chest']
        d1, d2, b = ik(S, S + off, L1A, L2A, pole)
        loc['upper' + s], loc['fore' + s] = arm_frames(d1, d2, b, s)
        we = ev('w' + s, t).copy()
        if rip > 0:
            we[1] += rip * 28 * math.sin(2 * math.pi * 0.9 * t - 1.8) * (1 if s == 'L' else -1)
        loc['hand' + s] = eul(we)
        tg = [leg_target(st['l' + s], s, rp, yaw, Wpel_inv, Wpel[:3, :3], t, bour) for st in STATES]
        T_ = herm(TS, [a for a, _ in tg], t, HOLDS)
        P_ = unit(herm(TS, [b_ for _, b_ in tg], t, HOLDS))
        S = PIV['thigh' + s] - PIV['pelvis']
        d1, d2, b = ik(S, T_, L1L, L2L, P_)
        loc['thigh' + s], loc['shin' + s] = leg_frames(d1, d2, b)
    return rp, yaw, loc


def simulate():
    frames = []
    for fi in range(NF):
        t = fi / FPS
        rp, yaw, loc = pose_at(t)
        frames.append({'t': t, 'rp': rp, 'yaw': yaw, 'loc': loc, 'flap': ev('flap', t)})
    dt = 1.0 / FPS
    ph = 0.0
    for fr in frames:
        amp, fq = fr['flap']
        ph += 2 * math.pi * fq * dt
        fr['wing'] = (amp * math.sin(ph), 0.8 * amp * math.sin(ph - 0.7))
    yaws = np.array([f['yaw'] for f in frames]); zs = np.array([f['rp'][2] for f in frames])
    om = np.gradient(yaws, dt); vz = np.gradient(zs, dt)
    xy = np.array([f['rp'][:2] for f in frames]); vxy = np.gradient(xy, dt, axis=0)
    fl = flv = sw = swv = 0.0
    w1, z1 = 2 * math.pi * 2.3, 0.33
    w2, z2 = 2 * math.pi * 2.0, 0.5
    for i, fr in enumerate(frames):
        spin = min(abs(om[i]) / 950.0, 1.0)
        speed = float(np.linalg.norm(vxy[i]))
        tgt = spin ** 0.8 + float(np.clip(-vz[i] * 0.45, -0.35, 0.6)) + min(speed * 0.25, 0.3)
        stgt = -math.copysign(1, om[i]) * 0.5 * spin if abs(om[i]) > 1 else 0.0
        for _ in range(4):
            h = dt / 4
            flv += (w1 * w1 * (tgt - fl) - 2 * z1 * w1 * flv) * h; fl += flv * h
            swv += (w2 * w2 * (stgt - sw) - 2 * z2 * w2 * swv) * h; sw += swv * h
        fr['flare'] = float(np.clip(fl, -0.45, 1.15)); fr['swirl'] = sw
        fr['flutter'] = 0.35 + 0.9 * spin + 0.6 * min(abs(vz[i]), 1.0) + 0.5 * min(speed, 1.0)
        fr['omega'] = om[i]
        wig = float(np.clip(3.5 * math.sin(2 * math.pi * 0.55 * fr['t']) - 10 * vz[i], -14, 14))
        fr['loc']['abdomen'] = fr['loc']['abdomen'] @ Rx(wig)
        a1, a2 = fr['wing']
        for s, sg in (('L', 1), ('R', -1)):
            fr['loc']['wing1' + s] = Rz(sg * a1)
            fr['loc']['wing2' + s] = Rz(sg * a2)
    for side, ph0 in (('antL', 0.0), ('antR', 1.7)):
        x = v = None
        wn, zt = 2 * math.pi * 2.6, 0.17
        for fr in frames:
            t = fr['t']
            idle = eul((3 * math.sin(2 * math.pi * 0.7 * t + ph0), 0, 4 * math.sin(2 * math.pi * 0.45 * t + ph0)))
            loc = dict(fr['loc']); loc[side] = idle
            Wm = fk(fr['rp'], fr['yaw'], loc)
            base = Wm['head'][:3, :3] @ (PIV[side] - PIV['head']) + Wm['head'][:3, 3]
            rest_tip = bone_pt(Wm, side, ANT_TIP[side])
            if x is None:
                x, v = rest_tip.copy(), np.zeros(3)
            for _ in range(8):
                h = 1.0 / FPS / 8
                a = wn * wn * (rest_tip - x) - 2 * zt * wn * v
                v = v + a * h; x = x + v * h
            r0 = unit(rest_tip - base); r1 = unit(x - base)
            ax = np.cross(r0, r1); sn = np.linalg.norm(ax); ang = min(math.atan2(sn, float(r0 @ r1)), math.radians(50))
            Rd = geo.axis_angle(ax, ang) if sn > 1e-8 else np.eye(3)
            Hr = Wm['head'][:3, :3]
            fr['loc'][side] = Hr.T @ Rd @ Hr @ idle
    for fr in frames:
        fr['W'] = fk(fr['rp'], fr['yaw'], fr['loc'])
    # camera target follows the dancer smoothly
    tgt = np.array([0.0, 0.0])
    for fr in frames:
        a = 1 - math.exp(-dt / 0.38)
        tgt = tgt + (fr['rp'][:2] - tgt) * a
        fr['camxy'] = tgt.copy()
    return frames

# ---------------------------------------------------------------- collisions
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
        caps['upper' + s] = (bone_pt(Wm, 'upper' + s, (sg * 0.15, 0, 1.37)), bone_pt(Wm, 'upper' + s, (sg * 0.35, 0, 1.37)), 0.022)
        caps['gaunt' + s] = (bone_pt(Wm, 'fore' + s, (sg * 0.385, 0, 1.37)), bone_pt(Wm, 'fore' + s, (sg * 0.625, 0, 1.37)), 0.064)
        caps['hand' + s] = (bone_pt(Wm, 'hand' + s, (sg * 0.68, 0, 1.37)), bone_pt(Wm, 'hand' + s, (sg * 0.79, 0, 1.37)), 0.03)
        caps['thigh' + s] = (Wm['thigh' + s][:3, 3], Wm['shin' + s][:3, 3], 0.068)
        caps['shin' + s] = (Wm['shin' + s][:3, 3], bone_pt(Wm, 'shin' + s, (sg * 0.075, 0, 0.02)), 0.06)
    return caps


def body_caps(Wm):
    return {'torso': (bone_pt(Wm, 'chest', (0, 0, 1.21)), bone_pt(Wm, 'chest', (0, 0, 1.38)), 0.1),
            'pelvis': (bone_pt(Wm, 'pelvis', (0, 0, 0.97)), bone_pt(Wm, 'pelvis', (0, 0, 1.10)), 0.09),
            'head': (bone_pt(Wm, 'head', (0, 0, 1.57)), bone_pt(Wm, 'head', (0, 0, 1.63)), 0.16),
            'abdomen': (bone_pt(Wm, 'abdomen', (0, 0.1, 0.975)), bone_pt(Wm, 'abdomen', (0, 0.2, 0.935)), 0.095)}


def diagnose(frames):
    pairs = []
    for s in 'LR':
        o = 'R' if s == 'L' else 'L'
        for part in ('gaunt', 'hand'):
            for b in ('torso', 'pelvis', 'head', 'abdomen'):
                pairs.append((part + s, b))
            for lp in ('thigh', 'shin'):
                pairs.append((part + s, lp + 'L')); pairs.append((part + s, lp + 'R'))
            pairs.append((part + s, 'gaunt' + o)); pairs.append((part + s, 'hand' + o))
        for lp in ('thigh', 'shin'):
            pairs.append((lp + s, 'abdomen'))
    pairs.append(('shinL', 'shinR')); pairs.append(('thighL', 'shinR')); pairs.append(('shinL', 'thighR'))
    seen = set(); uniq = []
    for p in pairs:
        k = tuple(sorted(p))
        if k not in seen:
            seen.add(k); uniq.append(p)
    report = {}
    for fi, fr in enumerate(frames):
        caps = limb_caps(fr['W']); caps.update(body_caps(fr['W']))
        for a, b in uniq:
            d = cap_dist(caps[a], caps[b])
            if d < -0.012:
                report.setdefault((a, b), []).append((fi / FPS, d))
    for (a, b), lst in sorted(report.items(), key=lambda kv: kv[1][0][0]):
        ts = [x[0] for x in lst]; worst = min(x[1] for x in lst)
        print('  %-8s x %-8s  %5.2f-%5.2fs  n=%3d  worst %.3f' % (a, b, ts[0], ts[-1], len(ts), worst))
    return report


def skirt_lifts(frames, skirt):
    n = skirt.n
    cands = np.radians([0, 7, 14, 22, 31, 41, 53, 66, 80])
    prev = np.zeros(n)
    k = np.exp(-0.5 * (np.arange(-30, 31) / 9.0) ** 2); k /= k.sum()
    for fr in frames:
        Wm = fr['W']
        Pinv = np.linalg.inv(Wm['pelvis'])
        conv = lambda w: (Pinv @ np.append(w, 1.0))[:3] + PIV['pelvis']
        caps = []
        for nm, (a, b, r) in limb_caps(Wm).items():
            if nm.startswith('upper'):
                continue
            caps.append((conv(a), conv(b), r + (0.012 if nm.startswith(('thigh', 'shin')) else 0.008)))
        need = np.full(n, cands[-1]); found = np.zeros(n, bool)
        for c in cands:
            top, _, _ = skirt.surface(fr['flare'], fr['swirl'], fr['t'], fr['flutter'], lift=np.full(n, c))
            pts = top[:, 3:, :].reshape(-1, 3)
            clear = np.full(len(pts), 9.0)
            for a, b, r in caps:
                clear = np.minimum(clear, seg_dist(pts, a, b) - r)
            ok = clear.reshape(n, -1).min(1) >= 0
            newly = ok & ~found; need[newly] = c; found |= ok
            if found.all():
                break
        ext = np.concatenate([need[-30:], need, need[:30]])
        sm = np.convolve(ext, k, mode='same')[30:-30]
        lift = np.maximum(need, sm * 1.15)
        lift = np.maximum(lift, prev - math.radians(5))
        prev = lift
        fr['lift'] = lift


def simulate_particles(frames, skirt):
    P = np.zeros((0, 3)); V = np.zeros((0, 3)); life = np.zeros(0); life0 = np.zeros(0)
    size = np.zeros(0); hue = np.zeros(0); pha = np.zeros(0)
    dt = 1.0 / FPS
    out = []
    windows = ((10.95, 12.45, 80), (14.45, 15.2, 60), (15.6, 17.2, 55), (18.0, 21.4, 60), (21.9, 25.95, 170), (26.6, 30, 28))
    bursts = (26.0,)
    for fr in frames:
        t = fr['t']
        top, _, _ = skirt.surface(fr['flare'], fr['swirl'], t, fr['flutter'], fr['lift'])
        tips = top[skirt.peaks, -1]
        Wp = fr['W']['pelvis']
        tipsw = (tips - PIV['pelvis']) @ Wp[:3, :3].T + Wp[:3, 3]
        rate = sum(r for a, b, r in windows if a <= t <= b)
        n = rng.poisson(rate * dt)
        burst = any(abs(t - b) < dt / 2 for b in bursts)
        if burst:
            n += 230
        if abs(t - (BANNER_T0 + 0.12)) < dt / 2:
            bc = banner_frame(fr['W'])[0]
            m = 260
            dirs = rng.normal(0, 1, (m, 3)); dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
            P = np.vstack([P, bc + dirs * rng.uniform(0.0, 0.25, (m, 1))])
            V = np.vstack([V, dirs * rng.uniform(0.6, 1.9, (m, 1)) + np.array([0, 0, 0.4])])
            l = rng.uniform(0.8, 1.8, m)
            life = np.concatenate([life, l]); life0 = np.concatenate([life0, l])
            size = np.concatenate([size, rng.uniform(0.02, 0.045, m)])
            hue = np.concatenate([hue, rng.uniform(0, 1, m)])
            pha = np.concatenate([pha, rng.uniform(0, 6.28, m)])
        if n:
            idx = rng.integers(0, len(tipsw), n)
            p = tipsw[idx] + rng.normal(0, 0.01, (n, 3))
            c = np.array([fr['rp'][0], fr['rp'][1], p[:, 2].mean()])
            rad = p - c; rad[:, 2] = 0; rad = rad / np.maximum(np.linalg.norm(rad, axis=1, keepdims=True), 1e-6)
            om = math.radians(fr['omega'])
            tan = np.cross(np.array([0, 0, om]), p - c) * 0.7
            out_s = rng.uniform(0.6, 1.8, (n, 1)) if burst else rng.uniform(0.15, 0.55, (n, 1))
            up = rng.uniform(0.4, 1.6, (n, 1)) if burst else rng.uniform(0.05, 0.7, (n, 1))
            v = tan + rad * out_s + np.array([0, 0, 1.0]) * up + rng.normal(0, 0.12, (n, 3))
            P = np.vstack([P, p]); V = np.vstack([V, v])
            l = rng.uniform(0.7, 1.6, n)
            life = np.concatenate([life, l]); life0 = np.concatenate([life0, l])
            size = np.concatenate([size, rng.uniform(0.018, 0.042, n)])
            hue = np.concatenate([hue, rng.uniform(0, 1, n)])
            pha = np.concatenate([pha, rng.uniform(0, 6.28, n)])
        if len(P):
            V *= math.exp(-0.9 * dt); V[:, 2] -= 0.9 * dt; P = P + V * dt; life = life - dt
            under = P[:, 2] < 0.01
            P[under, 2] = 0.01; V[under, 2] *= -0.3
            keep = life > 0
            P, V, life, life0, size, hue, pha = P[keep], V[keep], life[keep], life0[keep], size[keep], hue[keep], pha[keep]
        if len(P):
            kk = life / life0
            a = np.clip(kk * 1.3, 0, 1) * (0.65 + 0.35 * np.sin(t * 22 + pha))
            col = np.stack([np.ones_like(hue), 0.55 + 0.4 * hue, 0.32 + 0.55 * hue], 1)
            data = np.hstack([P, col, a[:, None], (size * (0.5 + 0.5 * kk))[:, None]])
        else:
            data = np.zeros((0, 8))
        out.append(data.astype(np.float32))
    return out
