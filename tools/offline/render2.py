"""Claude Skirt v2 — 16:9, 30 s, full Blender viewport chrome."""
import sys, math, time, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import glx as G
import geo
from rig import M4, perspective, lookat, smooth, PIV, unit
import dance2 as D

W, H, FPS = 1920, 1080, D.FPS
NF = D.NF
VFOV = 38.0
LOGO = 'claude-logo.png'  # optional: the logo image; without it the shipped profile is used
HDR, TLH = 46, 80

VS_MESH = """#version 330 core
layout(location=0) in vec3 aP; layout(location=1) in vec3 aN;
uniform mat4 uM; uniform mat4 uV; uniform mat4 uP;
out vec3 vN; out vec3 vPv;
void main(){ vec4 w = uM*vec4(aP,1.0); vec4 v = uV*w; vPv = v.xyz; vN = mat3(uV)*(mat3(uM)*aN); gl_Position = uP*v; }"""
FS_MESH = """#version 330 core
in vec3 vN; in vec3 vPv; uniform vec3 uC; uniform float uS; out vec4 o;
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
  vec3 c = uC*dif + vec3(sp+rim);
  o = vec4(pow(clamp(c,0.0,1.0), vec3(1.0/2.2)), 1.0);
}"""
VS_FLOOR = """#version 330 core
layout(location=0) in vec3 aP; layout(location=1) in vec3 aN; uniform mat4 uV; uniform mat4 uP; out vec3 vW;
void main(){ vW = aP; gl_Position = uP*uV*vec4(aP,1.0); }"""
FS_FLOOR = """#version 330 core
in vec3 vW; uniform vec3 uCam; uniform vec4 uSh0; uniform vec4 uSh1; uniform vec4 uSh2; out vec4 o;
float gridl(vec2 p, float sp, float w){
  vec2 g = p/sp; vec2 fw = max(fwidth(g), vec2(1e-6));
  vec2 d = abs(fract(g-0.5)-0.5)/fw; float l = min(d.x,d.y);
  float a = 1.0 - smoothstep(w-0.5, w+0.5, l);
  float dens = max(fw.x, fw.y);
  return a*(1.0 - smoothstep(0.22, 0.6, dens));
}
float shd(vec4 s){ vec2 d = (vW.xy - s.xy)/s.z; return s.w*exp(-dot(d,d)*2.2); }
void main(){
  vec3 bg = vec3(0.2471);
  float dist = length(vW.xy - uCam.xy);
  float fade = 1.0 - smoothstep(6.0, 30.0, dist);
  float a1 = gridl(vW.xy, 0.14, 0.62)*0.95;
  float a2 = gridl(vW.xy, 1.4, 0.85);
  vec2 fw = fwidth(vW.xy/0.14); float dens = max(fw.x,fw.y);
  float haze = smoothstep(0.25, 1.0, dens)*0.55;
  vec3 col = bg;
  col = mix(col, vec3(0.292), haze*fade);
  col = mix(col, vec3(0.335), a1*fade);
  col = mix(col, vec3(0.375), a2*fade);
  float af = 1.0 - smoothstep(10.0, 45.0, dist);
  float ax = (1.0 - smoothstep(0.7, 1.7, abs(vW.y)/max(fwidth(vW.y),1e-6)))*af;
  float ay = (1.0 - smoothstep(0.7, 1.7, abs(vW.x)/max(fwidth(vW.x),1e-6)))*af;
  col = mix(col, vec3(0.78,0.22,0.29), ax*0.9);
  col = mix(col, vec3(0.45,0.64,0.15), ay*0.9);
  float s = clamp(shd(uSh0)+shd(uSh1)+shd(uSh2), 0.0, 0.6);
  col *= 1.0 - s*fade;
  o = vec4(col, 1.0);
}"""
VS_PTS = """#version 330 core
layout(location=0) in vec3 aP; layout(location=1) in vec4 aC; layout(location=2) in float aS;
uniform mat4 uV; uniform mat4 uP; uniform float uK; out vec4 vC;
void main(){ vec4 c = uP*uV*vec4(aP,1.0); gl_Position = c; gl_PointSize = clamp(aS*uK/c.w, 1.5, 120.0); vC = aC; }"""
FS_PTS = """#version 330 core
in vec4 vC; out vec4 o;
void main(){ vec2 d = gl_PointCoord*2.0-1.0; float r = dot(d,d);
  float g = exp(-r*3.5)*0.55 + exp(-r*28.0)*1.3 + (exp(-abs(d.x)*16.0)*exp(-abs(d.y)*2.2)+exp(-abs(d.y)*16.0)*exp(-abs(d.x)*2.2))*0.55;
  o = vec4(vC.rgb*g*vC.a, 1.0); }"""

