"""Procedural geometry for the bee-ballerina (rest T-pose, Z up, facing -Y, +X = her left)."""
import math
import re
import numpy as np
from PIL import Image


def nrm(v):
    l = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(l, 1e-12)


def tri_grid(nu, nv, wu, wv):
    iu = nu if wu else nu - 1
    jv = nv if wv else nv - 1
    ii, jj = np.meshgrid(np.arange(iu), np.arange(jv), indexing='ij')
    a = ii * nv + jj
    b = ((ii + 1) % nu) * nv + jj
    c = ((ii + 1) % nu) * nv + (jj + 1) % nv
    d = ii * nv + (jj + 1) % nv
    return np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3),
                           np.stack([a, c, d], -1).reshape(-1, 3)]).astype(np.int64)


def vnormals(P, T):
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    N = np.zeros_like(P)
    n = len(P)
    for k in range(3):
        for c in range(3):
            N[:, c] += np.bincount(T[:, k], weights=fn[:, c], minlength=n)
    return nrm(N)


def mesh_grid(G, wu, wv, poles=()):
    nu, nv = G.shape[:2]
    P = G.reshape(-1, 3).astype(np.float64)
    T = tri_grid(nu, nv, wu, wv)
    N = vnormals(P, T)
    for row, normal in poles:
        N[row * nv:(row + 1) * nv] = normal
    return [P, N, T]


def skew(v):
    return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])


def rot_to(axis):
    a = nrm(np.asarray(axis, float))
    z = np.array([0, 0, 1.0])
    v = np.cross(z, a)
    s = np.linalg.norm(v)
    c = z @ a
    if s < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    K = skew(v / s)
    th = math.atan2(s, c)
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K


def axis_angle(axis, ang):
    a = nrm(np.asarray(axis, float))
    K = skew(a)
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def orient(m, R, t=(0, 0, 0)):
    P, N, T = m
    return [P @ R.T + np.asarray(t, float), N @ R.T, T]


def mirror(m):
    P, N, T = m
    s = np.array([-1.0, 1, 1])
    return [P * s, N * s, T[:, ::-1].copy()]


def merge(ms):
    Ps, Ns, Ts, off = [], [], [], 0
    for P, N, T in ms:
        Ps.append(P); Ns.append(N); Ts.append(T + off); off += len(P)
    return [np.vstack(Ps), np.vstack(Ns), np.vstack(Ts)]


def chaikin(pts, it=2):
    P = np.asarray(pts, float)
    for _ in range(it):
        Q = [P[0]]
        for a, b in zip(P[:-1], P[1:]):
            Q.append(0.75 * a + 0.25 * b)
            Q.append(0.25 * a + 0.75 * b)
        Q.append(P[-1])
        P = np.array(Q)
    return P


def lathe(prof, n=40, axis=(0, 0, 1), origin=(0, 0, 0)):
    prof = np.asarray(prof, float)
    r, z = prof[:, 0], prof[:, 1]
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    G = np.stack([r[:, None] * np.cos(th)[None], r[:, None] * np.sin(th)[None],
                  np.repeat(z[:, None], n, 1)], -1)
    poles = []
    if r[0] < 1e-9:
        poles.append((0, np.array([0, 0, -1.0])))
    if r[-1] < 1e-9:
        poles.append((len(r) - 1, np.array([0, 0, 1.0])))
    m = mesh_grid(G, False, True, poles)
    return orient(m, rot_to(axis), origin)


def sellip(a, b, c, e=0.5, center=(0, 0, 0), nu=34, nv=56):
    phi = np.linspace(-np.pi / 2, np.pi / 2, nu)
    th = np.linspace(-np.pi, np.pi, nv, endpoint=False)
    PH, TH = np.meshgrid(phi, th, indexing='ij')
    f = lambda w: np.sign(w) * np.abs(w) ** e
    cp = np.cos(PH); cp[0] = 0; cp[-1] = 0
    G = np.stack([a * f(cp) * f(np.cos(TH)), b * f(cp) * f(np.sin(TH)), c * f(np.sin(PH))], -1)
    G = G + np.asarray(center, float)
    return mesh_grid(G, False, True, [(0, np.array([0, 0, -1.0])), (nu - 1, np.array([0, 0, 1.0]))])


def sphere(r, center):
    return sellip(r, r, r, 1.0, center, nu=18, nv=28)


