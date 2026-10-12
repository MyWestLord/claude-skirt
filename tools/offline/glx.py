"""Minimal headless OpenGL 3.3 via EGL (Mesa llvmpipe) using ctypes only."""
import os, ctypes as C
os.environ.setdefault('EGL_PLATFORM', 'surfaceless')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
os.environ.setdefault('GALLIUM_DRIVER', 'llvmpipe')
import numpy as np

egl = C.CDLL('libEGL.so.1')
egl.eglGetProcAddress.restype = C.c_void_p
egl.eglGetProcAddress.argtypes = [C.c_char_p]

def _F(name, res, *args):
    p = egl.eglGetProcAddress(name.encode())
    if not p:
        raise RuntimeError('missing ' + name)
    return C.CFUNCTYPE(res, *args)(p)

u, i, f, vp, ub = C.c_uint, C.c_int, C.c_float, C.c_void_p, C.c_ubyte

def init_context():
    gpd = _F('eglGetPlatformDisplayEXT', C.c_void_p, C.c_uint, C.c_void_p, C.c_void_p)
    dpy = gpd(0x31DD, None, None)
    egl.eglInitialize.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p]
    if not egl.eglInitialize(dpy, None, None):
        raise RuntimeError('eglInitialize failed')
    egl.eglBindAPI(0x30A2)
    egl.eglCreateContext.restype = C.c_void_p
    egl.eglCreateContext.argtypes = [C.c_void_p] * 4
    attrs = (C.c_int * 7)(0x3098, 3, 0x30FB, 3, 0x30FD, 1, 0x3038)
    ctx = egl.eglCreateContext(dpy, None, None, attrs)
    if not ctx:
        raise RuntimeError('eglCreateContext failed')
    egl.eglMakeCurrent.argtypes = [C.c_void_p] * 4
    if not egl.eglMakeCurrent(dpy, None, None, ctx):
        raise RuntimeError('eglMakeCurrent failed')
    return dpy, ctx

init_context()

