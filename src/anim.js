// Choreography playback: key interpolation, IK, secondary motion (skirt, antennae, wings) and sparkles.
import { D2R, add, sub, scl, dot, cross, len, unit, lerp, lerp3, clamp, Rx, Ry, Rz, eul, m3mul, m3T, m3v,
  axisAngle, m4, m4mul, m4pt, m4R, m4t, m4invRigid, wrap180, rng } from './math.js';
import { PIV, L1A, L2A, L1L, L2L, ANT_TIP, ik, armFrames, legFrames, fk, bonePt } from './rig.js';

const mir = (v) => [-v[0], v[1], v[2]];

export function spotRz(rel) { // ballet "spotting": the head waits, then whips round
  if (Math.abs(rel) <= 75) return -rel;
  const f = rel > 75 ? (rel - 75) / 210 : (rel + 360 - 75) / 210;
  return -75 + 150 * f;
}

export class Timeline {
  constructor(dance) {
    this.d = dance;
    const keys = dance.keys;
    this.ts = keys.map((k) => k.t);
    this.holds = keys.map((k) => !!k.h);
    const cur = { song: 0, wag: 0 }, S = [];
    for (const k of keys) { Object.assign(cur, k); S.push({ ...cur }); }
    const F = {};
    for (const f of ['rp', 'pel', 'chs', 'head', 'abd', 'flap', 'wL']) F[f] = S.map((s) => s[f]);
    for (const f of ['yaw', 'bour', 'rip', 'spot', 'song', 'wag']) F[f] = S.map((s) => [s[f]]);
    F.wR = S.map((s) => [s.wR[0], -s.wR[1], -s.wR[2]]);
    F.aLo = S.map((s) => s.aL[0]); F.aLp = S.map((s) => unit(s.aL[1]));
    F.aRo = S.map((s) => mir(s.aR[0])); F.aRp = S.map((s) => mir(unit(s.aR[1])));
    this.F = F; this.legs = { L: S.map((s) => s.lL), R: S.map((s) => s.lR) };
    this.dur = dance.dur; this.jumps = dance.jumps || [];
  }
  // Hermite (cardinal, tension .55) weights as a sparse list [[keyIndex, weight], ...]
  basis(t, tension = 0.55) {
    const ts = this.ts, n = ts.length;
    let lo = 0, hi = n - 1;
    while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (ts[mid] <= t) lo = mid; else hi = mid - 1; }
    const k = Math.min(Math.max(lo, 0), n - 2), t0 = ts[k], t1 = ts[k + 1], dt = t1 - t0;
    const s = clamp((t - t0) / dt, 0, 1), s2 = s * s, s3 = s2 * s;
    const h00 = 2 * s3 - 3 * s2 + 1, h10 = s3 - 2 * s2 + s, h01 = -2 * s3 + 3 * s2, h11 = s3 - s2;
    const w = new Map();
    const addw = (j, v) => w.set(j, (w.get(j) || 0) + v);
    addw(k, h00); addw(k + 1, h01);
    if (!this.holds[k]) { const jm = Math.max(k - 1, 0), jp = Math.min(k + 1, n - 1), c = (h10 * dt * tension) / (ts[jp] - ts[jm]); addw(jp, c); addw(jm, -c); }
    if (!this.holds[k + 1]) { const jm = k, jp = Math.min(k + 2, n - 1), c = (h11 * dt * tension) / (ts[jp] - ts[jm]); addw(jp, c); addw(jm, -c); }
    return [...w.entries()];
  }
  mix(B, field) {
    const arr = this.F[field], L = arr[0].length, out = new Array(L).fill(0);
    for (const [j, w] of B) { const v = arr[j]; for (let i = 0; i < L; i++) out[i] += w * v[i]; }
    return out;
  }
}

function legWorld(spec, side, rp, yaw, Wpel, t, bour, sig) {
  let [mode, v, pole] = spec;
  v = v.slice(); pole = unit(pole);
  if (side === 'R') { v = mir(v); pole = mir(pole); }
  const Rw = Rz(yaw);
  if (mode === 'floor') {
    if (bour > 0) { // tiny pointe steps: left and right feet are driven in anti-phase by the CPG
      const k = side === 'L' ? sig : -sig;
      v[1] += bour * 0.024 * k;
      v[2] += bour * 0.012 * Math.max(0, k);
    }
    return [add([rp[0], rp[1], 0], m3v(Rw, v)), m3v(Rw, pole)];
  }
  const hipLocal = add(sub(PIV['thigh' + side], PIV.pelvis), v);
  return [m4pt(Wpel, hipLocal), m3v(m4R(Wpel), pole)];
}

