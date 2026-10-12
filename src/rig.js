// Skeleton, two-bone IK and forward kinematics. Z is up, she faces -Y, +X is her left.
import { sub, add, scl, dot, cross, len, unit, m3mul, m3T, fromCols, m4, m4mul, m4pt, I3 } from './math.js';

const P = {
  root: [0, 0, 1.0], pelvis: [0, 0, 1.0], chest: [0, 0, 1.12], head: [0, 0, 1.46],
  antL: [0.065, 0, 1.725], wing1L: [0.05, 0.10, 1.345], wing2L: [0.045, 0.095, 1.275],
  upperL: [0.128, 0, 1.37], foreL: [0.36, 0, 1.37], handL: [0.67, 0, 1.37],
  thighL: [0.075, 0, 0.92], shinL: [0.075, 0, 0.575], abdomen: [0, 0.05, 1.0],
};
for (const k of Object.keys(P)) if (k.endsWith('L')) P[k.slice(0, -1) + 'R'] = [-P[k][0], P[k][1], P[k][2]];
export const PIV = P;
export const PARENT = { pelvis: 'root', chest: 'pelvis', head: 'chest', abdomen: 'pelvis' };
for (const s of 'LR') Object.assign(PARENT, {
  ['ant' + s]: 'head', ['wing1' + s]: 'chest', ['wing2' + s]: 'chest', ['upper' + s]: 'chest',
  ['fore' + s]: 'upper' + s, ['hand' + s]: 'fore' + s, ['thigh' + s]: 'pelvis', ['shin' + s]: 'thigh' + s,
});
export const ORDER = ['root', 'pelvis', 'chest', 'head', 'abdomen'];
for (const s of 'LR') for (const b of ['ant', 'wing1', 'wing2', 'upper', 'fore', 'hand', 'thigh', 'shin']) ORDER.push(b + s);
export const L1A = 0.232;
export const L2A = 0.31;
export const L1L = 0.345;
export const L2L = 0.575;
export const ANT_TIP = {
  antL: add([0.103, 0, 1.925], scl(unit([0.86, 0, 0.5]), 0.144)),
  antR: add([-0.068, 0, 1.955], scl(unit([-0.08, 0, 1.0]), 0.144)),
};

export function ik(S, T, l1, l2, pole) {
  const v = sub(T, S); let d = len(v); const u = scl(v, 1 / d);
  d = Math.min(Math.max(d, Math.abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4);
  const ca = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), sa = Math.sqrt(Math.max(0, 1 - ca * ca));
  let w = sub(pole, scl(u, dot(pole, u)));
  if (len(w) < 1e-6) w = Math.abs(u[2]) < 0.9 ? cross(u, [0, 0, 1]) : cross(u, [1, 0, 0]);
  w = unit(w);
  const E = add(S, scl(add(scl(u, ca), scl(w, sa)), l1));
  const d1 = scl(sub(E, S), 1 / l1), d2 = unit(sub(add(S, scl(u, d)), E));
  const b = unit(cross(w, u));
  return [d1, d2, b];
}
export function armFrames(d1, d2, b, side) {
  const F = (d) => { const X = side === 'L' ? d : scl(d, -1), Z = side === 'L' ? scl(b, -1) : b; return fromCols(X, cross(Z, X), Z); };
  const Fu = F(d1), Ff = F(d2);
  return [Fu, m3mul(m3T(Fu), Ff)];
}
export function legFrames(d1, d2, b) {
  const F = (d) => { const X = b, Z = scl(d, -1); return fromCols(X, cross(Z, X), Z); };
  const Ft = F(d1), Fs = F(d2);
  return [Ft, m3mul(m3T(Ft), Fs)];
}
export function fk(rootM, loc) {
  const W = { root: rootM };
  for (let i = 1; i < ORDER.length; i++) {
    const b = ORDER[i], p = PARENT[b];
    W[b] = m4mul(W[p], m4(loc[b] || I3(), sub(PIV[b], PIV[p])));
  }
  return W;
}
export const bonePt = (W, bone, p) => m4pt(W[bone], sub(p, PIV[bone]));