glClearColor = _F('glClearColor', None, f, f, f, f)
glClear = _F('glClear', None, u)
glEnable = _F('glEnable', None, u)
glDisable = _F('glDisable', None, u)
glViewport = _F('glViewport', None, i, i, i, i)
glDepthMask = _F('glDepthMask', None, ub)
glDepthFunc = _F('glDepthFunc', None, u)
glBlendFunc = _F('glBlendFunc', None, u, u)
glGenFramebuffers = _F('glGenFramebuffers', None, i, C.POINTER(u))
glBindFramebuffer = _F('glBindFramebuffer', None, u, u)
glGenRenderbuffers = _F('glGenRenderbuffers', None, i, C.POINTER(u))
glBindRenderbuffer = _F('glBindRenderbuffer', None, u, u)
glRenderbufferStorageMultisample = _F('glRenderbufferStorageMultisample', None, u, i, u, i, i)
glRenderbufferStorage = _F('glRenderbufferStorage', None, u, u, i, i)
glFramebufferRenderbuffer = _F('glFramebufferRenderbuffer', None, u, u, u, u)
glCheckFramebufferStatus = _F('glCheckFramebufferStatus', u, u)
glBlitFramebuffer = _F('glBlitFramebuffer', None, i, i, i, i, i, i, i, i, u, u)
glReadPixels = _F('glReadPixels', None, i, i, i, i, u, u, vp)
glPixelStorei = _F('glPixelStorei', None, u, i)
glCreateShader = _F('glCreateShader', u, u)
glShaderSource = _F('glShaderSource', None, u, i, C.POINTER(C.c_char_p), vp)
glCompileShader = _F('glCompileShader', None, u)
glGetShaderiv = _F('glGetShaderiv', None, u, u, C.POINTER(i))
glGetShaderInfoLog = _F('glGetShaderInfoLog', None, u, i, vp, C.c_char_p)
glCreateProgram = _F('glCreateProgram', u)
glAttachShader = _F('glAttachShader', None, u, u)
glLinkProgram = _F('glLinkProgram', None, u)
glGetProgramiv = _F('glGetProgramiv', None, u, u, C.POINTER(i))
glGetProgramInfoLog = _F('glGetProgramInfoLog', None, u, i, vp, C.c_char_p)
glUseProgram = _F('glUseProgram', None, u)
glGetUniformLocation = _F('glGetUniformLocation', i, u, C.c_char_p)
glUniformMatrix4fv = _F('glUniformMatrix4fv', None, i, i, ub, vp)
glUniform3f = _F('glUniform3f', None, i, f, f, f)
glUniform1f = _F('glUniform1f', None, i, f)
glUniform4f = _F('glUniform4f', None, i, f, f, f, f)
glGenVertexArrays = _F('glGenVertexArrays', None, i, C.POINTER(u))
glBindVertexArray = _F('glBindVertexArray', None, u)
glGenBuffers = _F('glGenBuffers', None, i, C.POINTER(u))
glBindBuffer = _F('glBindBuffer', None, u, u)
glBufferData = _F('glBufferData', None, u, C.c_ssize_t, vp, u)
glBufferSubData = _F('glBufferSubData', None, u, C.c_ssize_t, C.c_ssize_t, vp)
glVertexAttribPointer = _F('glVertexAttribPointer', None, u, i, u, ub, i, vp)
glEnableVertexAttribArray = _F('glEnableVertexAttribArray', None, u)
glDrawElements = _F('glDrawElements', None, u, i, u, vp)
glDrawArrays = _F('glDrawArrays', None, u, i, i)
glFinish = _F('glFinish', None)
glGenTextures = _F('glGenTextures', None, i, C.POINTER(u))
glBindTexture = _F('glBindTexture', None, u, u)
glTexImage2D = _F('glTexImage2D', None, u, i, i, i, i, i, u, u, vp)
glTexParameteri = _F('glTexParameteri', None, u, u, i)
glGenerateMipmap = _F('glGenerateMipmap', None, u)
glActiveTexture = _F('glActiveTexture', None, u)
glUniform1i = _F('glUniform1i', None, i, i)
glGetError = _F('glGetError', u)

GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT = 0x4000, 0x0100
GL_DEPTH_TEST, GL_BLEND, GL_CULL_FACE = 0x0B71, 0x0BE2, 0x0B44
GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE = 0x0302, 0x0303, 1
GL_LEQUAL = 0x0203
GL_TRIANGLES, GL_POINTS = 0x0004, 0x0000
GL_UNSIGNED_INT, GL_FLOAT, GL_UNSIGNED_BYTE = 0x1405, 0x1406, 0x1401
GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER = 0x8892, 0x8893
GL_STATIC_DRAW, GL_DYNAMIC_DRAW = 0x88E4, 0x88E8
GL_VERTEX_SHADER, GL_FRAGMENT_SHADER = 0x8B31, 0x8B30
GL_FRAMEBUFFER, GL_READ_FRAMEBUFFER, GL_DRAW_FRAMEBUFFER = 0x8D40, 0x8CA8, 0x8CA9
GL_RENDERBUFFER = 0x8D41
GL_COLOR_ATTACHMENT0, GL_DEPTH_ATTACHMENT = 0x8CE0, 0x8D00
GL_RGBA8, GL_DEPTH_COMPONENT24 = 0x8058, 0x81A6
GL_NEAREST = 0x2600
GL_RGB = 0x1907
GL_PROGRAM_POINT_SIZE, GL_MULTISAMPLE = 0x8642, 0x809D
GL_PACK_ALIGNMENT = 0x0D05


def _shader(src, kind):
    s = glCreateShader(kind)
    b = C.c_char_p(src.encode())
    glShaderSource(s, 1, C.byref(b), None)
    glCompileShader(s)
    ok = C.c_int()
    glGetShaderiv(s, 0x8B81, C.byref(ok))
    if not ok.value:
        buf = C.create_string_buffer(8192)
        glGetShaderInfoLog(s, 8192, None, buf)
        raise RuntimeError('shader: ' + buf.value.decode())
    return s