// Evaluate the choreography at time t into a blendable parameter set (legs as world-space targets).
export function evalParams(tl, t, yaw, sig) {
  if (sig == null) sig = Math.sin(2 * Math.PI * 7 * t);
  const B = tl.basis(t);
  const p = {};
  p.yawKey = tl.mix(B, 'yaw')[0];
  p.yaw = yaw == null ? p.yawKey : yaw;
  p.rp = tl.mix(B, 'rp');
  p.bour = clamp(tl.mix(B, 'bour')[0], 0, 1); p.rip = clamp(tl.mix(B, 'rip')[0], 0, 1);
  p.spot = clamp(tl.mix(B, 'spot')[0], 0, 1); p.song = clamp(tl.mix(B, 'song')[0], 0, 1); p.wag = clamp(tl.mix(B, 'wag')[0], 0, 1);
  for (const [t0, t1, h] of tl.jumps) if (t >= t0 && t <= t1) { const s = (t - t0) / (t1 - t0); p.rp[2] += h * 4 * s * (1 - s); }
  p.rp[2] += p.bour * 0.004 * (2 * sig * sig - 1);
  for (const f of ['pel', 'chs', 'head', 'abd', 'flap', 'wL', 'wR', 'aLo', 'aLp', 'aRo', 'aRp']) p[f] = tl.mix(B, f);
  const Wroot = m4(Rz(p.yaw), p.rp), Wpel = m4mul(Wroot, m4(eul(p.pel), sub(PIV.pelvis, PIV.root)));
  p.legs = {};
  for (const s of 'LR') {
    let T = [0, 0, 0], Pp = [0, 0, 0];
    for (const [j, w] of B) {
      const [a, b] = legWorld(tl.legs[s][j], s, p.rp, p.yaw, Wpel, t, p.bour, sig);
      T = add(T, scl(a, w)); Pp = add(Pp, scl(b, w));
    }
    p.legs[s] = [T, unit(Pp)];
  }
  p.t = t;
  return p;
}

export function blendParams(a, b, w) {
  const o = {};
  for (const k of Object.keys(a)) {
    const va = a[k], vb = b[k];
    if (k === 'legs') o.legs = { L: [lerp3(va.L[0], vb.L[0], w), unit(lerp3(va.L[1], vb.L[1], w))], R: [lerp3(va.R[0], vb.R[0], w), unit(lerp3(va.R[1], vb.R[1], w))] };
    else if (Array.isArray(va)) o[k] = va.map((x, i) => lerp(x, vb[i], w));
    else if (typeof va === 'number') o[k] = lerp(va, vb, w);
  }
  o.t = b.t;
  return o;
}

// Turn parameters into bone rotations (IK for arms and legs, spotting, ripples, waggle).
export function solvePose(p, t, camAz) {
  const loc = {};
  const Wroot = m4(Rz(p.yaw), p.rp);
  loc.pelvis = eul(p.pel);
  const Wpel = m4mul(Wroot, m4(loc.pelvis, sub(PIV.pelvis, PIV.root)));
  const WpelInv = m4invRigid(Wpel);
  loc.chest = eul(p.chs);
  const hd = p.head.slice();
  if (p.spot > 0) hd[2] = (1 - p.spot) * hd[2] + p.spot * spotRz(wrap180(p.yaw + camAz));
  loc.head = eul(hd);
  loc.abdomen = m3mul(eul(p.abd), Rz(p.wag * 22 * Math.sin(2 * Math.PI * 7 * t)));
  const wv = Math.sin(2 * Math.PI * 0.9 * t);
  for (const s of 'LR') {
    const off = s === 'L' ? p.aLo.slice() : p.aRo.slice();
    let pole = s === 'L' ? p.aLp.slice() : p.aRp.slice();
    if (p.rip > 0) { off[2] += p.rip * 0.075 * wv; pole[2] += p.rip * 0.7 * Math.sin(2 * Math.PI * 0.9 * t - 0.9); }
    pole = unit(pole);
    const S = sub(PIV['upper' + s], PIV.chest);
    let [d1, d2, b] = ik(S, add(S, off), L1A, L2A, pole);
    [loc['upper' + s], loc['fore' + s]] = armFrames(d1, d2, b, s);
    const we = (s === 'L' ? p.wL : p.wR).slice();
    if (p.rip > 0) we[1] += p.rip * 28 * Math.sin(2 * Math.PI * 0.9 * t - 1.8) * (s === 'L' ? 1 : -1);
    loc['hand' + s] = eul(we);
    const [Tw, Pw] = p.legs[s];
    const Tl = m4pt(WpelInv, Tw), Pl = m3v(m3T(m4R(Wpel)), Pw);
    [d1, d2, b] = ik(sub(PIV['thigh' + s], PIV.pelvis), Tl, L1L, L2L, Pl);
    [loc['thigh' + s], loc['shin' + s]] = legFrames(d1, d2, b);
  }
  return { loc, Wroot };
}

