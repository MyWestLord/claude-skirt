// "Fly brain": a ring-attractor model of the Drosophila head-direction circuit (E-PG / P-EN / Δ7)
// that integrates turn commands into her heading, plus a half-center oscillator (CPG) for stepping rhythm.
//
// This is a small computational model inspired by the fly's central complex
// (Seelig & Jayaraman 2015; Kim et al. 2017; Green et al. 2017), not a copy of the real connectome.

const TAU = 0.012;         // E-PG membrane time constant (s)
const J1 = 7.0, J0 = 4.0;  // local excitation (cosine) / global inhibition via Δ7
const J2 = 3.0;            // strength of the shifted P-EN -> E-PG projection
const KAPPA = 0.55;        // visual landmark (ring neuron) input
const BIAS = 0.4;
const GAIN = 0.0281;       // turn command (rad/s) -> P-EN drive, calibrated with tools/brain-calibrate.mjs

const f = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x);

export class FlyBrain {
  constructor(N = 16) {
    this.N = N;
    this.th = Float64Array.from({ length: N }, (_, i) => (2 * Math.PI * i) / N);
    this.Wc = new Float64Array(N * N); this.Ws = new Float64Array(N * N);
    for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
      const d = this.th[i] - this.th[j];
      this.Wc[i * N + j] = (J1 * Math.cos(d) - J0) / N;
      this.Ws[i * N + j] = (J2 * Math.sin(d)) / N;
    }
    this.r = new Float64Array(N); this.inp = new Float64Array(N);
    for (let i = 0; i < N; i++) this.r[i] = Math.max(0, Math.cos(this.th[i])) * 0.8;
    this.heading = 0; this.prevPhi = 0; this.target = 0;
    this.drive = 0; this.d7 = 0; this.visual = true;
    // CPG: Matsuoka half-center oscillator
    this.u = [0.2, 0.0]; this.v = [0, 0]; this.y = [0, 0]; this.kick = 0; this.jo = 0;
    this.trace = []; this.period = 0.5;
  }
  reset(angle) {
    for (let i = 0; i < this.N; i++) this.r[i] = Math.max(0, Math.cos(this.th[i] - angle)) * 0.8;
    this.heading = angle; this.prevPhi = Math.atan2(Math.sin(angle), Math.cos(angle)); this.target = angle;
  }
  // omega: commanded turn rate (rad/s); target: landmark heading (rad, unwrapped)
  step(dt, omega, target) {
    const N = this.N, r = this.r, inp = this.inp, h = 0.0005;
    const steps = Math.max(1, Math.min(200, Math.round(dt / h)));
    const hh = dt / steps;
    this.drive = omega * GAIN; this.target = target;
    const ct = Math.cos(target), st = Math.sin(target);
    for (let s = 0; s < steps; s++) {
      for (let i = 0; i < N; i++) {
        let a = 0;
        for (let j = 0; j < N; j++) a += (this.Wc[i * N + j] + this.drive * this.Ws[i * N + j]) * r[j];
        const c = Math.max(0, Math.cos(this.th[i]) * ct + Math.sin(this.th[i]) * st);
        inp[i] = a + (this.visual ? KAPPA * c * c * c * c : 0) + BIAS;
      }
      for (let i = 0; i < N; i++) r[i] += (hh / TAU) * (-r[i] + f(inp[i]));
    }
    let sx = 0, sy = 0, tot = 0;
    for (let i = 0; i < N; i++) { sx += r[i] * Math.cos(this.th[i]); sy += r[i] * Math.sin(this.th[i]); tot += r[i]; }
    const phi = Math.atan2(sy, sx);
    let d = phi - this.prevPhi; d = Math.atan2(Math.sin(d), Math.cos(d));
    this.heading += d; this.prevPhi = phi; this.d7 = tot / N;
    return this.heading;
  }
  // Half-center oscillator entrained by the music: a beat arrives through the antennae (Johnston's organ).
  stepCPG(dt, period, beat) {
    this.period = period;
    const tr = period / 6.3, ta = 2 * tr, w = 2.5, beta = 2.5, sIn = 1.0;
    if (beat) { this.kick = 0.9; this.jo = 1; }
    const steps = Math.max(1, Math.round(dt / 0.002)), hh = dt / steps;
    for (let s = 0; s < steps; s++) {
      for (let i = 0; i < 2; i++) {
        const k = i === 0 ? this.kick : 0;
        this.u[i] += (hh / tr) * (-this.u[i] - w * this.y[1 - i] - beta * this.v[i] + sIn + k);
        this.v[i] += (hh / ta) * (-this.v[i] + this.y[i]);
        this.y[i] = Math.max(0, this.u[i]);
      }
      this.kick *= Math.exp(-hh / 0.04);
    }
    this.jo *= Math.exp(-dt / 0.15);
    this.trace.push([this.y[0], this.y[1]]);
    if (this.trace.length > 120) this.trace.shift();
    return this.y[0] - this.y[1];
  }
}
