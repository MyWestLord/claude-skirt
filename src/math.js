// Small linear-algebra kit. Matrices are plain row-major arrays (mat3: 9 numbers, mat4: 16 numbers).
export const D2R = Math.PI / 180;

export const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
export const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
export const scl = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
export const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
export const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
export const len = (a) => Math.hypot(a[0], a[1], a[2]);
export const unit = (a) => { const l = len(a); return l > 1e-12 ? [a[0] / l, a[1] / l, a[2] / l] : [a[0], a[1], a[2]]; };
export const lerp = (a, b, t) => a + (b - a) * t;
export const lerp3 = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
export const clamp = (x, a, b) => Math.min(Math.max(x, a), b);

export const I3 = () => [1, 0, 0, 0, 1, 0, 0, 0, 1];
export function m3mul(a, b) {
  const r = new Array(9);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++)
    r[i * 3 + j] = a[i * 3] * b[j] + a[i * 3 + 1] * b[3 + j] + a[i * 3 + 2] * b[6 + j];
  return r;
}
export const m3v = (a, v) => [a[0] * v[0] + a[1] * v[1] + a[2] * v[2], a[3] * v[0] + a[4] * v[1] + a[5] * v[2], a[6] * v[0] + a[7] * v[1] + a[8] * v[2]];
export const m3T = (a) => [a[0], a[3], a[6], a[1], a[4], a[7], a[2], a[5], a[8]];
export function Rx(d) { const a = d * D2R, c = Math.cos(a), s = Math.sin(a); return [1, 0, 0, 0, c, -s, 0, s, c]; }
export function Ry(d) { const a = d * D2R, c = Math.cos(a), s = Math.sin(a); return [c, 0, s, 0, 1, 0, -s, 0, c]; }
export function Rz(d) { const a = d * D2R, c = Math.cos(a), s = Math.sin(a); return [c, -s, 0, s, c, 0, 0, 0, 1]; }
export const eul = (e) => m3mul(Rz(e[2]), m3mul(Ry(e[1]), Rx(e[0])));
export function axisAngle(axis, ang) {
  const [x, y, z] = unit(axis), c = Math.cos(ang), s = Math.sin(ang), t = 1 - c;
  return [t * x * x + c, t * x * y - s * z, t * x * z + s * y,
          t * x * y + s * z, t * y * y + c, t * y * z - s * x,
          t * x * z - s * y, t * y * z + s * x, t * z * z + c];
}
export function rotTo(axis) { // rotation taking +Z onto axis
  const a = unit(axis), z = [0, 0, 1], v = cross(z, a), s = len(v), c = dot(z, a);
  if (s < 1e-9) return c > 0 ? I3() : [1, 0, 0, 0, -1, 0, 0, 0, -1];
  return axisAngle(v, Math.atan2(s, c));
}
export const fromCols = (X, Y, Z) => [X[0], Y[0], Z[0], X[1], Y[1], Z[1], X[2], Y[2], Z[2]];

export function m4(R, t) {
  R = R || I3(); t = t || [0, 0, 0];
  return [R[0], R[1], R[2], t[0], R[3], R[4], R[5], t[1], R[6], R[7], R[8], t[2], 0, 0, 0, 1];
}
export function m4mul(a, b) {
  const r = new Array(16);
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++)
    r[i * 4 + j] = a[i * 4] * b[j] + a[i * 4 + 1] * b[4 + j] + a[i * 4 + 2] * b[8 + j] + a[i * 4 + 3] * b[12 + j];
  return r;
}
export const m4pt = (M, p) => [M[0] * p[0] + M[1] * p[1] + M[2] * p[2] + M[3], M[4] * p[0] + M[5] * p[1] + M[6] * p[2] + M[7], M[8] * p[0] + M[9] * p[1] + M[10] * p[2] + M[11]];
export const m4R = (M) => [M[0], M[1], M[2], M[4], M[5], M[6], M[8], M[9], M[10]];
export const m4t = (M) => [M[3], M[7], M[11]];
export function m4invRigid(M) {
  const R = m3T(m4R(M)), t = m3v(R, m4t(M));
  return m4(R, [-t[0], -t[1], -t[2]]);
}
export function perspective(fovy, aspect, n, f) {
  const t = 1 / Math.tan(fovy * D2R / 2);
  return [t / aspect, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), 2 * f * n / (n - f), 0, 0, -1, 0];
}
export function lookAt(eye, tgt, up = [0, 0, 1]) {
  const f = unit(sub(tgt, eye)), s = unit(cross(f, up)), u = cross(s, f);
  const M = [s[0], s[1], s[2], 0, u[0], u[1], u[2], 0, -f[0], -f[1], -f[2], 0, 0, 0, 0, 1];
  M[3] = -dot(s, eye); M[7] = -dot(u, eye); M[11] = dot(f, eye);
  return M;
}
export function toGL(M, out) { // row-major -> column-major Float32Array
  out = out || new Float32Array(16);
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) out[j * 4 + i] = M[i * 4 + j];
  return out;
}
export const wrap180 = (a) => ((a + 180) % 360 + 360) % 360 - 180;
export const smooth = (x) => { x = clamp(x, 0, 1); return x * x * (3 - 2 * x); };

// Seeded PRNG (mulberry32) so effects are reproducible.
export function rng(seed) {
  let a = seed >>> 0;
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
