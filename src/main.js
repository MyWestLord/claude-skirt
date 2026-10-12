// Claude Skirt: order a dance, clap on the beat, watch a fly-brain model steer her spins.
import { DANCES } from './dances.data.js';
import { buildParts, Skirt, ORANGE } from './geo.js';
import { Renderer } from './render.js';
import { Timeline, evalParams, blendParams, solvePose, Secondary } from './anim.js';
import { FlyBrain } from './brain.js';
import { Synth } from './audio.js';
import { D2R, clamp, lerp, smooth, perspective, lookAt, m4, m4mul, m4pt, m4R, m3v, m4t, sub } from './math.js';
import { PIV } from './rig.js';

const $ = (id) => document.getElementById(id);
const FPS = 30;
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage blocked: fine */ } },
};

// ------------------------------------------------------------------ scene
const canvas = $('gl');
let R;
try { R = new Renderer(canvas); } catch (e) {
  const d = document.createElement('div'); d.className = 'err';
  d.textContent = 'This viewport needs WebGL2, which this browser does not provide. Try a recent Chrome, Safari or Firefox.';
  canvas.replaceWith(d); throw e;
}
const parts = buildParts();
let nVerts = 0;
for (const q of parts) { R.addPart(q.bone, q.m, q.color, q.spec); nVerts += q.m.P.length / 3; }
const skirt = new Skirt();
skirt.build(0, 0, 0, 0.4, null);
R.setSkirt(skirt);
$('o-parts').textContent = parts.length + 1;
$('o-verts').textContent = (nVerts + skirt.P.length / 3).toLocaleString('en-US');

const brain = new FlyBrain();
const sec = new Secondary(skirt);
const synth = new Synth();
const ptsBuf = new Float32Array(2500 * 8);

const IDLE_KEY = { ...DANCES.dances[1].keys[0] };
const idleTl = new Timeline({ keys: [{ ...IDLE_KEY, t: 0, h: 1 }, { t: 1, h: 1 }], dur: 1, jumps: [] });

const S = {
  playing: null, queue: [], yawHome: 0, prevYawD: 0, last: 0, fade: null, lastP: null,
  score: 0, combo: 0, bravo: 0, excite: 0, best: store.get('claude-skirt-best', {}),
  cam: { auto: true, az: 25, el: 3, dist: 4.4, tz: 1.03, txy: [0, 0], snap: null },
  frame: 0, fps: 60, fpsT: 0, fpsN: 0, cpgAmp: 0.3, beatIdx: 0,
};
const clock = () => (synth.ctx ? synth.ctx.currentTime : performance.now() / 1000);

// ------------------------------------------------------------------ dance menu + queue
const ALL = [...DANCES.dances, { ...DANCES.freestyle[0], id: 'free', variants: DANCES.freestyle }];
const fmtDur = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
const cards = {};
ALL.forEach((d, i) => {
  const el = document.createElement('div');
  el.className = 'dance';
  el.innerHTML = `<span class="no">${['I', 'II', 'III', 'IV', 'V'][i]}</span><span class="name"></span>
    <button type="button" id="order-${d.id}">Order</button>
    <span class="meta"></span><span class="desc"></span><span class="bar"></span>`;
  el.querySelector('.name').textContent = d.name;
  el.querySelector('.desc').textContent = d.sub;
  el.querySelector('button').addEventListener('click', () => order(d));
  $('dances').appendChild(el);
  cards[d.id] = el;
});
function renderMeta() {
  for (const d of ALL) {
    const b = S.best[d.id];
    cards[d.id].querySelector('.meta').innerHTML = `${d.bpm} BPM · ${d.meter}/4 · ${fmtDur(d.dur)} · ${d.musicName}` + (b != null ? ` · <span class="best">best ${b}%</span>` : '');
  }
}
renderMeta();

