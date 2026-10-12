"""Math helpers, skeleton, IK and spline interpolation."""
import math
import numpy as np


def Rx(a):
    a = math.radians(a); c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    a = math.radians(a); c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    a = math.radians(a); c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def eul(e):
    return Rz(e[2]) @ Ry(e[1]) @ Rx(e[0])


def M4(R=None, t=None):
    M = np.eye(4)
    if R is not None: M[:3, :3] = R
    if t is not None: M[:3, 3] = t
    return M


def unit(v):
    v = np.asarray(v, float); n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def perspective(fovy, aspect, n, f):
    t = 1 / math.tan(math.radians(fovy) / 2)
    M = np.zeros((4, 4))
    M[0, 0] = t / aspect; M[1, 1] = t; M[2, 2] = (f + n) / (n - f); M[2, 3] = 2 * f * n / (n - f); M[3, 2] = -1
    return M


def lookat(eye, tgt, up=(0, 0, 1)):
    f = unit(np.asarray(tgt) - eye); s = unit(np.cross(f, up)); u = np.cross(s, f)
    M = np.eye(4); M[0, :3] = s; M[1, :3] = u; M[2, :3] = -f
    M[:3, 3] = -M[:3, :3] @ eye
    return M


def smooth(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)


def mir(v):
    return np.array([-v[0], v[1], v[2]], float)


PIV = {'root': (0, 0, 1.0), 'pelvis': (0, 0, 1.0), 'chest': (0, 0, 1.12), 'head': (0, 0, 1.46),
       'antL': (0.065, 0, 1.725), 'wing1L': (0.05, 0.10, 1.345), 'wing2L': (0.045, 0.095, 1.275),
       'upperL': (0.128, 0, 1.37), 'foreL': (0.36, 0, 1.37), 'handL': (0.67, 0, 1.37),
       'thighL': (0.075, 0, 0.92), 'shinL': (0.075, 0, 0.575), 'abdomen': (0, 0.05, 1.0)}
for _k in list(PIV):
    if _k.endswith('L'):
        _x, _y, _z = PIV[_k]; PIV[_k[:-1] + 'R'] = (-_x, _y, _z)
PIV = {k: np.array(v, float) for k, v in PIV.items()}
PARENT = {'pelvis': 'root', 'chest': 'pelvis', 'head': 'chest', 'abdomen': 'pelvis'}
for _s in 'LR':
    PARENT.update({'ant' + _s: 'head', 'wing1' + _s: 'chest', 'wing2' + _s: 'chest', 'upper' + _s: 'chest',
                   'fore' + _s: 'upper' + _s, 'hand' + _s: 'fore' + _s, 'thigh' + _s: 'pelvis', 'shin' + _s: 'thigh' + _s})
ORDER = ['root', 'pelvis', 'chest', 'head', 'abdomen'] + [b + s for s in 'LR' for b in
         ('ant', 'wing1', 'wing2', 'upper', 'fore', 'hand', 'thigh', 'shin')]
L1A, L2A = 0.232, 0.31
L1L, L2L = 0.345, 0.575
ANT_TIP = {'antL': np.array([0.103, 0, 1.925]) + 0.144 * unit([0.86, 0, 0.5]),
           'antR': np.array([-0.068, 0, 1.955]) + 0.144 * unit([-0.08, 0, 1.0])}


def ik(S, T, l1, l2, pole):
    v = T - S; d = np.linalg.norm(v); u = v / d
    d = min(max(d, abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    ca = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d); sa = math.sqrt(max(0.0, 1 - ca * ca))
    w = pole - (pole @ u) * u
    if np.linalg.norm(w) < 1e-6:
        w = np.cross(u, [0, 0, 1.0]) if abs(u[2]) < 0.9 else np.cross(u, [1.0, 0, 0])
    w = unit(w)
    E = S + l1 * (ca * u + sa * w)
    d1 = (E - S) / l1; d2 = unit(S + u * d - E)
    b = unit(np.cross(w, u))
    return d1, d2, b


def arm_frames(d1, d2, b, side):
    def F(d):
        X, Z = (d, -b) if side == 'L' else (-d, b)
        return np.stack([X, np.cross(Z, X), Z], 1)
    Fu, Ff = F(d1), F(d2)
    return Fu, Fu.T @ Ff


def leg_frames(d1, d2, b):
    def F(d):
        X, Z = b, -d
        return np.stack([X, np.cross(Z, X), Z], 1)
    Ft, Fs = F(d1), F(d2)
    return Ft, Ft.T @ Fs


def fk(rp, yaw, loc):
    Wm = {'root': M4(Rz(yaw), rp)}
    for b in ORDER[1:]:
        p = PARENT[b]
        Wm[b] = Wm[p] @ M4(loc.get(b, np.eye(3)), PIV[b] - PIV[p])
    return Wm


def herm(ts, vals, t, holds, tension=0.55):
    n = len(ts)
    k = int(np.clip(np.searchsorted(ts, t, side='right') - 1, 0, n - 2))
    t0, t1 = ts[k], ts[k + 1]
    s = min(max((t - t0) / (t1 - t0), 0.0), 1.0)
    def tang(j):
        if holds[j]:
            return vals[j] * 0
        jm, jp = max(j - 1, 0), min(j + 1, n - 1)
        return tension * (vals[jp] - vals[jm]) / (ts[jp] - ts[jm])
    m0, m1 = tang(k) * (t1 - t0), tang(k + 1) * (t1 - t0)
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * vals[k] + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * vals[k + 1] + (s3 - s2) * m1


def bone_pt(Wm, bone, p):
    """World position of a rest-pose point p attached to bone."""
    return (Wm[bone] @ np.append(np.asarray(p, float) - PIV[bone], 1.0))[:3]