class Program:
    def __init__(self, vs, fs):
        p = glCreateProgram()
        glAttachShader(p, _shader(vs, GL_VERTEX_SHADER))
        glAttachShader(p, _shader(fs, GL_FRAGMENT_SHADER))
        glLinkProgram(p)
        ok = C.c_int()
        glGetProgramiv(p, 0x8B82, C.byref(ok))
        if not ok.value:
            buf = C.create_string_buffer(8192)
            glGetProgramInfoLog(p, 8192, None, buf)
            raise RuntimeError('link: ' + buf.value.decode())
        self.p = p
        self.loc = {}

    def use(self):
        glUseProgram(self.p)

    def _l(self, name):
        if name not in self.loc:
            self.loc[name] = glGetUniformLocation(self.p, name.encode())
        return self.loc[name]

    def mat4(self, name, M):
        a = np.ascontiguousarray(M, dtype=np.float32)
        glUniformMatrix4fv(self._l(name), 1, 1, a.ctypes.data)

    def vec3(self, name, v):
        glUniform3f(self._l(name), float(v[0]), float(v[1]), float(v[2]))

    def f1(self, name, x):
        glUniform1f(self._l(name), float(x))

    def vec4(self, name, v):
        glUniform4f(self._l(name), float(v[0]), float(v[1]), float(v[2]), float(v[3]))


class GMesh:
    """Interleaved position+normal mesh with index buffer."""
    def __init__(self, P, N, T, dynamic=False):
        self.vao = C.c_uint()
        glGenVertexArrays(1, C.byref(self.vao))
        glBindVertexArray(self.vao)
        self.vbo = C.c_uint()
        glGenBuffers(1, C.byref(self.vbo))
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        data = np.ascontiguousarray(np.hstack([P, N]), dtype=np.float32)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data.ctypes.data, GL_DYNAMIC_DRAW if dynamic else GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, 0, 24, C.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, 0, 24, C.c_void_p(12))
        glEnableVertexAttribArray(1)
        self.ebo = C.c_uint()
        glGenBuffers(1, C.byref(self.ebo))
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        idx = np.ascontiguousarray(T, dtype=np.uint32)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx.ctypes.data, GL_STATIC_DRAW)
        self.n = idx.size
        glBindVertexArray(0)

    def update(self, P, N):
        data = np.ascontiguousarray(np.hstack([P, N]), dtype=np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferSubData(GL_ARRAY_BUFFER, 0, data.nbytes, data.ctypes.data)

    def draw(self):
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.n, GL_UNSIGNED_INT, None)


class GPoints:
    """Dynamic point cloud: pos(3) color(4) size(1)."""
    def __init__(self, maxn):
        self.maxn = maxn
        self.vao = C.c_uint()
        glGenVertexArrays(1, C.byref(self.vao))
        glBindVertexArray(self.vao)
        self.vbo = C.c_uint()
        glGenBuffers(1, C.byref(self.vbo))
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, maxn * 32, None, GL_DYNAMIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, 0, 32, C.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 4, GL_FLOAT, 0, 32, C.c_void_p(12))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 1, GL_FLOAT, 0, 32, C.c_void_p(28))
        glEnableVertexAttribArray(2)
        glBindVertexArray(0)
        self.n = 0

    def update(self, data):
        data = np.ascontiguousarray(data[: self.maxn], dtype=np.float32)
        self.n = len(data)
        if self.n:
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferSubData(GL_ARRAY_BUFFER, 0, data.nbytes, data.ctypes.data)

    def draw(self):
        if self.n:
            glBindVertexArray(self.vao)
            glDrawArrays(GL_POINTS, 0, self.n)