# ------------------------------------------------------------------ Blender UI chrome
FD = '/usr/share/fonts/opentype/inter/'
F_UI = ImageFont.truetype(FD + 'Inter-Regular.otf', 20)
F_UIM = ImageFont.truetype(FD + 'Inter-Medium.otf', 24)
F_SM = ImageFont.truetype(FD + 'Inter-Regular.otf', 17)
F_G = ImageFont.truetype(FD + 'Inter-Bold.otf', 20 * 3)
F_T = ImageFont.truetype(FD + 'InterDisplay-Black.otf', 118)
TXT = (222, 222, 222, 255)
BLUE = (71, 114, 179, 255)


def rrect(d, box, r, fill, outline=None, width=1):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def chevron(d, x, y, s=5, col=(200, 200, 200, 255)):
    d.line([(x - s, y - s / 2), (x, y + s / 2), (x + s, y - s / 2)], fill=col, width=2)


def icon_layer(size, draw_fn, S=4):
    im = Image.new('RGBA', (size * S, size * S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), size * S, S)
    return im.resize((size, size), Image.LANCZOS)


def ic_cube(d, n, S):
    c = (215, 215, 215, 255); w = 2 * S
    a = n * 0.22; b = n * 0.62; o = n * 0.16
    d.rectangle([a, a + o, b, b + o], outline=c, width=w)
    d.line([(a, a + o), (a + o, a), (b + o, a), (b, a + o)], fill=c, width=w)
    d.line([(b + o, a), (b + o, b), (b, b + o)], fill=c, width=w)


def ic_sphere(kind):
    def f(d, n, S):
        r = n * 0.36; c = n / 2
        if kind == 0:
            d.ellipse([c - r, c - r, c + r, c + r], outline=(225, 225, 225, 255), width=2 * S)
            d.ellipse([c - r, c - r * 0.35, c + r, c + r * 0.35], outline=(225, 225, 225, 255), width=S)
            d.line([(c, c - r), (c, c + r)], fill=(225, 225, 225, 255), width=S)
        elif kind == 1:
            d.ellipse([c - r, c - r, c + r, c + r], fill=(235, 235, 235, 255))
        elif kind == 2:
            d.ellipse([c - r, c - r, c + r, c + r], fill=(120, 120, 120, 255), outline=(225, 225, 225, 255), width=S * 2)
            d.pieslice([c - r, c - r, c + r, c + r], 135, 315, fill=(225, 225, 225, 255))
        else:
            d.ellipse([c - r, c - r, c + r, c + r], fill=(205, 205, 205, 255))
            d.ellipse([c - r * 0.55, c - r * 0.6, c - r * 0.05, c - r * 0.1], fill=(255, 255, 255, 255))
            d.arc([c - r, c - r, c + r, c + r], 10, 120, fill=(110, 110, 110, 255), width=3 * S)
    return f


def ic_zoom(d, n, S):
    c = (230, 230, 230, 255); r = n * 0.2; cx = cy = n * 0.43
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=int(2.4 * S))
    d.line([(cx + r * 0.7, cy + r * 0.7), (n * 0.74, n * 0.74)], fill=c, width=int(3.2 * S))


def ic_hand(d, n, S):
    c = (230, 230, 230, 255)
    d.rounded_rectangle([n * 0.33, n * 0.45, n * 0.68, n * 0.78], n * 0.08, fill=c)
    for k, (x, top) in enumerate(((0.35, 0.28), (0.44, 0.22), (0.53, 0.24), (0.62, 0.30))):
        d.rounded_rectangle([n * x, n * top, n * (x + 0.065), n * 0.55], n * 0.03, fill=c)
    d.line([(n * 0.34, n * 0.6), (n * 0.24, n * 0.48)], fill=c, width=int(3 * S))