function order(d) {
  synth.init();
  synth.blip('order');
  if (!S.playing) startDance(d);
  else if (S.queue.length < 6) S.queue.push(d);
  renderQueue();
}
function renderQueue() {
  const q = $('queue');
  q.innerHTML = '';
  if (!S.queue.length) { q.innerHTML = '<span class="empty">Nothing queued. Order more than one dance and they play in order.</span>'; return; }
  S.queue.forEach((d, i) => {
    const row = document.createElement('div'); row.className = 'row';
    const s = document.createElement('span'); s.textContent = `${i + 1}. ${d.name}`;
    const x = document.createElement('button'); x.type = 'button'; x.textContent = '×'; x.setAttribute('aria-label', `Remove ${d.name} from the queue`);
    x.addEventListener('click', () => { S.queue.splice(i, 1); renderQueue(); });
    row.append(s, x); q.appendChild(row);
  });
}

function startDance(d) {
  synth.init();
  const pick = d.variants ? d.variants[Math.floor(Math.random() * d.variants.length)] : d;
  const now = clock() + 0.15;
  S.fade = S.lastP ? { from: S.lastP, t0: now - 0.15, dur: 0.6 } : null;
  S.playing = { d: { ...pick, id: d.id, name: d.name }, tl: new Timeline(pick), start: now, judged: new Set(), stats: { perfect: 0, good: 0, miss: 0 } };
  S.beatIdx = 0;
  synth.play(pick.music, now);
  for (const id in cards) cards[id].classList.toggle('playing', id === d.id);
  $('now-eyebrow').textContent = 'Now dancing';
  $('now-title').textContent = d.name;
  $('hint').hidden = true;
  $('endf').textContent = Math.round(pick.dur * FPS);
}

function finishDance(skipped) {
  const P = S.playing;
  if (!P) return;
  const keys = P.tl.F.yaw;
  S.yawHome += Math.round(keys[keys.length - 1][0] / 360) * 360;
  synth.stop();
  const st = P.stats, total = P.d.beats.length;
  const acc = total ? Math.round((100 * (st.perfect + 0.6 * st.good)) / total) : 0;
  if (!skipped) {
    synth.applause(clock() + 0.05, clamp(0.25 + acc / 100, 0, 1));
    if (st.perfect + st.good > 0) {
      showJudge(acc >= 70 ? `Bravo! ${acc}% on the beat` : `${acc}% on the beat`, acc >= 70);
      if ((S.best[P.d.id] || 0) < acc) { S.best[P.d.id] = acc; store.set('claude-skirt-best', S.best); renderMeta(); }
    }
  }
  cards[P.d.id].classList.remove('playing');
  cards[P.d.id].querySelector('.bar').style.width = '0';
  S.playing = null;
  S.fade = S.lastP ? { from: S.lastP, t0: clock(), dur: skipped ? 0.7 : 0.2 } : null;
  $('now-eyebrow').textContent = 'On stage';
  $('now-title').textContent = 'Claude Skirt';
  $('now-move').textContent = 'waiting for a request';
  if (S.queue.length) { const nx = S.queue.shift(); renderQueue(); setTimeout(() => { if (!S.playing) startDance(nx); }, skipped ? 400 : 900); }
}
$('t-skip').addEventListener('click', () => finishDance(true));

// ------------------------------------------------------------------ rhythm game
let judgeTimer = 0;
function showJudge(text, hot) {
  const j = $('judge');
  j.textContent = text; j.classList.toggle('perfect', !!hot); j.classList.add('show');
  clearTimeout(judgeTimer); judgeTimer = setTimeout(() => j.classList.remove('show'), 900);
}
function clap() {
  synth.init();
  const P = S.playing;
  if (!P) { showJudge('Order a dance first'); return; }
  const t = clock() - P.start - synth.latency, B = P.d.beats;
  let best = -1, bd = 1e9;
  for (let i = Math.max(0, S.beatIdx - 3); i < B.length && B[i] < t + 0.5; i++) {
    const d = Math.abs(B[i] - t);
    if (!P.judged.has(i) && d < bd) { bd = d; best = i; }
  }
  if (best >= 0 && bd <= 0.07) hit(P, best, 'perfect');
  else if (best >= 0 && bd <= 0.14) hit(P, best, 'good');
  else { S.combo = 0; P.stats.miss++; synth.blip('miss'); showJudge('Miss'); }
  updateScore();
}
function hit(P, i, kind) {
  P.judged.add(i); P.stats[kind]++;
  S.combo++;
  S.score += Math.round((kind === 'perfect' ? 100 : 50) * (1 + Math.min(S.combo, 30) / 10));
  S.bravo += kind === 'perfect' ? 0.09 : 0.05;
  synth.blip(kind);
  showJudge(kind === 'perfect' ? 'Perfect' : 'Good', kind === 'perfect');
  if (S.bravo >= 1) {
    S.bravo = 0; S.excite = 2.5; synth.blip('bravo'); showJudge('BRAVO!', true);
    S.bravoBurst = true;
  }
}
function updateScore() {
  $('score').textContent = S.score.toLocaleString('en-US');
  $('combo').textContent = '×' + S.combo;
  $('bravo').style.width = Math.round(S.bravo * 100) + '%';
}
$('clap').addEventListener('pointerdown', (e) => { e.preventDefault(); clap(); });
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && !e.repeat && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLButtonElement)) { e.preventDefault(); clap(); }
  else if (/^Digit[1-5]$/.test(e.code)) order(ALL[Number(e.code.slice(5)) - 1]);
});