class Target:
    """4x MSAA render target + resolve buffer + readback."""
    def __init__(self, w, h, samples=4):
        self.w, self.h = w, h
        self.fbo = C.c_uint(); glGenFramebuffers(1, C.byref(self.fbo))
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        rc = C.c_uint(); glGenRenderbuffers(1, C.byref(rc)); glBindRenderbuffer(GL_RENDERBUFFER, rc)
        glRenderbufferStorageMultisample(GL_RENDERBUFFER, samples, GL_RGBA8, w, h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rc)
        rd = C.c_uint(); glGenRenderbuffers(1, C.byref(rd)); glBindRenderbuffer(GL_RENDERBUFFER, rd)
        glRenderbufferStorageMultisample(GL_RENDERBUFFER, samples, GL_DEPTH_COMPONENT24, w, h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, rd)
        st = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if st != 0x8CD5:
            raise RuntimeError('MSAA fbo incomplete %x' % st)
        self.rfbo = C.c_uint(); glGenFramebuffers(1, C.byref(self.rfbo))
        glBindFramebuffer(GL_FRAMEBUFFER, self.rfbo)
        rr = C.c_uint(); glGenRenderbuffers(1, C.byref(rr)); glBindRenderbuffer(GL_RENDERBUFFER, rr)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, w, h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rr)
        st = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if st != 0x8CD5:
            raise RuntimeError('resolve fbo incomplete %x' % st)
        self.buf = np.empty((h, w, 3), np.uint8)

    def bind(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.w, self.h)

    def read(self):
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.fbo)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.rfbo)
        glBlitFramebuffer(0, 0, self.w, self.h, 0, 0, self.w, self.h, GL_COLOR_BUFFER_BIT, GL_NEAREST)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.rfbo)
        glPixelStorei(GL_PACK_ALIGNMENT, 1)
        glReadPixels(0, 0, self.w, self.h, GL_RGB, GL_UNSIGNED_BYTE, self.buf.ctypes.data)
        return self.buf[::-1].copy()


class GTexMesh:
    """Dynamic textured grid mesh: pos(3) uv(2)."""
    def __init__(self, nverts, T):
        self.vao = C.c_uint(); glGenVertexArrays(1, C.byref(self.vao)); glBindVertexArray(self.vao)
        self.vbo = C.c_uint(); glGenBuffers(1, C.byref(self.vbo)); glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, nverts * 20, None, GL_DYNAMIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, 0, 20, C.c_void_p(0)); glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, 0, 20, C.c_void_p(12)); glEnableVertexAttribArray(1)
        self.ebo = C.c_uint(); glGenBuffers(1, C.byref(self.ebo)); glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        idx = np.ascontiguousarray(T, dtype=np.uint32)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx.ctypes.data, GL_STATIC_DRAW)
        self.n = idx.size
        glBindVertexArray(0)

    def update(self, P, UV):
        data = np.ascontiguousarray(np.hstack([P, UV]), dtype=np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferSubData(GL_ARRAY_BUFFER, 0, data.nbytes, data.ctypes.data)

    def draw(self):
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.n, GL_UNSIGNED_INT, None)


def texture_rgba(img):
    a = np.ascontiguousarray(np.asarray(img.convert('RGBA'), dtype=np.uint8))
    h, w = a.shape[:2]
    tex = C.c_uint(); glGenTextures(1, C.byref(tex))
    glActiveTexture(0x84C0); glBindTexture(0x0DE1, tex)
    glTexImage2D(0x0DE1, 0, GL_RGBA8, w, h, 0, 0x1908, GL_UNSIGNED_BYTE, a.ctypes.data)
    glGenerateMipmap(0x0DE1)
    glTexParameteri(0x0DE1, 0x2801, 0x2703)
    glTexParameteri(0x0DE1, 0x2800, 0x2601)
    glTexParameteri(0x0DE1, 0x2802, 0x812F)
    glTexParameteri(0x0DE1, 0x2803, 0x812F)
    return tex