def ic_cam(d, n, S):
    c = (230, 230, 230, 255)
    d.rectangle([n * 0.22, n * 0.42, n * 0.62, n * 0.7], fill=c)
    d.polygon([(n * 0.62, n * 0.56), (n * 0.8, n * 0.44), (n * 0.8, n * 0.68)], fill=c)
    for x in (0.3, 0.5):
        d.ellipse([n * (x - 0.07), n * 0.24, n * (x + 0.07), n * 0.38], outline=c, width=int(2.2 * S))


def ic_grid(d, n, S):
    c = (230, 230, 230, 255); w = int(2 * S)
    pts = lambda u, v: (n * (0.3 + 0.4 * u - 0.12 * (1 - v) * (u - 0.5) * 2 * 0), n * (0.28 + 0.44 * v))
    for k in range(4):
        u = k / 3
        top = (n * (0.36 + 0.28 * u), n * 0.28); bot = (n * (0.22 + 0.56 * u), n * 0.72)
        d.line([top, bot], fill=c, width=w)
    for k in range(4):
        v = k / 3
        xl = n * (0.36 - 0.14 * v); xr = n * (0.64 + 0.14 * v); y = n * (0.28 + 0.44 * v)
        d.line([(xl, y), (xr, y)], fill=c, width=w)


def ic_play(kind):
    def f(d, n, S):
        c = (225, 225, 225, 255); m = n / 2
        if kind == 'start':
            d.rectangle([n * 0.25, n * 0.3, n * 0.32, n * 0.7], fill=c)
            d.polygon([(n * 0.72, n * 0.3), (n * 0.72, n * 0.7), (n * 0.36, m)], fill=c)
        elif kind == 'end':
            d.rectangle([n * 0.68, n * 0.3, n * 0.75, n * 0.7], fill=c)
            d.polygon([(n * 0.28, n * 0.3), (n * 0.28, n * 0.7), (n * 0.64, m)], fill=c)
        elif kind == 'prevk':
            d.polygon([(n * 0.62, n * 0.3), (n * 0.62, n * 0.7), (n * 0.32, m)], fill=c)
            d.polygon([(n * 0.72, n * 0.4), (n * 0.8, m), (n * 0.72, n * 0.6), (n * 0.64, m)], fill=c)
        elif kind == 'nextk':
            d.polygon([(n * 0.38, n * 0.3), (n * 0.38, n * 0.7), (n * 0.68, m)], fill=c)
            d.polygon([(n * 0.28, n * 0.4), (n * 0.36, m), (n * 0.28, n * 0.6), (n * 0.2, m)], fill=c)
        elif kind == 'rev':
            d.polygon([(n * 0.66, n * 0.28), (n * 0.66, n * 0.72), (n * 0.3, m)], fill=c)
        elif kind == 'pause':
            d.rectangle([n * 0.33, n * 0.28, n * 0.44, n * 0.72], fill=c)
            d.rectangle([n * 0.56, n * 0.28, n * 0.67, n * 0.72], fill=c)
    return f