// ------------------------------------------------------------------ sidebar tabs + toggles
document.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-selected', x === b); });
  document.querySelectorAll('.tabpanel').forEach((p) => { p.hidden = p.id !== 'tab-' + b.dataset.tab; });
}));
let gridOn = true, gizmoOn = true;
$('btn-overlays').addEventListener('click', (e) => { gridOn = !gridOn; e.currentTarget.classList.toggle('on', gridOn); e.currentTarget.setAttribute('aria-pressed', gridOn); });
$('btn-gizmo').addEventListener('click', (e) => { gizmoOn = !gizmoOn; e.currentTarget.classList.toggle('on', gizmoOn); e.currentTarget.setAttribute('aria-pressed', gizmoOn); $('gizmo').style.visibility = gizmoOn ? '' : 'hidden'; document.querySelector('.nav').style.visibility = gizmoOn ? '' : 'hidden'; });
$('mute').addEventListener('click', (e) => {
  synth.init(); const m = !synth.muted; synth.setMuted(m);
  e.currentTarget.setAttribute('aria-pressed', m); $('mute-wave').style.display = m ? 'none' : '';
});

// ------------------------------------------------------------------ camera: auto follow, orbit, zoom, gizmo snaps
const cam = S.cam;
const setAuto = (on) => { cam.auto = on; $('autocam').classList.toggle('on', on); $('autocam').setAttribute('aria-pressed', on); };
$('autocam').addEventListener('click', () => setAuto(!cam.auto));
$('zin').addEventListener('click', () => { setAuto(false); cam.dist = clamp(cam.dist * 0.85, 1.6, 14); });
$('zout').addEventListener('click', () => { setAuto(false); cam.dist = clamp(cam.dist / 0.85, 1.6, 14); });
const ptrs = new Map(); let pinch0 = 0;
canvas.addEventListener('pointerdown', (e) => { canvas.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]); if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; pinch0 = Math.hypot(a[0] - b[0], a[1] - b[1]); } });
canvas.addEventListener('pointermove', (e) => {
  if (!ptrs.has(e.pointerId)) return;
  const p = ptrs.get(e.pointerId), dx = e.clientX - p[0], dy = e.clientY - p[1];
  ptrs.set(e.pointerId, [e.clientX, e.clientY]);
  setAuto(false); cam.snap = null;
  if (ptrs.size === 1) { cam.az -= dx * 0.4; cam.el = clamp(cam.el + dy * 0.3, -60, 85); }
  else if (ptrs.size === 2) { const [a, b] = [...ptrs.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]); if (pinch0) cam.dist = clamp(cam.dist * pinch0 / d, 1.6, 14); pinch0 = d; }
});
const up = (e) => { ptrs.delete(e.pointerId); pinch0 = 0; };
canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);
canvas.addEventListener('wheel', (e) => { e.preventDefault(); setAuto(false); cam.dist = clamp(cam.dist * Math.exp(e.deltaY * 0.0012), 1.6, 14); }, { passive: false });
canvas.addEventListener('dblclick', () => setAuto(true));

