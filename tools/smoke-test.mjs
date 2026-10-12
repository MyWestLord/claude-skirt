// Headless smoke test: builds the model and plays every dance through the animation stack (no DOM, no GPU).
import { DANCES } from '../src/dances.data.js';
import { buildParts, Skirt } from '../src/geo.js';
import { Timeline, evalParams, blendParams, solvePose, Secondary } from '../src/anim.js';
import { FlyBrain } from '../src/brain.js';
import { D2R } from '../src/math.js';

const t0 = performance.now();
const parts = buildParts();
let nv = 0, ni = 0;
for (const p of parts) { nv += p.m.P.length / 3; ni += p.m.I.length / 3; if (p.m.P.some(Number.isNaN) || p.m.N.some(Number.isNaN)) throw new Error('NaN in ' + p.bone); }
const sk = new Skirt(); sk.build(0, 0, 0, 0.4, null);
console.log(`parts ${parts.length}  verts ${nv}  tris ${ni}  build ${(performance.now() - t0).toFixed(0)} ms`);
const ptsBuf = new Float32Array(2500 * 8);
for (const d of [...DANCES.dances, DANCES.freestyle[0]]) {
  const tl = new Timeline(d), brain = new FlyBrain(), sec = new Secondary(sk);
  const dt = 1 / 60; let prevYaw = 0, maxErr = 0, worst = 0, nPts = 0, tSolve = 0, prevP = null;
  const ts = performance.now();
  for (let t = 0; t <= d.dur; t += dt) {
    const yawD = tl.mix(tl.basis(t), 'yaw')[0];
    const head = brain.step(dt, (yawD - prevYaw) / dt * D2R, yawD * D2R) / D2R; prevYaw = yawD;
    maxErr = Math.max(maxErr, Math.abs(head - yawD));
    let p = evalParams(tl, t, head, Math.sin(t * 40));
    if (prevP) p = blendParams(prevP, p, 0.999);
    prevP = p;
    const { loc, Wroot } = solvePose(p, t, 20);
    const W = sec.step(dt, p, t, loc, Wroot, { excite: 0 });
    const a = performance.now();
    const lift = sec.solveSkirt(W, t);
    tSolve += performance.now() - a;
    sk.build(sec.flare, sec.sw, t, sec.flutter, lift);
    for (const v of Object.values(W)) if (v.some(Number.isNaN)) throw new Error('NaN pose at ' + t);
    worst = Math.max(worst, Math.max(...lift));
    let rate = 0; for (const [a0, a1, r] of d.sparks) if (t >= a0 && t <= a1) rate += r;
    if (rate) sec.emitParticles(W, t, dt, rate, 0, sec.omega, p.rp);
    nPts = Math.max(nPts, sec.updateParticles(dt, t, ptsBuf));
  }
  const ms = (performance.now() - ts) / (d.dur * 60);
  console.log(`${d.name.padEnd(20)} ${d.dur.toFixed(1)}s  ${ms.toFixed(2)} ms/frame (skirt ${(tSolve / (d.dur * 60)).toFixed(2)})  heading err max ${maxErr.toFixed(1)}°  max petal lift ${(worst / D2R).toFixed(0)}°  sparks ${nPts}`);
}