// ------------------------------------------------------------------ secondary motion + sparkles
export class Secondary {
  constructor(skirt) {
    this.skirt = skirt;
    this.fl = 0; this.flv = 0; this.sw = 0; this.swv = 0; this.ph = 0;
    this.prev = null; this.ant = {};
    this.lift = new Float64Array(skirt.n); this.need = new Float64Array(skirt.n);
    this.parts = []; this.rand = rng(7);
    this.kern = []; for (let o = -30; o <= 30; o++) this.kern.push(Math.exp(-0.5 * (o / 9) ** 2));
    const ks = this.kern.reduce((a, b) => a + b, 0); this.kern = this.kern.map((k) => k / ks);
  }
  // advance springs; returns per-frame extras used by the renderer
  step(dt, p, t, loc, rootW, extra) {
    dt = Math.min(Math.max(dt, 1e-4), 0.05);
    const yaw = p.yaw, z = p.rp[2], xy = [p.rp[0], p.rp[1]];
    const prev = this.prev || { yaw, z, xy };
    const om = (yaw - prev.yaw) / dt, vz = (z - prev.z) / dt, speed = Math.hypot(xy[0] - prev.xy[0], xy[1] - prev.xy[1]) / dt;
    this.prev = { yaw, z, xy };
    const spin = Math.min(Math.abs(om) / 950, 1);
    const tgt = Math.pow(spin, 0.8) + clamp(-vz * 0.45, -0.35, 0.6) + Math.min(speed * 0.25, 0.3) + (extra.excite || 0) * 0.25;
    const stgt = Math.abs(om) > 1 ? -Math.sign(om) * 0.5 * spin : 0;
    const w1 = 2 * Math.PI * 2.3, z1 = 0.33, w2 = 2 * Math.PI * 2.0, z2 = 0.5;
    for (let i = 0; i < 4; i++) {
      const h = dt / 4;
      this.flv += (w1 * w1 * (tgt - this.fl) - 2 * z1 * w1 * this.flv) * h; this.fl += this.flv * h;
      this.swv += (w2 * w2 * (stgt - this.sw) - 2 * z2 * w2 * this.swv) * h; this.sw += this.swv * h;
    }
    this.flare = clamp(this.fl, -0.45, 1.15);
    this.flutter = 0.35 + 0.9 * spin + 0.6 * Math.min(Math.abs(vz), 1) + 0.5 * Math.min(speed, 1);
    this.omega = om;
    const wig = clamp(3.5 * Math.sin(2 * Math.PI * 0.55 * t) - 10 * vz, -14, 14);
    loc.abdomen = m3mul(loc.abdomen, Rx(wig));
    // wings: flapping, plus the fruit-fly courtship song (one wing out, vibrating)
    const [amp, fq] = p.flap;
    this.ph += 2 * Math.PI * (fq + (extra.excite || 0) * 6) * dt;
    const a1 = (amp + (extra.excite || 0) * 12) * Math.sin(this.ph), a2 = 0.8 * amp * Math.sin(this.ph - 0.7);
    const song = p.song, vib = song * 9 * Math.sin(2 * Math.PI * 13 * t);
    loc.wing1L = m3mul(Rz(a1 * (1 - song) - 48 * song + vib), Ry(-28 * song));
    loc.wing2L = Rz(a2 * (1 - song * 0.7));
    loc.wing1R = Rz(-a1); loc.wing2R = Rz(-a2);
    // antennae: tips hang on damped springs that lag behind the head
    const W0 = fk(rootW, loc);
    for (const [side, ph0] of [['antL', 0], ['antR', 1.7]]) {
      const idle = eul([3 * Math.sin(2 * Math.PI * 0.7 * t + ph0), 0, 4 * Math.sin(2 * Math.PI * 0.45 * t + ph0)]);
      loc[side] = idle;
      const Wh = W0.head, Hr = m4R(Wh);
      const base = m4pt(Wh, sub(PIV[side], PIV.head));
      const Wa = m4mul(Wh, m4(idle, sub(PIV[side], PIV.head)));
      const rest = m4pt(Wa, sub(ANT_TIP[side], PIV[side]));
      let st = this.ant[side];
      if (!st) st = this.ant[side] = { x: rest.slice(), v: [0, 0, 0] };
      const wn = 2 * Math.PI * 2.6, zt = 0.17;
      for (let i = 0; i < 6; i++) {
        const h = dt / 6;
        const a = sub(scl(sub(rest, st.x), wn * wn), scl(st.v, 2 * zt * wn));
        st.v = add(st.v, scl(a, h)); st.x = add(st.x, scl(st.v, h));
      }
      const r0 = unit(sub(rest, base)), r1 = unit(sub(st.x, base));
      const ax = cross(r0, r1), sn = len(ax), ang = Math.min(Math.atan2(sn, dot(r0, r1)), 50 * D2R);
      const Rd = sn > 1e-8 ? axisAngle(ax, ang) : [1, 0, 0, 0, 1, 0, 0, 0, 1];
      loc[side] = m3mul(m3T(Hr), m3mul(Rd, m3mul(Hr, idle)));
    }
    return fk(rootW, loc);
  }
  // Petals are pushed up wherever a leg or an arm would cut through them.
  solveSkirt(W, t) {
    const sk = this.skirt, n = sk.n, m = sk.m;
    const Pinv = m4invRigid(W.pelvis);
    const conv = (w) => add(m4pt(Pinv, w), PIV.pelvis);
    const caps = [];
    const cap = (a, b, r) => caps.push([a[0], a[1], a[2], b[0], b[1], b[2], r * r]);
    for (const [s, sg] of [['L', 1], ['R', -1]]) {
      cap(conv(m4t(W['thigh' + s])), conv(m4t(W['shin' + s])), 0.08);
      cap(conv(m4t(W['shin' + s])), conv(bonePt(W, 'shin' + s, [sg * 0.075, 0, 0.02])), 0.072);
      cap(conv(bonePt(W, 'fore' + s, [sg * 0.385, 0, 1.37])), conv(bonePt(W, 'fore' + s, [sg * 0.625, 0, 1.37])), 0.072);
      cap(conv(bonePt(W, 'hand' + s, [sg * 0.68, 0, 1.37])), conv(bonePt(W, 'hand' + s, [sg * 0.79, 0, 1.37])), 0.038);
    }
    const cands = [0, 7, 14, 22, 31, 41, 53, 66, 80].map((d) => d * D2R);
    const need = this.need; need.fill(cands[cands.length - 1]);
    const found = new Uint8Array(n); let nFound = 0;
    const lift = new Float64Array(n);
    for (const c of cands) {
      lift.fill(c);
      const top = sk.surface(this.flare, this.sw, t, this.flutter, lift);
      for (let i = 0; i < n; i++) {
        if (found[i]) continue;
        let ok = true;
        for (let j = 3; j < m && ok; j++) {
          const o = (i * m + j) * 3, px = top[o], py = top[o + 1], pz = top[o + 2];
          for (let q = 0; q < caps.length; q++) {
            const C = caps[q];
            const ax = C[0], ay = C[1], az = C[2], bx = C[3], by = C[4], bz = C[5];
            const ex = bx - ax, ey = by - ay, ez = bz - az;
            let u = ((px - ax) * ex + (py - ay) * ey + (pz - az) * ez) / (ex * ex + ey * ey + ez * ez + 1e-12);
            u = u < 0 ? 0 : u > 1 ? 1 : u;
            const dx = px - ax - ex * u, dy = py - ay - ey * u, dz = pz - az - ez * u;
            if (dx * dx + dy * dy + dz * dz < C[6]) { ok = false; break; }
          }
        }
        if (ok) { found[i] = 1; nFound++; need[i] = c; }
      }
      if (nFound === n) break;
    }
    const K = this.kern, out = this.lift;
    for (let i = 0; i < n; i++) {
      let acc = 0;
      for (let o = -30; o <= 30; o++) acc += K[o + 30] * need[(i + o + n) % n];
      const v = Math.max(need[i], acc * 1.15);
      out[i] = Math.max(v, out[i] - 5 * D2R);
    }
    return out;
  }
  // sparkles flung off the petal tips
  emitParticles(W, t, dt, rate, burst, om, center) {
    const sk = this.skirt, tips = sk.tips(), Wp = W.pelvis, R = this.rand;
    let n = 0;
    const lam = rate * dt; let L = Math.exp(-lam), k = 0, pr = 1;
    do { k++; pr *= R(); } while (pr > L && k < 50);
    n = k - 1 + (burst || 0);
    const omr = om * D2R;
    for (let i = 0; i < n && this.parts.length < 2500; i++) {
      const tip = tips[Math.floor(R() * tips.length)];
      const pos = add(m4pt(Wp, sub(tip, PIV.pelvis)), [(R() - 0.5) * 0.02, (R() - 0.5) * 0.02, (R() - 0.5) * 0.02]);
      const c = [center[0], center[1], pos[2]];
      let rad = sub(pos, c); rad[2] = 0; rad = unit(rad);
      const tan = scl(cross([0, 0, omr], sub(pos, c)), 0.7);
      const big = burst > 0;
      const out = big ? 0.6 + R() * 1.2 : 0.15 + R() * 0.4, up = big ? 0.4 + R() * 1.2 : 0.05 + R() * 0.65;
      const v = add(add(tan, scl(rad, out)), [(R() - 0.5) * 0.24, (R() - 0.5) * 0.24, up + (R() - 0.5) * 0.24]);
      const life = 0.7 + R() * 0.9;
      this.parts.push({ p: pos, v, life, life0: life, size: 0.018 + R() * 0.024, hue: R(), ph: R() * 6.28 });
    }
  }
  burstAt(pos, count) {
    const R = this.rand;
    for (let i = 0; i < count && this.parts.length < 2500; i++) {
      const d = unit([R() - 0.5, R() - 0.5, R() - 0.5]);
      const life = 0.8 + R() * 1.0;
      this.parts.push({ p: add(pos, scl(d, R() * 0.2)), v: add(scl(d, 0.6 + R() * 1.3), [0, 0, 0.4]), life, life0: life, size: 0.02 + R() * 0.025, hue: R(), ph: R() * 6.28 });
    }
  }
  updateParticles(dt, t, buf) {
    const ps = this.parts, damp = Math.exp(-0.9 * dt);
    let w = 0, o = 0;
    for (let i = 0; i < ps.length; i++) {
      const q = ps[i];
      q.v = scl(q.v, damp); q.v[2] -= 0.9 * dt; q.p = add(q.p, scl(q.v, dt)); q.life -= dt;
      if (q.p[2] < 0.01) { q.p[2] = 0.01; q.v[2] *= -0.3; }
      if (q.life <= 0) continue;
      ps[w++] = q;
      const k = q.life / q.life0, a = clamp(k * 1.3, 0, 1) * (0.65 + 0.35 * Math.sin(t * 22 + q.ph));
      if (o + 8 <= buf.length) {
        buf[o++] = q.p[0]; buf[o++] = q.p[1]; buf[o++] = q.p[2];
        buf[o++] = 1; buf[o++] = 0.55 + 0.4 * q.hue; buf[o++] = 0.32 + 0.55 * q.hue; buf[o++] = a; buf[o++] = q.size * (0.5 + 0.5 * k);
      }
    }
    ps.length = w;
    return o / 8;
  }
}