let gizmoHits = [];
$('gizmo').addEventListener('click', (e) => {
  const r = e.currentTarget.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * 240, y = (e.clientY - r.top) / r.height * 240;
  let best = null, bd = 30;
  for (const h of gizmoHits) { const d = Math.hypot(h.x - x, h.y - y); if (d < bd) { bd = d; best = h; } }
  if (!best) return;
  const V = { '+X': [-90, 0], '-X': [90, 0], '+Y': [180, 0], '-Y': [0, 0], '+Z': [cam.az, 89], '-Z': [cam.az, -89] }[best.id];
  setAuto(false);
  cam.snap = { az0: cam.az, el0: cam.el, az1: cam.az + ((((V[0] - cam.az) % 360) + 540) % 360 - 180), el1: V[1], t0: performance.now() };
});

function autoCam(t, dt) {
  const P = S.playing;
  if (P && P.d.cam) {
    const C = P.d.cam, ts = C.map((c) => c[0]);
    let k = 0; while (k < ts.length - 2 && ts[k + 1] <= t) k++;
    const s = smooth((t - ts[k]) / (ts[k + 1] - ts[k])), a = C[k], b = C[k + 1];
    return { az: lerp(a[1], b[1], s), el: lerp(a[2], b[2], s), dist: lerp(a[3], b[3], s), tz: lerp(a[4], b[4], s) };
  }
  const tt = clock();
  const spin = Math.min(Math.abs(sec.omega || 0) / 900, 1);
  return { az: 18 + 14 * Math.sin(tt * 0.13), el: 6 + 2.5 * Math.sin(tt * 0.17), dist: 4.5 - 0.45 * spin + (P ? 0.4 : 0), tz: 1.05 };
}

// ------------------------------------------------------------------ 2D overlays: gizmo, 3D cursor, timeline, brain
const gz = $('gizmo').getContext('2d');
function drawGizmo(V) {
  const c = gz, Wd = 240, cx = 120, cy = 120, Rr = 82, cr = 19;
  c.clearRect(0, 0, Wd, Wd);
  const cols = { X: '#ff3352', Y: '#8bdc00', Z: '#2890ff' }, items = [];
  ['X', 'Y', 'Z'].forEach((ax, i) => {
    const v = [V[i], V[4 + i], V[8 + i]];
    items.push({ z: v[2], ax, sg: 1, v }); items.push({ z: -v[2], ax, sg: -1, v: v.map((x) => -x) });
  });
  items.sort((a, b) => a.z - b.z);
  gizmoHits = [];
  c.font = '600 24px Inter, system-ui, sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
  for (const it of items) {
    const px = cx + it.v[0] * Rr, py = cy - it.v[1] * Rr;
    gizmoHits.push({ id: (it.sg > 0 ? '+' : '-') + it.ax, x: px, y: py });
    if (it.sg > 0) {
      c.strokeStyle = cols[it.ax]; c.lineWidth = 4.5; c.beginPath(); c.moveTo(cx, cy); c.lineTo(px, py); c.stroke();
      c.fillStyle = cols[it.ax]; c.beginPath(); c.arc(px, py, cr, 0, 7); c.fill();
      c.fillStyle = '#111'; c.fillText(it.ax, px, py + 1);
    } else {
      c.fillStyle = cols[it.ax] + '55'; c.strokeStyle = cols[it.ax]; c.lineWidth = 3.5;
      c.beginPath(); c.arc(px, py, cr - 1, 0, 7); c.fill(); c.stroke();
    }
  }
}
const ov = $('ov'), oc = ov.getContext('2d');
const CURSOR = [-1.9, 2.6, 1.9], ORIGIN = [-2.4, 3.0, 0.9];
function drawOverlay(VP, w, h) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  if (ov.width !== Math.round(w * dpr)) { ov.width = Math.round(w * dpr); ov.height = Math.round(h * dpr); }
  oc.setTransform(dpr, 0, 0, dpr, 0, 0); oc.clearRect(0, 0, w, h);
  if (!gridOn) return;
  const proj = (p) => { const c = [0, 1, 2, 3].map((r) => VP[r * 4] * p[0] + VP[r * 4 + 1] * p[1] + VP[r * 4 + 2] * p[2] + VP[r * 4 + 3]); return c[3] > 0.05 ? [(c[0] / c[3] * 0.5 + 0.5) * w, (1 - (c[1] / c[3] * 0.5 + 0.5)) * h] : null; };
  const o = proj(ORIGIN);
  if (o) { oc.fillStyle = '#141414'; oc.beginPath(); oc.arc(o[0], o[1], 4.5, 0, 7); oc.fill(); oc.fillStyle = '#ffa028'; oc.beginPath(); oc.arc(o[0], o[1], 3.2, 0, 7); oc.fill(); }
  const q = proj(CURSOR);
  if (q) {
    for (let k = 0; k < 8; k++) { oc.strokeStyle = k % 2 ? '#fff' : '#ff3c3c'; oc.lineWidth = 2; oc.beginPath(); oc.arc(q[0], q[1], 10, k * Math.PI / 4, (k + 1) * Math.PI / 4); oc.stroke(); }
    oc.strokeStyle = '#0c0c0c'; oc.lineWidth = 1.6;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { oc.beginPath(); oc.moveTo(q[0] + dx * 4.5, q[1] + dy * 4.5); oc.lineTo(q[0] + dx * 17, q[1] + dy * 17); oc.stroke(); }
  }
}

