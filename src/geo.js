// Procedural geometry for the bee-bot ballerina. Every part is generated from math, no model files.
// Rest pose is the T-pose from the Blender screenshot: Z up, facing -Y, +X is her left.
import { D2R, unit, cross, sub, add, scl, dot, axisAngle, rotTo, m3v, I3 } from './math.js';
import { SKIRT_R, SKIRT_PEAKS } from './skirt-profile.js';

export const GREY = [0.80, 0.80, 0.80];
export const WINGC = [0.86, 0.87, 0.88];
export const ORANGE = [0.87, 0.24, 0.125];

function triGrid(nu, nv, wu, wv) {
  const iu = wu ? nu : nu - 1, jv = wv ? nv : nv - 1;
  const out = new Uint32Array(iu * jv * 6);
  let o = 0;
  for (let i = 0; i < iu; i++) for (let j = 0; j < jv; j++) {
    const a = i * nv + j, b = ((i + 1) % nu) * nv + j, c = ((i + 1) % nu) * nv + (j + 1) % nv, d = i * nv + (j + 1) % nv;
    out[o++] = a; out[o++] = b; out[o++] = c; out[o++] = a; out[o++] = c; out[o++] = d;
  }
  return out;
}

export function vnormals(P, I, N) {
  N = N || new Float32Array(P.length);
  N.fill(0);
  for (let k = 0; k < I.length; k += 3) {
    const a = I[k] * 3, b = I[k + 1] * 3, c = I[k + 2] * 3;
    const ux = P[b] - P[a], uy = P[b + 1] - P[a + 1], uz = P[b + 2] - P[a + 2];
    const vx = P[c] - P[a], vy = P[c + 1] - P[a + 1], vz = P[c + 2] - P[a + 2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    N[a] += nx; N[a + 1] += ny; N[a + 2] += nz; N[b] += nx; N[b + 1] += ny; N[b + 2] += nz; N[c] += nx; N[c + 1] += ny; N[c + 2] += nz;
  }
  for (let i = 0; i < N.length; i += 3) {
    const l = Math.hypot(N[i], N[i + 1], N[i + 2]) || 1;
    N[i] /= l; N[i + 1] /= l; N[i + 2] /= l;
  }
  return N;
}

function meshGrid(G, nu, nv, wu, wv, poles = []) {
  const P = new Float32Array(G), I = triGrid(nu, nv, wu, wv), N = vnormals(P, I);
  for (const [row, n] of poles) for (let j = 0; j < nv; j++) N.set(n, (row * nv + j) * 3);
  return { P, N, I };
}

function orient(m, R, t = [0, 0, 0]) {
  const { P, N } = m;
  for (let i = 0; i < P.length; i += 3) {
    const p = m3v(R, [P[i], P[i + 1], P[i + 2]]), n = m3v(R, [N[i], N[i + 1], N[i + 2]]);
    P[i] = p[0] + t[0]; P[i + 1] = p[1] + t[1]; P[i + 2] = p[2] + t[2];
    N[i] = n[0]; N[i + 1] = n[1]; N[i + 2] = n[2];
  }
  return m;
}

export function mirror(m) {
  const P = m.P.slice(), N = m.N.slice(), I = m.I.slice();
  for (let i = 0; i < P.length; i += 3) { P[i] = -P[i]; N[i] = -N[i]; }
  for (let k = 0; k < I.length; k += 3) { const t = I[k]; I[k] = I[k + 2]; I[k + 2] = t; }
  return { P, N, I };
}

function merge(ms) {
  let nv = 0, ni = 0;
  for (const m of ms) { nv += m.P.length; ni += m.I.length; }
  const P = new Float32Array(nv), N = new Float32Array(nv), I = new Uint32Array(ni);
  let ov = 0, oi = 0;
  for (const m of ms) {
    P.set(m.P, ov); N.set(m.N, ov);
    for (let k = 0; k < m.I.length; k++) I[oi + k] = m.I[k] + ov / 3;
    ov += m.P.length; oi += m.I.length;
  }
  return { P, N, I };
}

function chaikin(pts, it = 2) {
  let P = pts.map((p) => p.slice());
  for (let r = 0; r < it; r++) {
    const Q = [P[0]];
    for (let k = 0; k < P.length - 1; k++) {
      const a = P[k], b = P[k + 1];
      Q.push(a.map((v, i) => 0.75 * v + 0.25 * b[i]));
      Q.push(a.map((v, i) => 0.25 * v + 0.75 * b[i]));
    }
    Q.push(P[P.length - 1]);
    P = Q;
  }
  return P;
}

function lathe(prof, n = 40, axis = [0, 0, 1], origin = [0, 0, 0]) {
  const nu = prof.length, G = new Float64Array(nu * n * 3);
  for (let i = 0; i < nu; i++) for (let j = 0; j < n; j++) {
    const a = (2 * Math.PI * j) / n, o = (i * n + j) * 3;
    G[o] = prof[i][0] * Math.cos(a); G[o + 1] = prof[i][0] * Math.sin(a); G[o + 2] = prof[i][1];
  }
  const poles = [];
  if (prof[0][0] < 1e-9) poles.push([0, [0, 0, -1]]);
  if (prof[nu - 1][0] < 1e-9) poles.push([nu - 1, [0, 0, 1]]);
  return orient(meshGrid(G, nu, n, false, true, poles), rotTo(axis), origin);
}

const spow = (w, e) => Math.sign(w) * Math.pow(Math.abs(w), e);

function sellip(a, b, c, e = 0.5, center = [0, 0, 0], nu = 34, nv = 56) {
  const G = new Float64Array(nu * nv * 3);
  for (let i = 0; i < nu; i++) {
    const ph = -Math.PI / 2 + (Math.PI * i) / (nu - 1);
    const cp = i === 0 || i === nu - 1 ? 0 : Math.cos(ph);
    for (let j = 0; j < nv; j++) {
      const th = -Math.PI + (2 * Math.PI * j) / nv, o = (i * nv + j) * 3;
      G[o] = a * spow(cp, e) * spow(Math.cos(th), e) + center[0];
      G[o + 1] = b * spow(cp, e) * spow(Math.sin(th), e) + center[1];
      G[o + 2] = c * spow(Math.sin(ph), e) + center[2];
    }
  }
  return meshGrid(G, nu, nv, false, true, [[0, [0, 0, -1]], [nu - 1, [0, 0, 1]]]);
}
const sphere = (r, c) => sellip(r, r, r, 1.0, c, 18, 28);

function torus(R, r, center = [0, 0, 0], axis = [0, 0, 1], nu = 56, nv = 14) {
  const G = new Float64Array(nu * nv * 3);
  for (let i = 0; i < nu; i++) for (let j = 0; j < nv; j++) {
    const U = (2 * Math.PI * i) / nu, V = (2 * Math.PI * j) / nv, o = (i * nv + j) * 3;
    G[o] = (R + r * Math.cos(V)) * Math.cos(U); G[o + 1] = (R + r * Math.cos(V)) * Math.sin(U); G[o + 2] = r * Math.sin(V);
  }
  return orient(meshGrid(G, nu, nv, true, true), rotTo(axis), center);
}

function loft(rows, n = 56, p = 2.6, crease = 0) {
  const G = new Float64Array(rows.length * n * 3), poles = [];
  for (let r = 0; r < rows.length; r++) {
    const [z, hx, hy, yc] = rows[r];
    if (hx < 1e-9) poles.push([r, [0, 0, r === 0 ? -1 : 1]]);
    for (let j = 0; j < n; j++) {
      const th = (2 * Math.PI * j) / n, c = Math.cos(th), s = Math.sin(th);
      let k = 1;
      if (crease) { let d = th + Math.PI / 2; d = Math.atan2(Math.sin(d), Math.cos(d)); k = 1 - crease * Math.exp(-((d / 0.07) ** 2)); }
      const o = (r * n + j) * 3;
      G[o] = hx * spow(c, 2 / p) * k; G[o + 1] = yc + hy * spow(s, 2 / p) * k; G[o + 2] = z;
    }
  }
  return meshGrid(G, rows.length, n, false, true, poles);
}

function sweep(C, ra, rb, closed = false, nseg = 14, fixedB = null) {
  const n = C.length;
  const A = typeof ra === 'number' ? new Array(n).fill(ra) : ra;
  const B_ = rb == null ? A : typeof rb === 'number' ? new Array(n).fill(rb) : rb;
  const T = [];
  for (let k = 0; k < n; k++) {
    let d;
    if (closed) d = sub(C[(k + 1) % n], C[(k - 1 + n) % n]);
    else if (k === 0) d = sub(C[1], C[0]);
    else if (k === n - 1) d = sub(C[n - 1], C[n - 2]);
    else d = scl(sub(C[k + 1], C[k - 1]), 0.5);
    T.push(unit(d));
  }
  const N = [], Bv = [];
  if (fixedB) {
    for (let k = 0; k < n; k++) { const b = unit(sub(fixedB, scl(T[k], dot(T[k], fixedB)))); Bv.push(b); N.push(cross(b, T[k])); }
  } else {
    const a = Math.abs(T[0][2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
    N.push(unit(cross(T[0], a)));
    for (let k = 1; k < n; k++) N.push(unit(sub(N[k - 1], scl(T[k], dot(N[k - 1], T[k])))));
    for (let k = 0; k < n; k++) Bv.push(cross(T[k], N[k]));
  }
  const G = new Float64Array(n * nseg * 3);
  for (let k = 0; k < n; k++) for (let j = 0; j < nseg; j++) {
    const a = (2 * Math.PI * j) / nseg, o = (k * nseg + j) * 3, cs = Math.cos(a) * A[k], sn = Math.sin(a) * B_[k];
    G[o] = C[k][0] + N[k][0] * cs + Bv[k][0] * sn;
    G[o + 1] = C[k][1] + N[k][1] * cs + Bv[k][1] * sn;
    G[o + 2] = C[k][2] + N[k][2] * cs + Bv[k][2] * sn;
  }
  const m = meshGrid(G, n, nseg, closed, true);
  if (!closed) {
    if (A[0] < 1e-6) for (let j = 0; j < nseg; j++) m.N.set(scl(T[0], -1), j * 3);
    if (A[n - 1] < 1e-6) for (let j = 0; j < nseg; j++) m.N.set(T[n - 1], ((n - 1) * nseg + j) * 3);
  }
  return m;
}

function fan(outline, center) {
  const n = outline.length, P = new Float32Array((n + 1) * 3), I = new Uint32Array(n * 3);
  P.set(center, 0);
  outline.forEach((p, k) => P.set(p, (k + 1) * 3));
  for (let k = 0; k < n; k++) { I[k * 3] = 0; I[k * 3 + 1] = 1 + k; I[k * 3 + 2] = 1 + ((k + 1) % n); }
  return { P, N: vnormals(P, I), I };
}

function tubeTip(pts, r0, r1, tip = true, base = true) {
  const n = pts.length;
  let P = pts.slice(), r = pts.map((_, k) => r0 + ((r1 - r0) * k) / (n - 1));
  if (base) {
    const d0 = unit(sub(pts[0], pts[1]));
    P = [add(pts[0], scl(d0, r0 * 0.9)), add(pts[0], scl(d0, r0 * 0.6)), ...P];
    r = [0, r0 * 0.8, ...r];
  }
  if (tip) {
    const d1 = unit(sub(pts[n - 1], pts[n - 2]));
    P = [...P, add(pts[n - 1], scl(d1, r1 * 0.6)), add(pts[n - 1], scl(d1, r1 * 0.9))];
    r = [...r, r1 * 0.8, 0];
  }
  return sweep(P, r, null, false, 10);
}

function bezier(p0, p1, p2, p3, n = 24) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1), a = (1 - t) ** 3, b = 3 * (1 - t) ** 2 * t, c = 3 * (1 - t) * t * t, d = t ** 3;
    out.push([0, 1, 2].map((k) => a * p0[k] + b * p1[k] + c * p2[k] + d * p3[k]));
  }
  return out;
}