def torus(R, r, center=(0, 0, 0), axis=(0, 0, 1), nu=56, nv=14):
    U, V = np.meshgrid(np.linspace(0, 2 * np.pi, nu, endpoint=False),
                       np.linspace(0, 2 * np.pi, nv, endpoint=False), indexing='ij')
    G = np.stack([(R + r * np.cos(V)) * np.cos(U), (R + r * np.cos(V)) * np.sin(U), r * np.sin(V)], -1)
    return orient(mesh_grid(G, True, True), rot_to(axis), center)


def loft(rows, n=56, p=2.6, crease=0.0):
    """rows: (z, hx, hy, yc) superellipse cross sections, ends with hx=0 close the shape."""
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    fx = np.sign(c) * np.abs(c) ** (2 / p)
    fy = np.sign(s) * np.abs(s) ** (2 / p)
    if crease:
        d = np.angle(np.exp(1j * (th + np.pi / 2)))
        k = 1 - crease * np.exp(-(d / 0.07) ** 2)
    else:
        k = np.ones(n)
    G = np.zeros((len(rows), n, 3))
    poles = []
    for r, (z, hx, hy, yc) in enumerate(rows):
        G[r, :, 0] = hx * fx * k
        G[r, :, 1] = yc + hy * fy * k
        G[r, :, 2] = z
        if hx < 1e-9:
            poles.append((r, np.array([0, 0, -1.0 if r == 0 else 1.0])))
    return mesh_grid(G, False, True, poles)