const tlc = $('tl'), tx = tlc.getContext('2d');
function drawTimeline(t) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2), w = tlc.clientWidth, h = tlc.clientHeight;
  if (tlc.width !== Math.round(w * dpr) || tlc.height !== Math.round(h * dpr)) { tlc.width = Math.round(w * dpr); tlc.height = Math.round(h * dpr); }
  const c = tx; c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.fillStyle = '#282828'; c.fillRect(0, 0, w, h);
  const P = S.playing, dur = P ? P.d.dur : 8, frames = dur * FPS, x0 = 14, x1 = w - 14;
  const X = (sec) => x0 + (x1 - x0) * (sec * FPS) / frames;
  const step = frames / ((x1 - x0) / 46) > 50 ? 100 : frames / ((x1 - x0) / 46) > 20 ? 50 : 10;
  c.font = '500 10px JetBrains Mono, ui-monospace, monospace'; c.textBaseline = 'top';
  for (let f = 0; f <= frames; f += 10) {
    const x = Math.round(X(f / FPS)) + 0.5, big = f % step === 0;
    c.strokeStyle = big ? '#3c3c3c' : '#313131'; c.beginPath(); c.moveTo(x, big ? 0 : 0); c.lineTo(x, big ? h : 7); c.stroke();
    if (big) { c.fillStyle = '#8a8a8a'; c.fillText(String(f), x + 3, 2); }
  }
  if (P) {
    const yk = h * 0.42;
    for (const kt of P.tl.ts) { // keyframe diamonds
      const x = X(kt); c.fillStyle = '#d8d8d8'; c.strokeStyle = '#111';
      c.beginPath(); c.moveTo(x, yk - 5); c.lineTo(x + 5, yk); c.lineTo(x, yk + 5); c.lineTo(x - 5, yk); c.closePath(); c.fill(); c.stroke();
    }
    const yb = h * 0.78;
    P.d.beats.forEach((bt, i) => { // beat lane for the clap game
      const x = X(bt), judged = P.judged.has(i), past = bt < t - 0.14;
      c.fillStyle = judged ? '#f0a080' : past ? '#555' : '#d97757';
      c.fillRect(x - 1.5, yb - (judged ? 6 : 4), 3, judged ? 12 : 8);
    });
    c.fillStyle = '#9a9a9a'; c.font = '500 10px Inter, system-ui, sans-serif'; c.textBaseline = 'bottom';
    for (const [mt, label] of P.d.marks || []) { const x = X(mt); c.beginPath(); c.moveTo(x, h - 1); c.lineTo(x - 4, h - 7); c.lineTo(x + 4, h - 7); c.fill(); }
  } else {
    c.fillStyle = '#7d7d7d'; c.font = '500 11px Inter, system-ui, sans-serif'; c.textBaseline = 'middle';
    c.fillText('No keyframes yet: order a dance from the sidebar', x0 + 4, h * 0.6);
  }
  const x = Math.round(X(P ? clamp(t, 0, dur) : 0)) + 0.5;
  c.strokeStyle = '#4772b3'; c.lineWidth = 2; c.beginPath(); c.moveTo(x, 0); c.lineTo(x, h); c.stroke(); c.lineWidth = 1;
}