const HC = [0, 0, 1.60], HA = 0.175, HB = 0.150, HCZ = 0.140, HE = 0.5;
const shellFrontY = (x, z) => {
  const q = 1 - Math.abs(x / HA) ** (2 / HE) - Math.abs(z / HCZ) ** (2 / HE);
  return -HB * Math.pow(Math.min(Math.max(q, 0), 1), HE / 2);
};

export function buildParts() {
  const parts = [];
  const put = (bone, m, color = GREY, spec = 0.16) => parts.push({ bone, m, color, spec });
  const both = (bone, m, color = GREY, spec = 0.16) => { put(bone + 'L', m, color, spec); put(bone + 'R', mirror(m), color, spec); };
  const linspace = (a, b, n) => Array.from({ length: n }, (_, i) => a + ((b - a) * i) / (n - 1));

  // head: rounded TV-box shell, protruding frame, flat screen, ear discs, neck
  put('head', sellip(HA, HB, HCZ, HE, HC, 40, 72));
  const frame = [], screen = [];
  for (let k = 0; k < 140; k++) {
    const th = (2 * Math.PI * k) / 140, fx = spow(Math.cos(th), 2 / 4.5), fz = spow(Math.sin(th), 2 / 4.5);
    const px = 0.128 * fx, pz = 0.112 * fz;
    frame.push([px, shellFrontY(px, pz) - 0.012, pz + HC[2]]);
    screen.push([px, -0.152, pz + HC[2]]);
  }
  put('head', sweep(frame, 0.021, 0.030, true, 14, [0, 1, 0]));
  put('head', fan(screen, [0, -0.152, HC[2]]), [0.74, 0.75, 0.76], 0.25);
  const ear = chaikin([[0, 0], [0.068, 0], [0.071, 0.012], [0.066, 0.026], [0.053, 0.030], [0.049, 0.034],
    [0.049, 0.043], [0.038, 0.048], [0.026, 0.049], [0.021, 0.053], [0, 0.054]], 2);
  both('head_', lathe(ear, 40, [1, 0, 0], [0.166, -0.005, 1.605]));
  put('head', lathe(chaikin([[0, 1.425], [0.031, 1.425], [0.031, 1.478], [0, 1.478]], 1), 24));
  // antennae: socket, stalk, leaf
  for (const [side, base, ctrl, leafDir] of [
    ['antR', [-0.065, 0, 1.725], [[-0.075, 0, 1.81], [-0.058, 0, 1.89], [-0.068, 0, 1.955]], [-0.08, 0, 1.0]],
    ['antL', [0.065, 0, 1.725], [[0.07, 0, 1.82], [0.082, 0, 1.885], [0.103, 0, 1.925]], [0.86, 0, 0.5]]]) {
    put(side, sellip(0.023, 0.023, 0.017, 1.0, base, 16, 24));
    put(side, tubeTip(bezier(base, ctrl[0], ctrl[1], ctrl[2], 26), 0.0095, 0.0075));
    const prof = linspace(0, 1, 28).map((t, i, a) => [i === 0 || i === a.length - 1 ? 0 : 0.027 * Math.pow(Math.sin(Math.PI * t), 0.72) * (1 - 0.22 * t), t * 0.15]);
    put(side, lathe(prof, 28, leafDir, sub(ctrl[2], scl(unit(leafDir), 0.006))));
  }
  // chest
  put('chest', loft([[1.183, 0, 0, 0], [1.19, 0.058, 0.048, 0], [1.21, 0.083, 0.068, 0], [1.25, 0.104, 0.080, -0.004],
    [1.30, 0.120, 0.088, -0.006], [1.345, 0.126, 0.088, -0.004], [1.38, 0.121, 0.083, 0], [1.41, 0.099, 0.069, 0.004],
    [1.432, 0.064, 0.051, 0.004], [1.442, 0, 0, 0.004]], 64, 2.8, 0.035));
  put('chest', torus(0.046, 0.017, [0, 0.003, 1.437]));
  both('chest_', sphere(0.036, [0.128, 0, 1.372]));
  put('chest', lathe(chaikin([[0, 1.095], [0.042, 1.095], [0.042, 1.20], [0, 1.20]], 1), 32));
  put('chest', torus(0.045, 0.009, [0, 0, 1.17]));
  // wings: membrane fan + rim tube
  for (const [nm, L, Wd, root, down, back] of [['wing1', 0.28, 0.088, [0.05, 0.10, 1.345], 20, 20], ['wing2', 0.20, 0.062, [0.045, 0.095, 1.275], 62, 16]]) {
    const up = [], lo = [];
    for (let k = 0; k < 44; k++) { const u = k / 43, w = Wd * Math.pow(Math.sin(Math.PI * Math.pow(u, 0.85)), 0.85); up.push([u * L, w]); lo.push([u * L, -0.8 * w]); }
    const o2 = [...up, ...lo.reverse().slice(1, -1)];
    const R = (v) => m3v(axisAngle([0, 0, 1], back * D2R), m3v(axisAngle([0, 1, 0], down * D2R), v));
    const pts = o2.map(([x, z]) => add(R([x, 0, z]), root));
    const cen = add(R([0.45 * L, 0, 0]), root);
    both(nm, merge([fan(pts, cen), sweep(pts, 0.0075, null, true, 8)]), WINGC, 0.3);
  }
  // pelvis, hip balls, bee abdomen with segment grooves
  put('pelvis', torus(0.064, 0.021, [0, 0, 1.105]));
  put('pelvis', sellip(0.098, 0.078, 0.075, 0.75, [0, 0, 0.995]));
  both('pelvis_', sphere(0.03, [0.075, 0, 0.92]));
  const tx = [0, 0.04, 0.12, 0.25, 0.4, 0.55, 0.7, 0.82, 0.92, 0.97, 1.0], ty = [0.05, 0.07, 0.10, 0.118, 0.126, 0.123, 0.11, 0.09, 0.06, 0.035, 0];
  const interp = (t) => { for (let i = 0; i < tx.length - 1; i++) if (t <= tx[i + 1]) return ty[i] + (ty[i + 1] - ty[i]) * (t - tx[i]) / (tx[i + 1] - tx[i]); return 0; };
  const abd = [[0, -0.005]];
  for (const t of linspace(0, 1, 70)) {
    const g = 1 - 0.07 * [0.3, 0.47, 0.64, 0.79].reduce((s, c) => s + Math.exp(-(((t - c) / 0.018) ** 2)), 0);
    abd.push([0.86 * interp(t) * g, t * 0.27]);
  }
  put('abdomen', lathe(abd, 44, [0, 1.0, -0.42], [0, 0.05, 1.0]));
  // arms
  both('upper', lathe(chaikin([[0, 0], [0.017, 0], [0.017, 0.232], [0, 0.232]], 1), 20, [1, 0, 0], [0.128, 0, 1.37]));
  both('fore', sphere(0.026, [0.36, 0, 1.37]));
  const gaunt = chaikin([[0, 0], [0.05, 0], [0.063, 0.003], [0.067, 0.011], [0.067, 0.027], [0.061, 0.033],
    [0.061, 0.24], [0.057, 0.263], [0.045, 0.275], [0.02, 0.279], [0, 0.28]], 2);
  both('fore', lathe(gaunt, 44, [1, 0, 0], [0.37, 0, 1.37]));
  both('hand', lathe(chaikin([[0, 0], [0.012, 0], [0.012, 0.045], [0, 0.045]], 1), 16, [1, 0, 0], [0.64, 0, 1.37]));
  both('hand', sellip(0.036, 0.028, 0.011, 0.75, [0.708, 0, 1.37], 16, 24));
  const fingers = [];
  for (const [yoff, ang, ln] of [[-0.019, -10, 0.060], [-0.0065, -3, 0.068], [0.0065, 3, 0.064], [0.019, 10, 0.052]]) {
    let p = [0.738, yoff, 1.37], d = [Math.cos(ang * D2R), Math.sin(ang * D2R), 0];
    const pts = [p];
    for (let k = 0; k < 10; k++) { d = m3v(axisAngle(unit(cross(d, [0, 0, -1])), 3.2 * D2R), d); p = add(p, scl(d, ln / 10)); pts.push(p); }
    fingers.push(tubeTip(pts, 0.0063, 0.0047, true, false));
  }
  const tp = [0.695, -0.026, 1.367], td = unit([0.5, -0.8, -0.2]);
  fingers.push(tubeTip(linspace(0, 1, 8).map((s) => add(tp, scl(td, 0.045 * s))), 0.0068, 0.0052, true, false));
  both('hand', merge(fingers));
  // legs: thigh rod, boot, knee hinge, pointe loop
  both('thigh', lathe(chaikin([[0, 0], [0.022, 0], [0.022, 0.095], [0, 0.095]], 1), 20, [0, 0, 1], [0.075, 0, 0.828]));
  both('thigh', orient(loft([[0.583, 0, 0, 0], [0.59, 0.044, 0.042, 0], [0.63, 0.049, 0.047, 0], [0.71, 0.057, 0.053, -0.004],
    [0.79, 0.065, 0.059, -0.006], [0.838, 0.071, 0.063, -0.006], [0.853, 0.066, 0.058, -0.004], [0.86, 0, 0, -0.004]], 48, 2.4), I3(), [0.075, 0, 0]));
  both('shin', lathe(chaikin([[0, 0], [0.026, 0], [0.026, 0.06], [0, 0.06]], 1), 24, [1, 0, 0], [0.045, 0, 0.575]));
  const loop = [], ra = [], rb = [];
  for (let k = 0; k < 160; k++) {
    const t = (2 * Math.PI * k) / 160, s = Math.sin(t);
    const sc = 1 - 0.55 * Math.exp(-(((t - Math.PI) / 0.5) ** 2));
    loop.push([0.075, s >= 0 ? -0.042 * s : -0.062 * s, 0.2875 + 0.2875 * Math.cos(t) + (0.007 * (1 - Math.cos(t))) / 2]);
    ra.push(0.021 * sc); rb.push(0.029 * sc);
  }
  both('shin', sweep(loop, ra, rb, true, 12, [1, 0, 0]));
  return parts.map((p) => ({ ...p, bone: p.bone.endsWith('_L') || p.bone.endsWith('_R') ? p.bone.slice(0, -2) : p.bone }));
}

