"""Renders README assets (banner, preview GIF, moves grid) with the offline viewport renderer."""
import math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import render2 as R2
import glx as G
import geo
from rig import M4, perspective, lookat, PIV, unit
import dance2 as D

OUT = '../../assets'
os.makedirs(OUT, exist_ok=True)
FD = '/usr/share/fonts/opentype/inter/'

parts = geo.build_parts()
skirt = geo.Skirt(R2.LOGO)
frames = D.simulate()
D.skirt_lifts(frames, skirt)
psim = D.simulate_particles(frames, skirt)
prog = G.Program(R2.VS_MESH, R2.FS_MESH); fprog = G.Program(R2.VS_FLOOR, R2.FS_FLOOR); pprog = G.Program(R2.VS_PTS, R2.FS_PTS)
gm = [(b[:-2] if b.endswith(('_L', '_R')) else b, G.GMesh(*m), col, spec) for b, m, col, spec in parts]
sp_, sn_, _ = skirt.build()
skirt_mesh = G.GMesh(sp_, sn_, skirt.T, dynamic=True)
E = 80.0
floor = G.GMesh(np.array([[-E, -E, 0], [E, -E, 0], [E, E, 0], [-E, E, 0]], float), np.tile([0, 0, 1.0], (4, 1)), np.array([[0, 1, 2], [0, 2, 3]]))
pts = G.GPoints(30000)
targets = {}


def default_camera(fr):
    az, el, dist, tz, follow, fxx, fyy = D.cam_params(fr['t'])
    follow = min(max(follow, 0.0), 1.0)
    txy = follow * fr['camxy'] + (1 - follow) * np.array([fxx, fyy])
    a, e = math.radians(az), math.radians(el)
    look = np.array([txy[0], txy[1], tz])
    return look + dist * np.array([-math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)]), look


def render(fi, Wd, Hd, cam=None, vfov=38.0):
    if (Wd, Hd) not in targets:
        targets[(Wd, Hd)] = G.Target(Wd, Hd, 4)
    tgt = targets[(Wd, Hd)]
    fr = frames[fi]; t = fr['t']
    eye, look = cam if cam is not None else default_camera(fr)
    V = lookat(eye, look); Pm = perspective(vfov, Wd / Hd, 0.05, 200.0)
    Wm = fr['W']
    tgt.bind()
    G.glClearColor(0.2471, 0.2471, 0.2471, 1.0); G.glClear(G.GL_COLOR_BUFFER_BIT | G.GL_DEPTH_BUFFER_BIT)
    G.glDisable(G.GL_BLEND); G.glDisable(G.GL_DEPTH_TEST); G.glDepthMask(0)
    fprog.use(); fprog.mat4('uV', V); fprog.mat4('uP', Pm); fprog.vec3('uCam', eye)
    pel = Wm['pelvis'][:3, 3]; hgt = max(0.0, pel[2] - 1.0)
    fprog.vec4('uSh0', (pel[0], pel[1], 0.36, 0.30 * math.exp(-hgt * 3)))
    for k, s in enumerate('LR'):
        tip = Wm['shin' + s] @ np.append(np.array([0.075 if s == 'L' else -0.075, 0, 0.01]) - PIV['shin' + s], 1)
        fprog.vec4('uSh%d' % (k + 1), (tip[0], tip[1], 0.075, 0.32 * math.exp(-max(tip[2], 0) * 9)))
    floor.draw()
    G.glEnable(G.GL_DEPTH_TEST); G.glDepthMask(1); G.glDepthFunc(G.GL_LEQUAL)
    prog.use(); prog.mat4('uV', V); prog.mat4('uP', Pm)
    for b, mesh, col, spec in gm:
        prog.mat4('uM', Wm[b] @ M4(None, -PIV[b])); prog.vec3('uC', col); prog.f1('uS', spec); mesh.draw()
    P_, N_, _ = skirt.build(fr['flare'], fr['swirl'], t, fr['flutter'], fr['lift'])
    skirt_mesh.update(P_, N_)
    prog.mat4('uM', Wm['pelvis'] @ M4(None, -PIV['pelvis'])); prog.vec3('uC', geo.ORANGE); prog.f1('uS', 0.22); skirt_mesh.draw()
    pdata = psim[fi]
    if len(pdata):
        pts.update(pdata)
        G.glEnable(G.GL_BLEND); G.glBlendFunc(G.GL_ONE, G.GL_ONE); G.glDepthMask(0); G.glEnable(G.GL_PROGRAM_POINT_SIZE)
        pprog.use(); pprog.mat4('uV', V); pprog.mat4('uP', Pm); pprog.f1('uK', Hd / (2 * math.tan(math.radians(vfov) / 2)))
        pts.draw(); G.glDepthMask(1); G.glDisable(G.GL_BLEND)
    return tgt.read(), V, Pm


def side_camera(fi, az, el, dist, frac_x, tz=1.05, Wd=1280, Hd=640, vfov=38.0):
    """Camera that places the dancer at horizontal fraction frac_x of the frame."""
    p = frames[fi]['W']['pelvis'][:3, 3]
    a, e = math.radians(az), math.radians(el)
    f = np.array([math.sin(a), math.cos(a), 0.0]); right = np.array([f[1] * 1, -f[0], 0.0])
    right = unit(np.cross(f, [0, 0, 1]))
    halfw = dist * math.tan(math.radians(vfov) / 2) * Wd / Hd
    look = np.array([p[0], p[1], tz]) - right * (frac_x - 0.5) * 2 * halfw
    eye = look + dist * np.array([-math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])
    return eye, look


def chip(d, x, y, text, font):
    w = d.textlength(text, font=font)
    d.rounded_rectangle([x, y, x + w + 28, y + 40], 8, fill=(48, 48, 48, 235))
    d.text((x + 14, y + 8), text, font=font, fill=(232, 232, 232, 255))
    return x + w + 40