def build_static_ui():
    ui = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ui)
    # --- 3D viewport header
    d.rectangle([0, 0, W, HDR], fill=(48, 48, 48, 255))
    d.line([(0, HDR), (W, HDR)], fill=(32, 32, 32, 255), width=2)
    rrect(d, [10, 8, 60, 38], 6, (62, 62, 62, 255))
    ui.alpha_composite(icon_layer(28, ic_cube), (16, 9)); chevron(d, 52, 23, 4)
    rrect(d, [70, 8, 238, 38], 6, (62, 62, 62, 255))
    d.rectangle([80, 16, 94, 30], outline=(230, 150, 70, 255), width=2)
    d.text((102, 11), 'Object Mode', font=F_UI, fill=TXT); chevron(d, 224, 23, 4)
    x = 258
    for m in ('View', 'Select', 'Add', 'Object'):
        d.text((x, 11), m, font=F_UI, fill=TXT); x += int(d.textlength(m, font=F_UI)) + 26
    cx = W // 2 - 150
    rrect(d, [cx, 8, cx + 128, 38], 6, (62, 62, 62, 255))
    d.text((cx + 34, 11), 'Global', font=F_UI, fill=TXT); chevron(d, cx + 114, 23, 4)
    d.ellipse([cx + 10, 15, cx + 26, 31], outline=(225, 225, 225, 255), width=2)
    for k in range(3):
        bx = cx + 140 + k * 46
        rrect(d, [bx, 8, bx + 40, 38], 6, (62, 62, 62, 255))
        if k == 0:
            d.ellipse([bx + 12, 15, bx + 28, 31], outline=(225, 225, 225, 255), width=2); d.ellipse([bx + 18, 21, bx + 22, 25], fill=TXT)
        elif k == 1:
            d.polygon([(bx + 10, 30), (bx + 20, 12), (bx + 30, 30)], outline=(225, 225, 225, 255), width=2)
        else:
            d.arc([bx + 10, 13, bx + 30, 33], 200, 340, fill=(225, 225, 225, 255), width=2); d.ellipse([bx + 18, 22, bx + 22, 26], fill=TXT)
    # right side: overlays / gizmo toggles + shading modes
    rx = W - 360
    for k in range(2):
        bx = rx + k * 70
        rrect(d, [bx, 8, bx + 62, 38], 6, (71, 114, 179, 255) if True else (62, 62, 62, 255))
        if k == 0:
            d.ellipse([bx + 10, 14, bx + 26, 30], outline=TXT, width=2); d.ellipse([bx + 18, 14, bx + 34, 30], outline=TXT, width=2)
        else:
            d.line([(bx + 12, 30), (bx + 30, 14)], fill=TXT, width=3); d.polygon([(bx + 30, 12), (bx + 24, 14), (bx + 30, 20)], fill=TXT)
        chevron(d, bx + 50, 23, 4)
    sx = W - 214
    rrect(d, [sx, 8, sx + 4 * 40, 38], 6, (62, 62, 62, 255))
    rrect(d, [sx + 40, 8, sx + 80, 38], 0, (71, 114, 179, 255))
    for k in range(4):
        ui.alpha_composite(icon_layer(26, ic_sphere(k)), (sx + k * 40 + 7, 10))
    chevron(d, W - 34, 23, 4)
    # --- navigation buttons under the gizmo
    gx = W - 104
    for k, fn in enumerate((ic_zoom, ic_hand, ic_cam, ic_grid)):
        y = HDR + 234 + k * 54
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.ellipse([gx - 22, y - 22, gx + 22, y + 22], fill=(28, 28, 28, 150))
        ui.alpha_composite(ov)
        ui.alpha_composite(icon_layer(40, fn), (gx - 20, y - 20))
    # --- timeline editor
    ty = H - TLH
    d.rectangle([0, ty, W, ty + 32], fill=(48, 48, 48, 255))
    d.line([(0, ty), (W, ty)], fill=(26, 26, 26, 255), width=2)
    d.rectangle([0, ty + 32, W, H], fill=(40, 40, 40, 255))
    x = 14
    for m, dd in (('Playback', True), ('Keying', True), ('View', False), ('Marker', False)):
        d.text((x, ty + 5), m, font=F_SM, fill=TXT)
        x += int(d.textlength(m, font=F_SM)) + (24 if dd else 18)
        if dd:
            chevron(d, x - 14, ty + 16, 4)
    px = W // 2 - 150
    for k, kind in enumerate(('start', 'prevk', 'rev', 'pause', 'nextk', 'end')):
        bx = px + k * 40
        rrect(d, [bx, ty + 4, bx + 36, ty + 28], 4, (71, 114, 179, 255) if kind == 'pause' else (62, 62, 62, 255))
        ui.alpha_composite(icon_layer(24, ic_play(kind)), (bx + 6, ty + 4))
    rrect(d, [W - 330, ty + 4, W - 186, ty + 28], 4, (62, 62, 62, 255))
    d.text((W - 320, ty + 6), 'Start', font=F_SM, fill=(170, 170, 170, 255)); d.text((W - 206, ty + 6), '1', font=F_SM, fill=TXT)
    rrect(d, [W - 180, ty + 4, W - 14, ty + 28], 4, (62, 62, 62, 255))
    d.text((W - 170, ty + 6), 'End', font=F_SM, fill=(170, 170, 170, 255))
    d.text((W - 24 - d.textlength(str(NF), font=F_SM), ty + 6), str(NF), font=F_SM, fill=TXT)
    for f in range(0, NF + 1, 10):
        xx = fx(f)
        big = f % 50 == 0
        d.line([(xx, ty + 33), (xx, H if big else ty + 40)], fill=(56, 56, 56, 255) if big else (50, 50, 50, 255), width=1)
        if big and f % 100 == 0:
            d.text((xx + 4, ty + 34), str(f), font=F_SM, fill=(150, 150, 150, 255))
    for kt in D.TS:
        xx = fx(kt * FPS); yy = H - 18
        d.polygon([(xx, yy - 7), (xx + 7, yy), (xx, yy + 7), (xx - 7, yy)], fill=(225, 225, 225, 255), outline=(20, 20, 20, 255))
    return ui