// The Claude Skirt: the spark logo's outline swept into a tutu of petals.
export class Skirt {
  constructor(m = 10) {
    this.R = SKIRT_R; this.peaks = SKIRT_PEAKS; this.n = SKIRT_R.length; this.m = m;
    const n = this.n;
    this.th = Float64Array.from({ length: n }, (_, i) => (2 * Math.PI * i) / n);
    this.I = triGrid(n, 2 * m, true, false);
    this.P = new Float32Array(n * 2 * m * 3); this.N = new Float32Array(this.P.length);
    this.top = new Float64Array(n * m * 3); this.phi = new Float64Array(n * m); this.ang = new Float64Array(n * m);
    this.lift = new Float64Array(n);
  }
  surface(flare, swirl, time, flutter, lift) {
    const { n, m, R, th, top, phi, ang } = this;
    const L = 0.27, z0 = 1.097, rIn = 0.062;
    const phi0 = 10 * D2R * (1 - flare) - 6 * D2R * flare, kap = 46 * D2R * (1 - flare) + 14 * D2R * flare;
    for (let i = 0; i < n; i++) {
      const rip = (3 * D2R * Math.sin(3 * th[i] + 4.3 * time) + 2.2 * D2R * Math.sin(7 * th[i] - 6.1 * time)) * flutter;
      let rad = rIn, z = z0, sPrev = 0;
      for (let j = 0; j < m; j++) {
        const s = (j / (m - 1)) * R[i], ph = phi0 + kap * s + rip * s - (lift ? lift[i] : 0), ds = (s - sPrev) * L;
        rad += Math.cos(ph) * ds; z -= Math.sin(ph) * ds; sPrev = s;
        const a = th[i] - swirl * s, o = i * m + j;
        top[o * 3] = rad * Math.cos(a); top[o * 3 + 1] = rad * Math.sin(a); top[o * 3 + 2] = z;
        phi[o] = ph; ang[o] = a;
      }
    }
    return top;
  }
  build(flare, swirl, time, flutter, lift) {
    const { n, m, top, phi, ang, P } = this, thick = 0.0085;
    this.surface(flare, swirl, time, flutter, lift);
    for (let i = 0; i < n; i++) for (let j = 0; j < m; j++) {
      const o = i * m + j, sp = Math.sin(phi[o]);
      const nx = sp * Math.cos(ang[o]), ny = sp * Math.sin(ang[o]), nz = Math.cos(phi[o]);
      const ti = (i * 2 * m + j) * 3, bi = (i * 2 * m + (2 * m - 1 - j)) * 3;
      P[ti] = top[o * 3]; P[ti + 1] = top[o * 3 + 1]; P[ti + 2] = top[o * 3 + 2];
      P[bi] = top[o * 3] - nx * thick; P[bi + 1] = top[o * 3 + 1] - ny * thick; P[bi + 2] = top[o * 3 + 2] - nz * thick;
    }
    vnormals(P, this.I, this.N);
    return this;
  }
  tips() { // outer tip of each big petal (skirt rest coordinates)
    return this.peaks.map((i) => { const o = (i * this.m + this.m - 1) * 3; return [this.top[o], this.top[o + 1], this.top[o + 2]]; });
  }
}
