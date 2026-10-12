// Raw WebGL2 renderer with Blender's Solid-mode look: studio lighting, grey clay, floor grid with axes.
import { toGL } from './math.js';

const MESH_VS = `#version 300 es
layout(location=0) in vec3 aP; layout(location=1) in vec3 aN;
uniform mat4 uM; uniform mat4 uV; uniform mat4 uP;
out vec3 vN; out vec3 vPv;
void main(){ vec4 w = uM*vec4(aP,1.0); vec4 v = uV*w; vPv = v.xyz; vN = mat3(uV)*(mat3(uM)*aN); gl_Position = uP*v; }`;
const MESH_FS = `#version 300 es
precision highp float;
in vec3 vN; in vec3 vPv; uniform vec3 uC; uniform float uS; uniform float uGlow; out vec4 o;
void main(){
  vec3 n = normalize(vN); vec3 v = normalize(-vPv);
  if (dot(n,v) < 0.0) n = -n;
  vec3 L1 = normalize(vec3(-0.45,0.62,0.64)); vec3 L2 = normalize(vec3(0.8,0.1,0.45)); vec3 L3 = normalize(vec3(0.15,-0.7,0.35));
  float d1 = max(dot(n,L1),0.0), d2 = max(dot(n,L2),0.0), d3 = max(dot(n,L3),0.0);
  float hemi = 0.5+0.5*n.y;
  vec3 amb = mix(vec3(0.13,0.13,0.14), vec3(0.30,0.31,0.33), hemi);
  vec3 dif = amb + vec3(1.0,0.98,0.95)*0.66*d1 + vec3(0.82,0.88,1.0)*0.24*d2 + vec3(0.9)*0.06*d3;
  float sp = pow(max(dot(n,normalize(L1+v)),0.0),42.0)*uS + pow(max(dot(n,normalize(L2+v)),0.0),28.0)*uS*0.35;
  float rim = pow(1.0-max(dot(n,v),0.0),3.0)*0.07;
  vec3 c = uC*dif + vec3(sp+rim) + uC*uGlow;
  o = vec4(pow(clamp(c,0.0,1.0), vec3(1.0/2.2)), 1.0);
}`;
const FLOOR_VS = `#version 300 es
layout(location=0) in vec3 aP; uniform mat4 uV; uniform mat4 uP; out vec3 vW;
void main(){ vW = aP; gl_Position = uP*uV*vec4(aP,1.0); }`;
const FLOOR_FS = `#version 300 es
precision highp float;
in vec3 vW; uniform vec3 uCam; uniform vec4 uSh0; uniform vec4 uSh1; uniform vec4 uSh2; uniform float uGrid; out vec4 o;
float gridl(vec2 p, float sp, float w){
  vec2 g = p/sp; vec2 fw = max(fwidth(g), vec2(1e-6));
  vec2 d = abs(fract(g-0.5)-0.5)/fw; float l = min(d.x,d.y);
  float a = 1.0 - smoothstep(w-0.5, w+0.5, l);
  return a*(1.0 - smoothstep(0.22, 0.6, max(fw.x, fw.y)));
}
float shd(vec4 s){ vec2 d = (vW.xy - s.xy)/s.z; return s.w*exp(-dot(d,d)*2.2); }
void main(){
  vec3 bg = vec3(0.2471);
  float dist = length(vW.xy - uCam.xy);
  float fade = (1.0 - smoothstep(6.0, 30.0, dist))*uGrid;
  float a1 = gridl(vW.xy, 0.14, 0.62)*0.95, a2 = gridl(vW.xy, 1.4, 0.85);
  vec2 fw = fwidth(vW.xy/0.14);
  float haze = smoothstep(0.25, 1.0, max(fw.x,fw.y))*0.55;
  vec3 col = bg;
  col = mix(col, vec3(0.292), haze*fade); col = mix(col, vec3(0.335), a1*fade); col = mix(col, vec3(0.375), a2*fade);
  float af = (1.0 - smoothstep(10.0, 45.0, dist))*uGrid;
  float ax = (1.0 - smoothstep(0.7, 1.7, abs(vW.y)/max(fwidth(vW.y),1e-6)))*af;
  float ay = (1.0 - smoothstep(0.7, 1.7, abs(vW.x)/max(fwidth(vW.x),1e-6)))*af;
  col = mix(col, vec3(0.78,0.22,0.29), ax*0.9); col = mix(col, vec3(0.45,0.64,0.15), ay*0.9);
  float s = clamp(shd(uSh0)+shd(uSh1)+shd(uSh2), 0.0, 0.6);
  col *= 1.0 - s*(1.0 - smoothstep(6.0, 30.0, dist));
  o = vec4(col, 1.0);
}`;
const PTS_VS = `#version 300 es
layout(location=0) in vec3 aP; layout(location=1) in vec4 aC; layout(location=2) in float aS;
uniform mat4 uV; uniform mat4 uP; uniform float uK; out vec4 vC;
void main(){ vec4 c = uP*uV*vec4(aP,1.0); gl_Position = c; gl_PointSize = clamp(aS*uK/c.w, 1.5, 96.0); vC = aC; }`;
const PTS_FS = `#version 300 es
precision highp float;
in vec4 vC; out vec4 o;
void main(){ vec2 d = gl_PointCoord*2.0-1.0; float r = dot(d,d);
  float g = exp(-r*3.5)*0.55 + exp(-r*28.0)*1.3 + (exp(-abs(d.x)*16.0)*exp(-abs(d.y)*2.2)+exp(-abs(d.y)*16.0)*exp(-abs(d.x)*2.2))*0.55;
  o = vec4(vC.rgb*g*vC.a, 1.0); }`;