def sweep(Cp, ra, rb=None, closed=False, nseg=14, fixedB=None):
    Cp = np.asarray(Cp, float)
    n = len(Cp)
    ra = np.broadcast_to(np.asarray(ra, float), (n,))
    rb = ra if rb is None else np.broadcast_to(np.asarray(rb, float), (n,))
    if closed:
        T = np.roll(Cp, -1, 0) - np.roll(Cp, 1, 0)
    else:
        T = np.gradient(Cp, axis=0)
    T = nrm(T)
    if fixedB is not None:
        fb = np.asarray(fixedB, float)
        B = nrm(fb[None] - (T @ fb)[:, None] * T)
        N = np.cross(B, T)
    else:
        N = np.zeros_like(Cp)
        a = np.array([0, 0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([1.0, 0, 0])
        N[0] = nrm(np.cross(T[0], a))
        for k in range(1, n):
            v = N[k - 1] - (N[k - 1] @ T[k]) * T[k]
            N[k] = nrm(v)
        B = np.cross(T, N)
    ang = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    G = (Cp[:, None, :] + N[:, None, :] * (ra[:, None, None] * np.cos(ang)[None, :, None])
         + B[:, None, :] * (rb[:, None, None] * np.sin(ang)[None, :, None]))
    m = mesh_grid(G, closed, True)
    if not closed:
        nv = nseg
        if ra[0] < 1e-6:
            m[1][0:nv] = -T[0]
        if ra[-1] < 1e-6:
            m[1][(n - 1) * nv:] = T[-1]
    return m


def fan(outline, center):
    P = np.vstack([np.asarray(center, float)[None], np.asarray(outline, float)])
    n = len(outline)
    T = np.array([[0, 1 + k, 1 + (k + 1) % n] for k in range(n)], np.int64)
    return [P, vnormals(P, T), T]


def tube_tip(pts, r0, r1, tip=True, base=True):
    """Open tube along pts with rounded ends (radius tapers to zero at both ends)."""
    pts = np.asarray(pts, float)
    n = len(pts)
    r = list(np.linspace(r0, r1, n))
    P = list(pts)
    if base:
        d0 = nrm(pts[0] - pts[1])
        P = [pts[0] + d0 * r0 * 0.9, pts[0] + d0 * r0 * 0.6] + P
        r = [0.0, r0 * 0.8] + r
    if tip:
        d1 = nrm(pts[-1] - pts[-2])
        P = P + [pts[-1] + d1 * r1 * 0.6, pts[-1] + d1 * r1 * 0.9]
        r = r + [r1 * 0.8, 0.0]
    return sweep(np.array(P), np.array(r), nseg=10)


def bezier(p0, p1, p2, p3, n=24):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(lambda p: np.asarray(p, float), (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


# ---------------------------------------------------------------- model
GREY = (0.80, 0.80, 0.80)
WINGC = (0.86, 0.87, 0.88)
ORANGE = (0.87, 0.24, 0.125)

HC = np.array([0, 0, 1.60]); HA, HB, HCZ, HE = 0.175, 0.150, 0.140, 0.5


def shell_front_y(x, z):
    q = 1 - np.abs(x / HA) ** (2 / HE) - np.abs(z / HCZ) ** (2 / HE)
    return -HB * np.clip(q, 0, 1) ** (HE / 2)


def build_parts():
    """Returns list of (bone, mesh, color, spec, group)."""
    parts = []

    def add(bone, m, col=GREY, spec=0.16):
        parts.append((bone, m, col, spec))

    def both(bone, m, col=GREY, spec=0.16):
        add(bone + 'L', m, col, spec)
        add(bone + 'R', mirror(m), col, spec)

    # ---- head
    add('head', sellip(HA, HB, HCZ, HE, center=HC, nu=40, nv=72))
    th = np.linspace(0, 2 * np.pi, 140, endpoint=False)
    sq = lambda w, p: np.sign(w) * np.abs(w) ** (2 / p)
    fx, fz = sq(np.cos(th), 4.5), sq(np.sin(th), 4.5)
    px, pz = 0.128 * fx, 0.112 * fz
    py = shell_front_y(px, pz) - 0.012
    add('head', sweep(np.stack([px, py, pz + HC[2]], -1), ra=0.021, rb=0.030, closed=True, nseg=14, fixedB=(0, 1, 0)))
    scr = np.stack([0.128 * fx, np.full_like(fx, -0.152), 0.112 * fz + HC[2]], -1)
    add('head', fan(scr, (0, -0.152, HC[2])), (0.74, 0.75, 0.76), 0.25)
    ear = chaikin([(0, 0), (0.068, 0), (0.071, 0.012), (0.066, 0.026), (0.053, 0.030), (0.049, 0.034),
                   (0.049, 0.043), (0.038, 0.048), (0.026, 0.049), (0.021, 0.053), (0, 0.054)], 2)
    both('head_', lathe(ear, 40, axis=(1, 0, 0), origin=(0.166, -0.005, 1.605)))
    add('head', lathe(chaikin([(0, 1.425), (0.031, 1.425), (0.031, 1.478), (0, 1.478)], 1), 24))
    # antennae: sockets + stalks + leaves
    for side, base, ctrl, leaf_dir in (
            ('antR', (-0.065, 0.0, 1.725), [(-0.075, 0.0, 1.81), (-0.058, 0.0, 1.89), (-0.068, 0.0, 1.955)], (-0.08, 0.0, 1.0)),
            ('antL', (0.065, 0.0, 1.725), [(0.07, 0.0, 1.82), (0.082, 0.0, 1.885), (0.103, 0.0, 1.925)], (0.86, 0.0, 0.5))):
        add(side, sellip(0.023, 0.023, 0.017, 1.0, center=base, nu=16, nv=24))
        stalk = bezier(base, ctrl[0], ctrl[1], ctrl[2], 26)
        add(side, tube_tip(stalk, 0.0095, 0.0075))
        t = np.linspace(0, 1, 28)
        r = 0.027 * np.sin(np.pi * t) ** 0.72 * (1 - 0.22 * t)
        r[0] = 0; r[-1] = 0
        add(side, lathe(np.stack([r, t * 0.15], -1), 28, axis=leaf_dir, origin=np.asarray(ctrl[2]) - 0.006 * nrm(np.asarray(leaf_dir, float))))

    # ---- chest
    rows = [(1.183, 0, 0, 0.0), (1.19, 0.058, 0.048, 0.0), (1.21, 0.083, 0.068, 0.0), (1.25, 0.104, 0.080, -0.004),
            (1.30, 0.120, 0.088, -0.006), (1.345, 0.126, 0.088, -0.004), (1.38, 0.121, 0.083, 0.0),
            (1.41, 0.099, 0.069, 0.004), (1.432, 0.064, 0.051, 0.004), (1.442, 0, 0, 0.004)]
    add('chest', loft(rows, 64, 2.8, crease=0.035))
    add('chest', torus(0.046, 0.017, center=(0, 0.003, 1.437)))
    both('chest_', sphere(0.036, (0.128, 0, 1.372)))
    add('chest', lathe(chaikin([(0, 1.095), (0.042, 1.095), (0.042, 1.20), (0, 1.20)], 1), 32))
    add('chest', torus(0.045, 0.009, center=(0, 0, 1.17)))
    # wings
    for nm, L, Wd, root, down, back in (('wing1', 0.28, 0.088, (0.05, 0.10, 1.345), 20, 20),
                                         ('wing2', 0.20, 0.062, (0.045, 0.095, 1.275), 62, 16)):
        u = np.linspace(0, 1, 44)
        w = Wd * np.sin(np.pi * u ** 0.85) ** 0.85
        up = np.stack([u * L, w], -1)
        lo = np.stack([u * L, -0.8 * w], -1)[::-1][1:-1]
        o2 = np.vstack([up, lo])
        pts = np.stack([o2[:, 0], np.zeros(len(o2)), o2[:, 1]], -1)
        R = axis_angle((0, 0, 1), math.radians(back)) @ axis_angle((0, 1, 0), math.radians(down))
        pts = pts @ R.T + np.asarray(root)
        cen = np.array([0.45 * L, 0, 0]) @ R.T + np.asarray(root)
        wm = merge([fan(pts, cen), sweep(pts, 0.0075, closed=True, nseg=8)])
        both(nm, wm, WINGC, 0.3)

    # ---- pelvis
    add('pelvis', torus(0.064, 0.021, center=(0, 0, 1.105)))
    add('pelvis', sellip(0.098, 0.078, 0.075, 0.75, center=(0, 0, 0.995)))
    both('pelvis_', sphere(0.03, (0.075, 0, 0.92)))
    # abdomen (bee bottom) with segment grooves
    t = np.linspace(0, 1, 70)
    base_r = np.interp(t, [0, 0.04, 0.12, 0.25, 0.4, 0.55, 0.7, 0.82, 0.92, 0.97, 1.0],
                       [0.05, 0.07, 0.10, 0.118, 0.126, 0.123, 0.11, 0.09, 0.06, 0.035, 0.0])
    g = 1 - 0.07 * sum(np.exp(-((t - c) / 0.018) ** 2) for c in (0.3, 0.47, 0.64, 0.79))
    prof = np.vstack([[0, -0.005], np.stack([0.86 * base_r * g, t * 0.27], -1)])
    add('abdomen', lathe(prof, 44, axis=(0, 1.0, -0.42), origin=(0, 0.05, 1.0)))

    # ---- arms (left, mirrored)
    both('upper', lathe(chaikin([(0, 0), (0.017, 0), (0.017, 0.232), (0, 0.232)], 1), 20, axis=(1, 0, 0), origin=(0.128, 0, 1.37)))
    both('fore', sphere(0.026, (0.36, 0, 1.37)))
    gaunt = chaikin([(0, 0), (0.05, 0), (0.063, 0.003), (0.067, 0.011), (0.067, 0.027), (0.061, 0.033),
                     (0.061, 0.24), (0.057, 0.263), (0.045, 0.275), (0.02, 0.279), (0, 0.28)], 2)
    both('fore', lathe(gaunt, 44, axis=(1, 0, 0), origin=(0.37, 0, 1.37)))
    both('hand', lathe(chaikin([(0, 0), (0.012, 0), (0.012, 0.045), (0, 0.045)], 1), 16, axis=(1, 0, 0), origin=(0.64, 0, 1.37)))
    both('hand', sellip(0.036, 0.028, 0.011, 0.75, center=(0.708, 0, 1.37), nu=16, nv=24))
    fingers = []
    for yoff, ang, ln in ((-0.019, -10, 0.060), (-0.0065, -3, 0.068), (0.0065, 3, 0.064), (0.019, 10, 0.052)):
        p = np.array([0.738, yoff, 1.37]); d = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0.0])
        pts = [p.copy()]
        for k in range(10):
            ax = nrm(np.cross(d, [0, 0, -1.0]))
            d = axis_angle(ax, math.radians(3.2)) @ d
            p = p + d * ln / 10
            pts.append(p.copy())
        fingers.append(tube_tip(pts, 0.0063, 0.0047, base=False))
    tp = np.array([0.695, -0.026, 1.367]); td = nrm(np.array([0.5, -0.8, -0.2]))
    fingers.append(tube_tip([tp + td * 0.045 * s for s in np.linspace(0, 1, 8)], 0.0068, 0.0052, base=False))
    both('hand', merge(fingers))

    # ---- legs (left, mirrored)
    both('thigh', lathe(chaikin([(0, 0), (0.022, 0), (0.022, 0.095), (0, 0.095)], 1), 20, origin=(0.075, 0, 0.828)))
    brows = [(0.583, 0, 0, 0), (0.59, 0.044, 0.042, 0), (0.63, 0.049, 0.047, 0), (0.71, 0.057, 0.053, -0.004),
             (0.79, 0.065, 0.059, -0.006), (0.838, 0.071, 0.063, -0.006), (0.853, 0.066, 0.058, -0.004), (0.86, 0, 0, -0.004)]
    both('thigh', orient(loft(brows, 48, 2.4), np.eye(3), (0.075, 0, 0)))
    both('shin', lathe(chaikin([(0, 0), (0.026, 0), (0.026, 0.06), (0, 0.06)], 1), 24, axis=(1, 0, 0), origin=(0.045, 0, 0.575)))
    tt = np.linspace(0, 2 * np.pi, 160, endpoint=False)
    zz = 0.2875 + 0.2875 * np.cos(tt) + 0.007 * (1 - np.cos(tt)) / 2
    yy = np.where(np.sin(tt) >= 0, -0.042 * np.sin(tt), -0.062 * np.sin(tt))
    sc = 1 - 0.55 * np.exp(-((tt - np.pi) / 0.5) ** 2)
    loop = np.stack([np.full_like(tt, 0.075), yy, zz], -1)
    both('shin', sweep(loop, ra=0.021 * sc, rb=0.029 * sc, closed=True, nseg=12, fixedB=(1, 0, 0)))
    return parts


# ---------------------------------------------------------------- skirt
def logo_profile(path, n=600):
    import os
    if not os.path.exists(path):  # use the profile shipped with the web build
        src = open(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'skirt-profile.js')).read()
        R = np.array([float(x) for x in re.search(r'SKIRT_R = \[([^\]]*)\]', src).group(1).split(',')])
        return np.linspace(0, 2 * np.pi, len(R), endpoint=False), R
    im = np.asarray(Image.open(path).convert('RGB')).astype(int)
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    mask = (R > 140) & (R - B > 60) & (G < 175)
    ys, xs = np.nonzero(mask)
    cx, cy = xs.mean(), ys.mean()
    h, w = mask.shape
    steps = np.arange(0, max(h, w), 0.75)
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rad = np.zeros(n)
    for k, a in enumerate(th):
        px = cx + steps * math.cos(a); py = cy - steps * math.sin(a)
        ok = (px >= 0) & (px < w - 1) & (py >= 0) & (py < h - 1)
        m = mask[py[ok].astype(int), px[ok].astype(int)]
        idx = np.argmin(m) if not m.all() else len(m)
        rad[k] = steps[idx]
    rad = (np.roll(rad, 1) + 2 * rad + np.roll(rad, -1)) / 4
    rad = rad / rad.max()
    k = int(round(6.5 / 360 * n))
    dil = np.zeros(n)
    for o in range(-k, k + 1):
        dil = np.maximum(dil, np.roll(rad, o) * (1 - 0.18 * (o / k) ** 2))
    dil = 0.22 + 0.78 * dil / dil.max()
    return th, dil


class Skirt:
    def __init__(self, path, m=10):
        self.th, self.R = logo_profile(path)
        self.n = len(self.th); self.m = m
        self.t = np.linspace(0, 1, m)
        n = self.n
        # grid: top rows j=0..m-1, then bottom rows m-1..0 -> 2m rows (v), u = angle (wrap)
        self.T = tri_grid(n, 2 * m, True, False)
        pk = [k for k in range(n) if self.R[k] >= self.R[k - 1] and self.R[k] >= self.R[(k + 1) % n] and self.R[k] > 0.55]
        self.peaks = np.array(pk)

    def surface(self, flare=0.0, swirl=0.0, time=0.0, flutter=0.4, lift=None):
        th, R, t = self.th, self.R, self.t
        r_in, L, z0 = 0.062, 0.27, 1.097
        s = t[None, :] * R[:, None]                      # normalized arc length (n, m)
        phi0 = math.radians(10) * (1 - flare) + math.radians(-6) * flare
        kap = math.radians(46) * (1 - flare) + math.radians(14) * flare
        rip = (math.radians(3.0) * np.sin(3 * th + 4.3 * time) + math.radians(2.2) * np.sin(7 * th - 6.1 * time)) * flutter
        phi = phi0 + kap * s + rip[:, None] * s
        if lift is not None:
            lift = np.asarray(lift, float)
            phi = phi - (lift[:, None] if lift.ndim == 1 else lift)
        ds = np.diff(s, axis=1, prepend=0.0) * L
        rad = r_in + np.cumsum(np.cos(phi) * ds, axis=1)
        zz = z0 - np.cumsum(np.sin(phi) * ds, axis=1)
        ang = th[:, None] - swirl * s
        top = np.stack([rad * np.cos(ang), rad * np.sin(ang), zz], -1)
        return top, phi, ang

    def build(self, flare=0.0, swirl=0.0, time=0.0, flutter=0.4, lift=None):
        thick = 0.0085
        top, phi, ang = self.surface(flare, swirl, time, flutter, lift)
        nr = np.stack([np.sin(phi) * np.cos(ang), np.sin(phi) * np.sin(ang), np.cos(phi)], -1)
        bot = top - nr * thick
        G = np.concatenate([top, bot[:, ::-1]], axis=1)
        P = G.reshape(-1, 3)
        N = vnormals(P, self.T)
        tips = top[self.peaks, -1]
        return P, N, tips
