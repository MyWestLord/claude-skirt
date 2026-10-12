// Calibrates the P-EN gain of src/brain.js: measures bump speed vs. turn command with the landmark off.
import { FlyBrain } from '../src/brain.js';
const b = new FlyBrain();
b.visual = false;
for (let k = 0; k < 200; k++) b.step(1 / 60, 0, 0);
console.log('bump', Array.from(b.r).map((x) => x.toFixed(2)).join(' '), 'd7', b.d7.toFixed(3));
for (const om of [1, 3, 6, 12, 20, 28]) {
  const bb = new FlyBrain(); bb.visual = false;
  for (let k = 0; k < 60; k++) bb.step(1 / 60, 0, 0);
  const h0 = bb.heading; let T = 0;
  for (let k = 0; k < 60; k++) { bb.step(1 / 60, om, 0); T += 1 / 60; }
  const sp = (bb.heading - h0) / T;
  console.log('cmd %s rad/s -> bump %s rad/s  ratio %s  peak %s', om, sp.toFixed(2), (sp / om).toFixed(3), Math.max(...bb.r).toFixed(2));
}
// tracking test: triple pirouette (1080 deg in 1.5 s, smoothstep) with the landmark on
const c = new FlyBrain();
for (let k = 0; k < 60; k++) c.step(1 / 60, 0, 0);
let maxErr = 0, prev = 0;
for (let k = 0; k <= 150; k++) {
  const t = k / 60, s = Math.min(Math.max(t / 1.5, 0), 1), yd = (3 * s * s - 2 * s * s * s) * 6 * Math.PI;
  const om = (yd - prev) * 60; prev = yd;
  const h = c.step(1 / 60, om, yd);
  maxErr = Math.max(maxErr, Math.abs(h - yd));
}
console.log('triple pirouette max error %s deg, final %s deg', (maxErr * 180 / Math.PI).toFixed(1), ((c.heading - prev) * 180 / Math.PI).toFixed(2));