const bc = $('brain'), bx = bc.getContext('2d');
function drawBrain(head, target) {
  const c = bx, w = 560, h = 604, cx = 280, cy = 236, R0 = 120, R1 = 190;
  c.clearRect(0, 0, w, h);
  c.fillStyle = '#1f1f1f'; c.fillRect(0, 0, w, h);
  const N = brain.N, ang = (a) => -a - Math.PI / 2;
  for (let i = 0; i < N; i++) {
    const a0 = ang(brain.th[i] + Math.PI / N), a1 = ang(brain.th[i] - Math.PI / N), r = clamp(brain.r[i], 0, 1);
    const col = `rgb(${Math.round(60 + 195 * r)}, ${Math.round(56 + 120 * r * r)}, ${Math.round(58 + 60 * r * r * r)})`;
    c.fillStyle = col; c.beginPath(); c.arc(cx, cy, R1, a0, a1); c.arc(cx, cy, R0, a1, a0, true); c.closePath(); c.fill();
    c.strokeStyle = '#1f1f1f'; c.lineWidth = 3; c.stroke();
  }
  c.fillStyle = '#e8e8e8'; c.font = '600 22px Inter, system-ui, sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
  c.fillText('E-PG', cx, cy - 22);
  c.font = '500 20px JetBrains Mono, ui-monospace, monospace'; c.fillStyle = '#a9a9a9';
  c.fillText(`${(((head % 360) + 360) % 360).toFixed(0)}°`, cx, cy + 8);
  const ha = ang(head * D2R);
  c.strokeStyle = '#ffffff'; c.lineWidth = 4; c.beginPath(); c.moveTo(cx + Math.cos(ha) * 30, cy + Math.sin(ha) * 30 + 30); c.lineTo(cx + Math.cos(ha) * (R0 - 8), cy + Math.sin(ha) * (R0 - 8)); c.stroke();
  const ta = ang(target * D2R);
  if (brain.visual) { c.fillStyle = '#5680c2'; c.beginPath(); const tx0 = cx + Math.cos(ta) * (R1 + 18), ty0 = cy + Math.sin(ta) * (R1 + 18); c.arc(tx0, ty0, 9, 0, 7); c.fill(); }
  // P-EN left / right drive
  const dr = clamp(brain.drive / 0.5, -1, 1);
  const bar = (x, v, label) => { c.fillStyle = '#2e2e2e'; c.fillRect(x, 60, 26, 200); c.fillStyle = '#d97757'; c.fillRect(x, 260 - 200 * v, 26, 200 * v); c.fillStyle = '#a9a9a9'; c.font = '500 17px Inter, system-ui, sans-serif'; c.fillText(label, x + 13, 282); };
  bar(18, Math.max(0, -dr), 'P-EN L'); bar(w - 44, Math.max(0, dr), 'P-EN R');
  // Δ7 global inhibition
  c.fillStyle = '#2e2e2e'; c.fillRect(150, 448, 260, 12); c.fillStyle = '#8a8a8a'; c.fillRect(150, 448, 260 * clamp(brain.d7 / 0.4, 0, 1), 12);
  c.fillStyle = '#a9a9a9'; c.textAlign = 'right'; c.fillText('Δ7', 138, 455);
  // CPG traces + Johnston's organ
  const tr = brain.trace, y0 = 590, y1 = 486;
  c.fillStyle = '#a9a9a9'; c.textAlign = 'left'; c.font = '500 17px Inter, system-ui, sans-serif'; c.fillText('CPG half-center', 18, 478);
  for (const [k, col] of [[0, '#d97757'], [1, '#5680c2']]) {
    c.strokeStyle = col; c.lineWidth = 3; c.beginPath();
    tr.forEach((v, i) => { const x = 18 + (i / 119) * (w - 110), y = y0 - clamp(v[k] / 0.8, 0, 1) * (y0 - y1 - 10); i ? c.lineTo(x, y) : c.moveTo(x, y); });
    c.stroke();
  }
  c.fillStyle = `rgba(240,160,128,${0.2 + 0.8 * brain.jo})`; c.beginPath(); c.arc(w - 46, 540, 18, 0, 7); c.fill();
  c.fillStyle = '#e8e8e8'; c.textAlign = 'center'; c.font = '600 15px Inter, system-ui, sans-serif'; c.fillText('JO', w - 46, 541);
}