def banner(fi=int(23.62 * 30)):
    Wd, Hd = 1280, 640
    img, V, Pm = render(fi, Wd, Hd, side_camera(fi, 34, 4, 3.7, 0.71, 1.06))
    im = Image.fromarray(img).convert('RGBA')
    grad = Image.new('L', (Wd, 1))
    for x in range(Wd):
        grad.putpixel((x, 0), int(170 * max(0.0, 1 - x / (Wd * 0.62)) ** 1.4))
    shade = Image.new('RGBA', (Wd, Hd), (18, 18, 18, 255)); shade.putalpha(grad.resize((Wd, Hd)))
    im.alpha_composite(shade)
    R2.W, R2.H = Wd, Hd
    R2.draw_gizmo(im, V)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, Wd, 38], fill=(48, 48, 48, 255))
    d.rounded_rectangle([10, 6, 170, 32], 6, fill=(62, 62, 62, 255))
    d.rectangle([20, 13, 31, 24], outline=(230, 150, 70, 255), width=2)
    fs = ImageFont.truetype(FD + 'Inter-Regular.otf', 17)
    d.text((40, 9), 'Object Mode', font=fs, fill=(222, 222, 222, 255))
    x = 190
    for m in ('View', 'Select', 'Add', 'Object'):
        d.text((x, 9), m, font=fs, fill=(222, 222, 222, 255)); x += int(d.textlength(m, font=fs)) + 22
    for k in range(4):
        bx = Wd - 176 + k * 40
        d.rounded_rectangle([bx, 6, bx + 38, 32], 0, fill=(71, 114, 179, 255) if k == 1 else (62, 62, 62, 255))
        d.ellipse([bx + 11, 11, bx + 27, 27], fill=(235, 235, 235, 255) if k == 1 else None, outline=(225, 225, 225, 255), width=2)
    fk = ImageFont.truetype(FD + 'Inter-SemiBold.otf', 21)
    kicker = 'A FRUIT-FLY BRAIN DANCES BALLET'
    x = 66
    for ch in kicker:
        d.text((x, 150), ch, font=fk, fill=(240, 160, 128, 255)); x += d.textlength(ch, font=fk) + 2.6
    ft = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSerifBoldItalic.ttf', 132)
    glow = Image.new('RGBA', (Wd, Hd), (0, 0, 0, 0)); ImageDraw.Draw(glow).text((60, 176), 'Claude Skirt', font=ft, fill=(217, 119, 87, 200))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(im)
    d.text((60, 176), 'Claude Skirt', font=ft, fill=(255, 246, 238, 255))
    fsub = ImageFont.truetype(FD + 'Inter-Regular.otf', 27)
    d.text((66, 340), 'A bee-bot ballerina in a fake Blender viewport.', font=fsub, fill=(226, 226, 226, 255))
    d.text((66, 378), 'Order a dance, clap on the beat.', font=fsub, fill=(226, 226, 226, 255))
    fc = ImageFont.truetype(FD + 'Inter-Medium.otf', 19)
    x = 66
    for c in ('WebGL2', 'Web Audio', 'no Blender', 'no model files'):
        x = chip(d, x, 456, c, fc)
    im.convert('RGB').save(OUT + '/banner.png', optimize=True)
    print('banner.png')


def moves():
    picks = [(8.0, 'bourrée on pointe', (10, 7, 3.9, 0.5, 1.05)), (13.85, 'arabesque', (4, 4, 3.9, 0.5, 1.02)),
             (15.05, 'grand jeté', (0, 6, 4.3, 0.5, 1.05)), (23.4, 'fouettés', (40, 2, 3.6, 0.5, 1.08))]
    sheet = Image.new('RGB', (1280, 720), (24, 24, 24))
    fl = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSerifBoldItalic.ttf', 38)
    for k, (t, label, (az, el, dist, fx, tz)) in enumerate(picks):
        fi = int(round(t * 30))
        img, _, _ = render(fi, 1280, 720, side_camera(fi, az, el, dist, fx, tz, 1280, 720))
        tile = Image.fromarray(img).resize((636, 356), Image.LANCZOS).convert('RGBA')
        d = ImageDraw.Draw(tile)
        d.text((22, 300), label, font=fl, fill=(255, 246, 238, 255), stroke_width=0)
        sheet.paste(tile.convert('RGB'), ((k % 2) * 642 + 1, (k // 2) * 362 + 1))
    sheet.save(OUT + '/moves.png', optimize=True)
    print('moves.png')


def preview_gif(t0=21.5, t1=28.8, fps=15):
    R2.W, R2.H = 1280, 720
    ui = R2.build_static_ui()
    e0, l0 = default_camera(frames[0]); R2.place_markers(lookat(e0, l0), perspective(R2.VFOV, 1280 / 720, 0.05, 200))
    tmp = 'gif-frames'; os.makedirs(tmp, exist_ok=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    n = 0
    for k in range(int((t1 - t0) * fps)):
        fi = int(round((t0 + k / fps) * 30))
        img, V, Pm = render(fi, 1280, 720)
        out = R2.overlay(img, fi, V, Pm, frames[fi]['t'], ui)
        Image.fromarray(out).resize((640, 360), Image.LANCZOS).save('%s/f%04d.png' % (tmp, n)); n += 1
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', tmp + '/f%04d.png', '-vf',
                    'split[a][b];[a]palettegen=max_colors=160:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle',
                    '-loop', '0', OUT + '/preview.gif'], check=True)
    print('preview.gif', os.path.getsize(OUT + '/preview.gif') // 1024, 'KB')


banner()
moves()
preview_gif()