def fx(f):
    return 40 + (W - 80) * f / NF


def make_cursor():
    S = 4; R = 16 * S; size = 2 * (R + 13 * S)
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = size / 2
    for k in range(8):
        col = (255, 60, 60, 255) if k % 2 == 0 else (255, 255, 255, 255)
        d.arc([c - R, c - R, c + R, c + R], k * 45, k * 45 + 45, fill=col, width=int(2.8 * S))
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([c + dx * R * 0.45, c + dy * R * 0.45, c + dx * (R + 10 * S), c + dy * (R + 10 * S)], fill=(10, 10, 10, 255), width=int(2.3 * S))
    return im.resize((size // S, size // S), Image.LANCZOS)


CURSOR = make_cursor()
CURSOR_W = None
ORIGIN_W = None


def place_markers(V, P):
    """Put the 3D cursor / origin dot where they sit in the screenshot, but far behind the dancer."""
    global CURSOR_W, ORIGIN_W
    inv = np.linalg.inv(P @ V)
    eye = np.linalg.inv(V)[:3, 3]
    def unproj(px, py, depth):
        nd = np.array([px / W * 2 - 1, 1 - py / H * 2, 0.5, 1.0])
        w = inv @ nd; w = w[:3] / w[3]
        return eye + unit(w - eye) * depth
    CURSOR_W = unproj(W / 2 - 300, H / 2 - 270, 7.5)
    ORIGIN_W = unproj(W / 2 - 390, H / 2 + 30, 8.5)


def project(VP, p):
    c = VP @ np.append(p, 1.0)
    if c[3] <= 1e-6:
        return None
    n = c[:3] / c[3]
    return ((n[0] * 0.5 + 0.5) * W, (1 - (n[1] * 0.5 + 0.5)) * H, c[3])


def draw_gizmo(img, V):
    S = 3; box = 220; cx = cy = box * S / 2; R = 74 * S; cr = 18 * S
    lay = Image.new('RGBA', (box * S, box * S), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    cols = {'X': (255, 51, 82), 'Y': (139, 220, 0), 'Z': (40, 144, 255)}
    items = []
    for i, ax in enumerate('XYZ'):
        e = np.zeros(3); e[i] = 1
        v = V[:3, :3] @ e
        items.append((v[2], ax, 1, v)); items.append((-v[2], ax, -1, -v))
    items.sort(key=lambda x: x[0])
    for z, ax, sg, v in items:
        px, py = cx + v[0] * R, cy - v[1] * R
        col = cols[ax]
        if sg > 0:
            d.line([cx, cy, px, py], fill=col + (255,), width=int(2.8 * S))
            d.ellipse([px - cr, py - cr, px + cr, py + cr], fill=col + (255,))
            tw = d.textlength(ax, font=F_G)
            d.text((px - tw / 2, py - 34), ax, font=F_G, fill=(15, 15, 15, 255))
        else:
            dark = tuple(int(c * 0.42) for c in col)
            d.ellipse([px - cr, py - cr, px + cr, py + cr], fill=dark + (210,), outline=col + (255,), width=int(2.6 * S))
    lay = lay.resize((box, box), Image.LANCZOS)
    img.alpha_composite(lay, (W - 104 - box // 2, HDR + 112 - box // 2))


def title(img, t, t0=27.35):
    txt = 'CLAUDE SKIRT'
    sp = 9
    widths = [F_T.getlength(ch) for ch in txt]
    total = sum(widths) + sp * (len(txt) - 1)
    LH = 300
    lay = Image.new('RGBA', (W, LH), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    glow = Image.new('RGBA', (W, LH), (0, 0, 0, 0)); dg = ImageDraw.Draw(glow)
    x = (W - total) / 2
    for k, ch in enumerate(txt):
        a = smooth((t - t0 - k * 0.045) / 0.3)
        if a > 0:
            yo = 30 * (1 - a)
            d.text((x, 70 + yo), ch, font=F_T, fill=(255, 246, 238, int(255 * a)))
            dg.text((x, 70 + yo), ch, font=F_T, fill=(217, 119, 87, int(255 * a)))
        x += widths[k] + sp
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    shadow = lay.split()[3].filter(ImageFilter.GaussianBlur(7))
    shl = Image.new('RGBA', (W, LH), (0, 0, 0, 255)); shl.putalpha(shadow.point(lambda v: int(v * 0.55)))
    y0 = 40
    img.alpha_composite(shl, (0, y0 + 6))
    img.alpha_composite(glow, (0, y0)); img.alpha_composite(glow, (0, y0))
    img.alpha_composite(lay, (0, y0))


def overlay(frame_rgb, fi, V, P, t, static_ui):
    img = Image.fromarray(frame_rgb).convert('RGBA')
    VP = P @ V
    d = ImageDraw.Draw(img)
    q = project(VP, ORIGIN_W)
    if q:
        x, y, _ = q
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(20, 20, 20, 255))
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 160, 40, 255))
    q = project(VP, CURSOR_W)
    if q:
        img.alpha_composite(CURSOR, (int(q[0] - CURSOR.width / 2), int(q[1] - CURSOR.height / 2)))
    if t >= 27.3:
        title(img, t)
    img.alpha_composite(static_ui)
    d = ImageDraw.Draw(img)
    for txt, y in (('User Perspective', HDR + 14), ('(%d) Collection | Claude Skirt' % (fi + 1), HDR + 46)):
        d.text((26, y + 2), txt, font=F_UIM, fill=(0, 0, 0, 170))
        d.text((24, y), txt, font=F_UIM, fill=(236, 236, 236, 255))
    draw_gizmo(img, V)
    ty = H - TLH
    rrect(d, [W - 436, ty + 4, W - 342, ty + 28], 4, (71, 114, 179, 255))
    s = str(fi + 1); d.text((W - 389 - d.textlength(s, font=F_SM) / 2, ty + 6), s, font=F_SM, fill=(255, 255, 255, 255))
    xx = fx(fi)
    d.line([(xx, ty + 32), (xx, H)], fill=(71, 114, 179, 255), width=2)
    bw = d.textlength(s, font=F_SM) + 16
    rrect(d, [xx - bw / 2, ty + 33, xx + bw / 2, ty + 55], 5, (71, 114, 179, 255))
    d.text((xx - bw / 2 + 8, ty + 34), s, font=F_SM, fill=(255, 255, 255, 255))
    return np.asarray(img.convert('RGB'))


def main():
    test = None
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        test = [float(x) for x in sys.argv[2].split(',')]
    t0 = time.time()
    parts = geo.build_parts()
    skirt = geo.Skirt(LOGO)
    frames = D.simulate()
    D.skirt_lifts(frames, skirt)
    print('sim+lift %.1fs' % (time.time() - t0), flush=True)
    psim = D.simulate_particles(frames, skirt)
    print('particles %.1fs' % (time.time() - t0), flush=True)
    static_ui = build_static_ui()

    prog = G.Program(VS_MESH, FS_MESH)
    fprog = G.Program(VS_FLOOR, FS_FLOOR)
    pprog = G.Program(VS_PTS, FS_PTS)
    gm = []
    for bone, m, col, spec in parts:
        b = bone[:-2] if bone.endswith('_L') or bone.endswith('_R') else bone
        gm.append((b, G.GMesh(*m), col, spec))
    sp_, sn_, _ = skirt.build()
    skirt_mesh = G.GMesh(sp_, sn_, skirt.T, dynamic=True)
    E = 80.0
    floor = G.GMesh(np.array([[-E, -E, 0], [E, -E, 0], [E, E, 0], [-E, E, 0]], float), np.tile([0, 0, 1.0], (4, 1)),
                    np.array([[0, 1, 2], [0, 2, 3]]))
    pts = G.GPoints(30000)
    tgt = G.Target(W, H, 4)
    Pm = perspective(VFOV, W / H, 0.05, 200.0)
    kpt = H / (2 * math.tan(math.radians(VFOV) / 2))

    def camera(fr):
        az, el, dist, tz, follow, fxx, fyy = D.cam_params(fr['t'])
        follow = min(max(follow, 0.0), 1.0)
        txy = follow * fr['camxy'] + (1 - follow) * np.array([fxx, fyy])
        a, e = math.radians(az), math.radians(el)
        look = np.array([txy[0], txy[1], tz])
        eye = look + dist * np.array([-math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])
        return eye, look

    e0, l0 = camera(frames[0])
    place_markers(lookat(e0, l0), Pm)

    def render(fi):
        fr = frames[fi]; t = fr['t']
        eye, look = camera(fr)
        V = lookat(eye, look)
        Wm = fr['W']
        tgt.bind()
        G.glClearColor(0.2471, 0.2471, 0.2471, 1.0)
        G.glClear(G.GL_COLOR_BUFFER_BIT | G.GL_DEPTH_BUFFER_BIT)
        G.glDisable(G.GL_BLEND); G.glDisable(G.GL_DEPTH_TEST); G.glDepthMask(0)
        fprog.use(); fprog.mat4('uV', V); fprog.mat4('uP', Pm); fprog.vec3('uCam', eye)
        pel = Wm['pelvis'][:3, 3]
        hgt = max(0.0, pel[2] - 1.0)
        fprog.vec4('uSh0', (pel[0], pel[1], 0.36, 0.30 * math.exp(-hgt * 3)))
        for k, s in enumerate('LR'):
            tip = Wm['shin' + s] @ np.append(np.array([0.075 if s == 'L' else -0.075, 0, 0.01]) - PIV['shin' + s], 1)
            fprog.vec4('uSh%d' % (k + 1), (tip[0], tip[1], 0.075, 0.32 * math.exp(-max(tip[2], 0) * 9)))
        floor.draw()
        G.glEnable(G.GL_DEPTH_TEST); G.glDepthMask(1); G.glDepthFunc(G.GL_LEQUAL)
        prog.use(); prog.mat4('uV', V); prog.mat4('uP', Pm)
        for b, mesh, col, spec in gm:
            prog.mat4('uM', Wm[b] @ M4(None, -PIV[b]))
            prog.vec3('uC', col); prog.f1('uS', spec)
            mesh.draw()
        P_, N_, _ = skirt.build(fr['flare'], fr['swirl'], t, fr['flutter'], fr['lift'])
        skirt_mesh.update(P_, N_)
        prog.mat4('uM', Wm['pelvis'] @ M4(None, -PIV['pelvis']))
        prog.vec3('uC', geo.ORANGE); prog.f1('uS', 0.22)
        skirt_mesh.draw()
        pdata = psim[fi]
        if len(pdata):
            pts.update(pdata)
            G.glEnable(G.GL_BLEND); G.glBlendFunc(G.GL_ONE, G.GL_ONE); G.glDepthMask(0)
            G.glEnable(G.GL_PROGRAM_POINT_SIZE)
            pprog.use(); pprog.mat4('uV', V); pprog.mat4('uP', Pm); pprog.f1('uK', kpt)
            pts.draw()
            G.glDepthMask(1); G.glDisable(G.GL_BLEND)
        img = tgt.read()
        return overlay(img, fi, V, Pm, t, static_ui)

    if test:
        for tt in test:
            fi = min(int(round(tt * FPS)), NF - 1)
            Image.fromarray(render(fi)).save('t2_%05.2f.png' % tt)
        print('test done %.1fs' % (time.time() - t0))
        return
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                           '-r', str(FPS), '-i', '-', '-i', 'audio2.wav', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                           '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-c:a', 'aac', '-b:a', '192k', '-shortest',
                           '-movflags', '+faststart', 'claude_skirt_twitter.mp4'], stdin=subprocess.PIPE)
    for fi in range(NF):
        ff.stdin.write(render(fi).tobytes())
        if fi % 60 == 0:
            print('frame %d  %.1fs' % (fi, time.time() - t0), flush=True)
    ff.stdin.close(); ff.wait()
    print('done %.1fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