// ------------------------------------------------------------------ main loop
const stepSmooth = { v: 0 };
function frame() {
  requestAnimationFrame(frame);
  const now = clock();
  const dt = clamp(now - (S.last || now), 0.001, 0.05); S.last = now;
  S.frame++;
  S.fpsN++; if (now - S.fpsT > 1) { S.fps = S.fpsN / (now - S.fpsT); S.fpsT = now; S.fpsN = 0; }
  let P = S.playing, t = P ? now - P.start : 0;
  if (P && t >= P.d.dur) { finishDance(false); P = S.playing; t = P ? now - P.start : 0; }
  const tl = P && t >= 0 ? P.tl : idleTl, tt = P ? Math.max(t, 0) : 0, tAnim = P ? tt : now;
  // beats: entrain the CPG through the antennae
  let beat = false;
  if (P) { const B = P.d.beats; while (S.beatIdx < B.length && B[S.beatIdx] <= tt) { beat = true; S.beatIdx++; } }
  const period = P ? 60 / P.d.bpm / 4 : 0.6;
  const cpg = brain.stepCPG(dt, period, beat);
  S.cpgAmp = Math.max(S.cpgAmp * Math.exp(-dt / 2), Math.abs(cpg), 0.05);
  const sig = clamp(cpg / S.cpgAmp, -1, 1);
  // heading: the choreography asks for a turn, the fly-brain ring attractor integrates it
  const yawLocal = tl.mix(tl.basis(tt), 'yaw')[0], yawD = S.yawHome + yawLocal;
  const omega = ((yawD - S.prevYawD) / dt) * D2R; S.prevYawD = yawD;
  brain.visual = $('b-vision').checked;
  const head = brain.step(dt, omega, yawD * D2R) / D2R;
  const yaw = $('b-steer').checked ? head : yawD;
  let p = evalParams(tl, tt, yaw, P ? sig : 0);
  if (!P) { p.chs[0] += 1.2 * Math.sin(2 * Math.PI * 0.25 * now); p.head[1] += 3 * Math.sin(2 * Math.PI * 0.13 * now); p.head[2] += 5 * Math.sin(2 * Math.PI * 0.09 * now); }
  if (S.fade) { const w = smooth((now - S.fade.t0) / S.fade.dur); p = blendParams(S.fade.from, p, w); if (w >= 1) S.fade = null; }
  S.lastP = p;
  // camera
  const a = cam.auto ? autoCam(tt, dt) : null;
  if (a) { cam.az = a.az; cam.el = a.el; cam.dist = a.dist; cam.tz = a.tz; }
  if (cam.snap) { const s = smooth((performance.now() - cam.snap.t0) / 350); cam.az = lerp(cam.snap.az0, cam.snap.az1, s); cam.el = lerp(cam.snap.el0, cam.snap.el1, s); if (s >= 1) cam.snap = null; }
  const k = 1 - Math.exp(-dt / 0.38);
  cam.txy = [cam.txy[0] + (p.rp[0] - cam.txy[0]) * k, cam.txy[1] + (p.rp[1] - cam.txy[1]) * k];
  const az = cam.az * D2R, el = cam.el * D2R, look = [cam.txy[0], cam.txy[1], cam.tz];
  const eye = [look[0] - Math.sin(az) * Math.cos(el) * cam.dist, look[1] - Math.cos(az) * Math.cos(el) * cam.dist, look[2] + Math.sin(el) * cam.dist];
  const w = canvas.clientWidth, h = canvas.clientHeight, aspect = w / Math.max(h, 1);
  const vfov = Math.max(38, (2 * Math.atan(Math.tan(26 * D2R) / aspect)) / D2R);
  const V = lookAt(eye, look, Math.abs(cam.el) > 88 ? [0, 1, 0] : [0, 0, 1]), Pm = perspective(Math.min(vfov, 80), aspect, 0.05, 200);
  // pose, secondary motion, skirt
  const { loc, Wroot } = solvePose(p, tAnim, cam.az);
  S.excite = Math.max(0, S.excite - dt);
  const W = sec.step(dt, p, tAnim, loc, Wroot, { excite: S.excite > 0 ? 1 : 0 });
  const lift = sec.solveSkirt(W, tAnim);
  skirt.build(sec.flare, sec.sw, tAnim, sec.flutter, lift);
  // sparkles
  let rate = 0, burst = 0;
  if (P) {
    for (const [a0, a1, r] of P.d.sparks || []) if (tt >= a0 && tt <= a1) rate += r;
    for (const b of P.d.bursts || []) if (tt - dt < b && tt >= b) burst += 230;
  }
  if (S.bravoBurst) { burst += 260; S.bravoBurst = false; }
  if (S.excite > 0) rate += 90;
  if (rate || burst) sec.emitParticles(W, tAnim, dt, rate, burst, sec.omega, p.rp);
  const nPts = sec.updateParticles(dt, tAnim, ptsBuf);
  // shadows: pelvis blob + both pointe tips
  const pel = m4t(W.pelvis), hgt = Math.max(0, pel[2] - 1.0), sh = [[pel[0], pel[1], 0.36, 0.3 * Math.exp(-hgt * 3)]];
  for (const [s, sg] of [['L', 1], ['R', -1]]) { const tip = m4pt(W['shin' + s], sub([sg * 0.075, 0, 0.01], PIV['shin' + s])); sh.push([tip[0], tip[1], 0.075, 0.32 * Math.exp(-Math.max(tip[2], 0) * 9)]); }
  const models = {};
  for (const b in W) models[b] = m4mul(W[b], m4(null, [-PIV[b][0], -PIV[b][1], -PIV[b][2]]));
  R.frame({ V, P: Pm, eye, grid: gridOn, shadows: sh, models, skirt, skirtModel: models.pelvis, skirtColor: ORANGE,
    skirtGlow: S.excite > 0 ? 0.25 * Math.min(1, S.excite) : 0, pts: ptsBuf, nPts, kpt: (canvas.height) / (2 * Math.tan(Math.min(vfov, 80) * D2R / 2)) });
  // UI
  if (gizmoOn) drawGizmo(V);
  drawOverlay(m4mul(Pm, V), w, h);
  const fno = Math.floor((P ? tt : now) * FPS) + 1;
  $('vpinfo').textContent = `(${fno}) Collection | Claude Skirt`;
  $('frame').textContent = fno;
  drawTimeline(tt);
  if (P) {
    let mv = '';
    for (const [mt, label] of P.d.marks || []) if (mt <= tt) mv = label;
    $('now-move').textContent = mv;
    cards[P.d.id].querySelector('.bar').style.width = `${clamp(tt / P.d.dur, 0, 1) * 100}%`;
  }
  if (!$('tab-brain').hidden && S.frame % 2 === 0) drawBrain(head, yawD);
  if (!$('tab-item').hidden && S.frame % 6 === 0) {
    $('lx').textContent = p.rp[0].toFixed(3) + ' m'; $('ly').textContent = p.rp[1].toFixed(3) + ' m'; $('lz').textContent = p.rp[2].toFixed(3) + ' m';
    $('rx').textContent = p.pel[0].toFixed(1) + '°'; $('ry').textContent = p.pel[1].toFixed(1) + '°'; $('rz').textContent = ((((yaw % 360) + 360) % 360)).toFixed(1) + '°';
    $('o-fps').textContent = S.fps.toFixed(0);
  }
}
brain.reset(0);
requestAnimationFrame(frame);
