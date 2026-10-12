// Web Audio synth: every instrument is built from oscillators and noise at play time. No samples.
export class Synth {
  constructor() { this.ctx = null; this.events = []; this.idx = 0; this.t0 = 0; this.timer = null; this.vol = 0.85; this.muted = false; }

  init() {
    if (this.ctx) { if (this.ctx.state === 'suspended') this.ctx.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    const ctx = this.ctx = new AC({ latencyHint: 'interactive' });
    this.comp = ctx.createDynamicsCompressor();
    this.comp.threshold.value = -14; this.comp.ratio.value = 3; this.comp.attack.value = 0.004; this.comp.release.value = 0.2;
    this.master = ctx.createGain(); this.master.gain.value = this.vol;
    this.master.connect(this.comp); this.comp.connect(ctx.destination);
    this.dry = ctx.createGain(); this.dry.connect(this.master);
    this.rev = ctx.createConvolver(); this.rev.buffer = this._ir(2.2);
    this.wet = ctx.createGain(); this.wet.gain.value = 0.32; this.wet.connect(this.rev); this.rev.connect(this.master);
    this.noise = this._noise(2.0);
  }
  get now() { return this.ctx ? this.ctx.currentTime : performance.now() / 1000; }
  get latency() { return this.ctx ? (this.ctx.outputLatency || this.ctx.baseLatency || 0) : 0; }
  setMuted(m) { this.muted = m; if (this.master) this.master.gain.setTargetAtTime(m ? 0 : this.vol, this.ctx.currentTime, 0.05); }

  _noise(sec) {
    const b = this.ctx.createBuffer(1, Math.floor(this.ctx.sampleRate * sec), this.ctx.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return b;
  }
  _ir(sec) {
    const sr = this.ctx.sampleRate, n = Math.floor(sr * sec), b = this.ctx.createBuffer(2, n, sr);
    for (let c = 0; c < 2; c++) {
      const d = b.getChannelData(c), pre = Math.floor(sr * (0.012 + c * 0.005));
      for (let i = pre; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.exp(-(i - pre) / (sr * 0.42));
    }
    return b;
  }
  _out(node, pan = 0, send = 0.5) {
    const p = this.ctx.createStereoPanner ? this.ctx.createStereoPanner() : null;
    if (p) { p.pan.value = Math.max(-1, Math.min(1, pan)); node.connect(p); node = p; }
    node.connect(this.dry);
    if (send > 0) { const s = this.ctx.createGain(); s.gain.value = send; node.connect(s); s.connect(this.wet); }
  }
  _osc(type, f, t, stop) { const o = this.ctx.createOscillator(); o.type = type; o.frequency.setValueAtTime(f, t); o.start(t); o.stop(stop); return o; }
  _env(t, peak, attack, tau, dur, rel) {
    const g = this.ctx.createGain(), G = g.gain;
    G.setValueAtTime(0, t); G.linearRampToValueAtTime(peak, t + attack);
    if (tau) G.setTargetAtTime(0, t + attack, tau);
    if (dur != null) { if (!tau) G.setValueAtTime(peak, t + Math.max(attack, dur)); G.setTargetAtTime(0, t + Math.max(attack, dur), rel); }
    return g;
  }
  _noiseSrc(t, dur) { const s = this.ctx.createBufferSource(); s.buffer = this.noise; s.loop = true; s.start(t, Math.random() * 1.5); s.stop(t + dur); return s; }

  // ---- instruments
  cel(t, f, dur, vel, pan = 0.15) {
    const d = 1.6 + 600 / f, end = t + dur + 1.4, mix = this.ctx.createGain(); mix.gain.value = 0.22 * vel;
    [[1, 1, d / 2.2], [2, 0.38, 0.2], [3.01, 0.14, 0.125], [4.17, 0.09, 0.07], [6.3, 0.05, 0.033]].forEach(([m, a, tau]) => {
      if (f * m > 16000) return;
      const o = this._osc('sine', f * m, t, end), g = this._env(t, a, 0.002, tau, dur, 0.3);
      o.connect(g); g.connect(mix);
    });
    this._out(mix, pan, 0.45);
  }
  plk(t, f, dur, vel, pan = -0.2) {
    const end = t + Math.min(dur, 1.2) + 0.5, o = this._osc('triangle', f, t, end), o2 = this._osc('sine', f * 2, t, end);
    const lp = this.ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(Math.min(f * 8, 9000), t);
    lp.frequency.setTargetAtTime(f * 1.6, t, 0.06);
    const tau = f < 150 ? 0.45 : 0.22, g = this._env(t, 0.42 * vel, 0.003, tau, Math.min(dur, 1.2), 0.08);
    const g2 = this.ctx.createGain(); g2.gain.value = 0.25;
    o.connect(lp); o2.connect(g2); g2.connect(lp); lp.connect(g); this._out(g, pan, 0.25);
  }
  harp(t, f, dur, vel, pan = -0.3) {
    const end = t + dur + 1.6, o = this._osc('triangle', f, t, end), o2 = this._osc('sine', f * 2.002, t, end);
    const g = this._env(t, 0.35 * vel, 0.002, 0.7, null), g2 = this._env(t, 0.12 * vel, 0.002, 0.25, null);
    o.connect(g); o2.connect(g2); this._out(g, pan, 0.5); this._out(g2, pan, 0.5);
  }
  lead(t, f, dur, vel) { // reedy oboe with delayed vibrato
    const end = t + dur + 0.6, o = this._osc('sawtooth', f, t, end);
    const lfo = this._osc('sine', 5.4, t, end), ld = this.ctx.createGain();
    ld.gain.setValueAtTime(0, t); ld.gain.linearRampToValueAtTime(f * 0.006, t + Math.min(0.35, dur));
    lfo.connect(ld); ld.connect(o.frequency);
    const lp = this.ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2400; lp.Q.value = 2.5;
    const bp = this.ctx.createBiquadFilter(); bp.type = 'peaking'; bp.frequency.value = 1150; bp.gain.value = 7;
    const g = this._env(t, 0.16 * vel, 0.07, 0, dur, 0.12);
    o.connect(lp); lp.connect(bp); bp.connect(g); this._out(g, 0.05, 0.55);
  }
  buzz(t, f, dur, vel) { // kazoo-like wingbeat buzz
    const end = t + dur + 0.3, o = this._osc('sawtooth', f, t, end), o2 = this._osc('square', f * 1.004, t, end);
    const am = this._osc('sine', 31, t, end), amg = this.ctx.createGain(); amg.gain.value = 0.35;
    const bp = this.ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = f * 3; bp.Q.value = 1.4;
    const g = this._env(t, 0.13 * vel, 0.02, 0, dur, 0.05), trem = this.ctx.createGain(); trem.gain.value = 0.8;
    am.connect(amg); amg.connect(trem.gain);
    const m = this.ctx.createGain(); m.gain.value = 0.5;
    o.connect(bp); o2.connect(m); m.connect(bp); bp.connect(trem); trem.connect(g); this._out(g, 0.1, 0.3);
  }
  pad(t, fs, dur, vel) {
    const end = t + dur + 1.0, g = this._env(t, vel * 0.9 / fs.length, 0.3, 0, dur, 0.35);
    const lp = this.ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 1100;
    for (const f of fs) for (const det of [-6, 6]) { const o = this._osc('sawtooth', f, t, end); o.detune.value = det; o.connect(lp); }
    lp.connect(g); this._out(g, 0, 0.6);
  }
  brass(t, fs, dur, vel) {
    const end = t + dur + 0.6, g = this._env(t, vel * 0.5 / fs.length, 0.05, 0, dur, 0.25);
    const lp = this.ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(400, t); lp.frequency.linearRampToValueAtTime(2600, t + 0.09);
    lp.frequency.setTargetAtTime(1400, t + 0.1, 0.3);
    for (const f of fs) for (const det of [-5, 5]) { const o = this._osc('sawtooth', f, t, end); o.detune.value = det; o.connect(lp); }
    lp.connect(g); this._out(g, 0, 0.45);
  }
  bass(t, f, dur, vel) {
    const end = t + dur + 0.3, o = this._osc('sawtooth', f, t, end), o2 = this._osc('square', f * 0.5, t, end);
    const lp = this.ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(1400, t); lp.frequency.setTargetAtTime(300, t, 0.07); lp.Q.value = 3;
    const g = this._env(t, 0.3 * vel, 0.004, 0.2, dur, 0.05), m = this.ctx.createGain(); m.gain.value = 0.4;
    o.connect(lp); o2.connect(m); m.connect(lp); lp.connect(g); this._out(g, 0, 0.1);
  }
  kick(t, vel) {
    const o = this._osc('sine', 150, t, t + 0.5); o.frequency.setTargetAtTime(44, t, 0.035);
    const g = this._env(t, 0.85 * vel, 0.002, 0.11, null); o.connect(g); this._out(g, 0, 0.05);
  }
  hat(t, vel) {
    const s = this._noiseSrc(t, 0.12), hp = this.ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 7500;
    const g = this._env(t, 0.32 * vel, 0.001, 0.025, null); s.connect(hp); hp.connect(g); this._out(g, 0.25, 0.1);
  }
  snare(t, vel) {
    const s = this._noiseSrc(t, 0.3), bp = this.ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 1900; bp.Q.value = 0.7;
    const g = this._env(t, 0.5 * vel, 0.001, 0.07, null); s.connect(bp); bp.connect(g); this._out(g, -0.05, 0.3);
    const o = this._osc('triangle', 190, t, t + 0.25), g2 = this._env(t, 0.35 * vel, 0.001, 0.05, null); o.connect(g2); this._out(g2, 0, 0.1);
  }
  wood(t, vel, f = 900) {
    const o = this._osc('sine', f, t, t + 0.2), o2 = this._osc('square', f * 2.7, t, t + 0.1);
    const g = this._env(t, 0.4 * vel, 0.001, 0.028, null), g2 = this._env(t, 0.05 * vel, 0.001, 0.012, null);
    o.connect(g); o2.connect(g2); this._out(g, 0.3, 0.3); this._out(g2, 0.3, 0.3);
  }
  timp(t, f, vel) {
    const o = this._osc('sine', f * 1.06, t, t + 1.8); o.frequency.setTargetAtTime(f, t, 0.04);
    const g = this._env(t, 0.55 * vel, 0.004, 0.5, null); o.connect(g); this._out(g, -0.1, 0.4);
    const s = this._noiseSrc(t, 0.2), lp = this.ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 500;
    const g2 = this._env(t, 0.3 * vel, 0.001, 0.04, null); s.connect(lp); lp.connect(g2); this._out(g2, 0, 0.2);
  }
  crash(t, vel) {
    const s = this._noiseSrc(t, 2.5), hp = this.ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 4200;
    const g = this._env(t, 0.22 * vel, 0.002, 0.7, null); s.connect(hp); hp.connect(g); this._out(g, 0.2, 0.5);
  }
  whoosh(t, dur, vel) {
    const s = this._noiseSrc(t, dur + 0.1), bp = this.ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 1.2;
    bp.frequency.setValueAtTime(500, t); bp.frequency.linearRampToValueAtTime(2600, t + dur * 0.5); bp.frequency.linearRampToValueAtTime(700, t + dur);
    const g = this.ctx.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.5 * vel, t + dur * 0.5); g.gain.linearRampToValueAtTime(0, t + dur);
    s.connect(bp); bp.connect(g); this._out(g, 0, 0.3);
  }
  song(t, dur) { // fruit-fly courtship song: pulse trains (~35 ms apart) alternating with a ~160 Hz sine song
    const sr = this.ctx.sampleRate, n = Math.floor(sr * dur), b = this.ctx.createBuffer(1, n, sr), d = b.getChannelData(0);
    let x = 0, mode = 0, next = 0;
    while (x < n) {
      if (x >= next) { mode = 1 - mode; next = x + Math.floor(sr * (mode ? 0.45 + Math.random() * 0.4 : 0.3 + Math.random() * 0.3)); }
      if (mode) { // pulse song
        const w = Math.floor(sr * 0.009);
        for (let i = 0; i < w && x + i < n; i++) { const u = i / w - 0.5; d[x + i] += Math.exp(-u * u * 18) * Math.sin(2 * Math.PI * 250 * i / sr) * 0.9; }
        x += Math.floor(sr * 0.035);
      } else { // sine song
        const w = Math.min(next - x, n - x);
        for (let i = 0; i < w; i++) d[x + i] += Math.sin(2 * Math.PI * 160 * (x + i) / sr) * 0.35 * Math.sin(Math.PI * i / w);
        x += w;
      }
    }
    const s = this.ctx.createBufferSource(); s.buffer = b; s.start(t);
    const hp = this.ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 120;
    const g = this.ctx.createGain(); g.gain.value = 0.55; s.connect(hp); hp.connect(g); this._out(g, -0.2, 0.25);
  }
  applause(t, amount) { // a crowd of synthetic claps
    const sr = this.ctx.sampleRate, dur = 1.2 + 2.2 * amount, n = Math.floor(sr * dur), b = this.ctx.createBuffer(2, n, sr);
    const claps = Math.floor(60 + 260 * amount);
    for (let c = 0; c < 2; c++) {
      const d = b.getChannelData(c);
      for (let k = 0; k < claps; k++) {
        const x0 = Math.floor(Math.pow(Math.random(), 1.3) * (n - sr * 0.03)), w = Math.floor(sr * (0.006 + Math.random() * 0.01)), a = 0.25 + Math.random() * 0.5;
        for (let i = 0; i < w; i++) d[x0 + i] += (Math.random() * 2 - 1) * a * Math.exp(-i / (w * 0.3));
      }
    }
    const s = this.ctx.createBufferSource(); s.buffer = b; s.start(t);
    const bp = this.ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 1500; bp.Q.value = 0.6;
    const g = this.ctx.createGain(); g.gain.setValueAtTime(0.35 + 0.35 * amount, t); g.gain.setTargetAtTime(0, t + dur * 0.6, dur * 0.25);
    s.connect(bp); bp.connect(g); this._out(g, 0, 0.6);
  }
  blip(kind) {
    if (!this.ctx) return;
    const t = this.ctx.currentTime + 0.005;
    if (kind === 'perfect') { this.cel(t, 2637, 0.1, 0.35, 0.3); this.cel(t + 0.05, 3520, 0.1, 0.25, 0.3); }
    else if (kind === 'good') this.cel(t, 1975, 0.1, 0.3, 0.3);
    else if (kind === 'miss') this.wood(t, 0.4, 330);
    else if (kind === 'order') { this.cel(t, 1318, 0.08, 0.3); this.cel(t + 0.07, 1760, 0.12, 0.3); }
    else if (kind === 'bravo') { [1318, 1661, 1975, 2637].forEach((f, i) => this.cel(t + i * 0.06, f, 0.3, 0.35)); this.crash(t, 0.4); }
  }

  // ---- sequencing
  play(events, startAt) {
    this.stop();
    this.events = events; this.idx = 0; this.t0 = startAt;
    const tick = () => {
      const horizon = this.ctx.currentTime + 0.18;
      while (this.idx < this.events.length && this.t0 + this.events[this.idx][0] < horizon) {
        const e = this.events[this.idx++], t = Math.max(this.t0 + e[0], this.ctx.currentTime);
        try { this._fire(t, e); } catch (err) { /* a single bad event must never stop the music */ }
      }
    };
    tick();
    this.timer = setInterval(tick, 25);
  }
  _fire(t, e) {
    const [, k, a, b, c, d] = e;
    switch (k) {
      case 'cel': return this.cel(t, a, b, c, d);
      case 'plk': return this.plk(t, a, b, c, d);
      case 'harp': return this.harp(t, a, b, c, d);
      case 'lead': return this.lead(t, a, b, c);
      case 'buzz': return this.buzz(t, a, b, c);
      case 'pad': return this.pad(t, a, b, c);
      case 'brass': return this.brass(t, a, b, c);
      case 'bass': return this.bass(t, a, b, c);
      case 'kick': return this.kick(t, a);
      case 'hat': return this.hat(t, a);
      case 'snare': return this.snare(t, a);
      case 'wood': return this.wood(t, a, b);
      case 'timp': return this.timp(t, a, b);
      case 'crash': return this.crash(t, a);
      case 'whoosh': return this.whoosh(t, a, b);
      case 'song': return this.song(t, a);
    }
  }
  stop() { if (this.timer) clearInterval(this.timer); this.timer = null; this.events = []; }
}