export const SHADERS = { MESH_VS, MESH_FS, FLOOR_VS, FLOOR_FS, PTS_VS, PTS_FS };

function compile(gl, vs, fs) {
  const mk = (type, src) => {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  };
  const p = gl.createProgram();
  gl.attachShader(p, mk(gl.VERTEX_SHADER, vs)); gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const U = {}, n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < n; i++) { const u = gl.getActiveUniform(p, i); U[u.name] = gl.getUniformLocation(p, u.name); }
  return { p, U };
}

export class Renderer {
  constructor(canvas) {
    const gl = canvas.getContext('webgl2', { antialias: true, alpha: false, powerPreference: 'high-performance' });
    if (!gl) throw new Error('This browser does not support WebGL2.');
    this.gl = gl; this.canvas = canvas;
    this.mesh = compile(gl, MESH_VS, MESH_FS); this.floor = compile(gl, FLOOR_VS, FLOOR_FS); this.pts = compile(gl, PTS_VS, PTS_FS);
    this.parts = []; this.m16 = new Float32Array(16); this.grid = 1;
    const E = 80, fv = new Float32Array([-E, -E, 0, E, -E, 0, E, E, 0, -E, E, 0]);
    this.floorVao = this._vao([[fv, 3]], new Uint16Array([0, 1, 2, 0, 2, 3]));
    this.pBuf = gl.createBuffer(); this.pVao = gl.createVertexArray();
    gl.bindVertexArray(this.pVao); gl.bindBuffer(gl.ARRAY_BUFFER, this.pBuf);
    gl.bufferData(gl.ARRAY_BUFFER, 2500 * 32, gl.DYNAMIC_DRAW);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 32, 0); gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(1, 4, gl.FLOAT, false, 32, 12); gl.enableVertexAttribArray(1);
    gl.vertexAttribPointer(2, 1, gl.FLOAT, false, 32, 28); gl.enableVertexAttribArray(2);
    gl.bindVertexArray(null);
  }
  _vao(attrs, idx, dynamic) {
    const gl = this.gl, vao = gl.createVertexArray(); gl.bindVertexArray(vao);
    const bufs = attrs.map(([data, size], loc) => {
      const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
      gl.bufferData(gl.ARRAY_BUFFER, data, dynamic ? gl.DYNAMIC_DRAW : gl.STATIC_DRAW);
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0); gl.enableVertexAttribArray(loc);
      return b;
    });
    const eb = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, eb); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);
    gl.bindVertexArray(null);
    return { vao, bufs, n: idx.length, type: idx instanceof Uint32Array ? gl.UNSIGNED_INT : gl.UNSIGNED_SHORT };
  }
  addPart(bone, m, color, spec) { this.parts.push({ bone, color, spec, ...this._vao([[m.P, 3], [m.N, 3]], m.I) }); }
  setSkirt(sk) { this.skirt = this._vao([[sk.P, 3], [sk.N, 3]], sk.I, true); }
  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2), c = this.canvas;
    const w = Math.max(1, Math.round(c.clientWidth * dpr)), h = Math.max(1, Math.round(c.clientHeight * dpr));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    return [w, h];
  }
  frame(s) {
    const gl = this.gl, [w, h] = this.resize();
    gl.viewport(0, 0, w, h);
    gl.clearColor(0.2471, 0.2471, 0.2471, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const V = toGL(s.V, new Float32Array(16)), P = toGL(s.P, new Float32Array(16));
    // floor grid + soft contact shadows
    gl.disable(gl.DEPTH_TEST); gl.depthMask(false); gl.disable(gl.BLEND);
    let pr = this.floor; gl.useProgram(pr.p);
    gl.uniformMatrix4fv(pr.U.uV, false, V); gl.uniformMatrix4fv(pr.U.uP, false, P);
    gl.uniform3fv(pr.U.uCam, s.eye); gl.uniform1f(pr.U.uGrid, s.grid ? 1 : 0);
    ['uSh0', 'uSh1', 'uSh2'].forEach((u, i) => gl.uniform4fv(pr.U[u], s.shadows[i]));
    gl.bindVertexArray(this.floorVao.vao); gl.drawElements(gl.TRIANGLES, 6, gl.UNSIGNED_SHORT, 0);
    // the dancer
    gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.depthFunc(gl.LEQUAL);
    pr = this.mesh; gl.useProgram(pr.p);
    gl.uniformMatrix4fv(pr.U.uV, false, V); gl.uniformMatrix4fv(pr.U.uP, false, P); gl.uniform1f(pr.U.uGlow, 0);
    for (const q of this.parts) {
      gl.uniformMatrix4fv(pr.U.uM, false, toGL(s.models[q.bone], this.m16));
      gl.uniform3fv(pr.U.uC, q.color); gl.uniform1f(pr.U.uS, q.spec);
      gl.bindVertexArray(q.vao); gl.drawElements(gl.TRIANGLES, q.n, q.type, 0);
    }
    if (this.skirt) {
      const k = this.skirt;
      gl.bindBuffer(gl.ARRAY_BUFFER, k.bufs[0]); gl.bufferSubData(gl.ARRAY_BUFFER, 0, s.skirt.P);
      gl.bindBuffer(gl.ARRAY_BUFFER, k.bufs[1]); gl.bufferSubData(gl.ARRAY_BUFFER, 0, s.skirt.N);
      gl.uniformMatrix4fv(pr.U.uM, false, toGL(s.skirtModel, this.m16));
      gl.uniform3fv(pr.U.uC, s.skirtColor); gl.uniform1f(pr.U.uS, 0.22); gl.uniform1f(pr.U.uGlow, s.skirtGlow || 0);
      gl.bindVertexArray(k.vao); gl.drawElements(gl.TRIANGLES, k.n, k.type, 0);
    }
    // sparkles
    if (s.nPts > 0) {
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE); gl.depthMask(false);
      pr = this.pts; gl.useProgram(pr.p);
      gl.uniformMatrix4fv(pr.U.uV, false, V); gl.uniformMatrix4fv(pr.U.uP, false, P); gl.uniform1f(pr.U.uK, s.kpt);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.pBuf); gl.bufferSubData(gl.ARRAY_BUFFER, 0, s.pts, 0, s.nPts * 8);
      gl.bindVertexArray(this.pVao); gl.drawArrays(gl.POINTS, 0, s.nPts);
      gl.depthMask(true); gl.disable(gl.BLEND);
    }
    gl.bindVertexArray(null);
  }
}
