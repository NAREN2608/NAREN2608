import io
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT_DIR = Path(__file__).parent / "fonts"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "assets")
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- tokens
C = {
    "bg": "#08080D",       # negro profundo
    "surface": "#101018",  # superficie elevada
    "line": "#2A2740",     # hairlines con tinte violeta
    "purple": "#8B5CF6",   # morado principal
    "violet": "#A78BFA",   # violeta eléctrico
    "white": "#F5F3FF",    # blanco
    "gray": "#92909F",     # gris secundario
    "fill": "#7C3AED",     # morado profundo: rellenos con texto blanco (contraste AA)
}
W = 1000   # ancho base de todos los paneles
M = 56     # margen


# ---------------------------------------------------------------- fuentes
class Face:
    def __init__(self, filename):
        f = TTFont(str(next(FONT_DIR.glob(f"x_*/package/files/{filename}"))))
        f.flavor = None
        buf = io.BytesIO()
        f.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        self.order = self.tt.getGlyphOrder()
        self.gs = self.tt.getGlyphSet()
        self.upem = self.tt["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(data))

    def shape(self, text, size, tracking=0.0):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        s = size / self.upem
        x, out = 0.0, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            out.append((self.order[info.codepoint], x + pos.x_offset * s))
            x += pos.x_advance * s + tracking * size
        return out, x - tracking * size  # sin tracking tras la última letra


DISPLAY = Face("bricolage-grotesque-latin-800-normal.woff")
TEXT = Face("bricolage-grotesque-latin-500-normal.woff")
MONO = Face("jetbrains-mono-latin-500-normal.woff")


def width(face, text, size, tracking=0.0):
    return face.shape(text, size, tracking)[1]


def num(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


_DEFS = {}


def text(face, s, x, y, size, fill, anchor="start", tracking=0.0):
    """Texto convertido a trazos; cada glifo se define una vez por archivo y se reutiliza."""
    glyphs, w = face.shape(s, size, tracking)
    if anchor == "middle":
        x -= w / 2
    elif anchor == "end":
        x -= w
    k = size / face.upem
    uses = []
    for name, gx in glyphs:
        key = (id(face), name, round(size, 1))
        if key not in _DEFS:
            pen = SVGPathPen(face.gs, ntos=num)
            face.gs[name].draw(TransformPen(pen, (k, 0, 0, -k, 0, 0)))
            d = pen.getCommands()
            _DEFS[key] = (f"g{len(_DEFS)}", d)
        gid, d = _DEFS[key]
        if d:  # los espacios no tienen contorno
            uses.append(f'<use href="#{gid}" x="{num(x + gx)}" y="{num(y)}"/>')
    return f'<g fill="{fill}">{"".join(uses)}</g>'


# ---------------------------------------------------------------- utilidades
def svg(w, h, title, body, desc="", bg=True):
    d = f"<desc>{desc}</desc>" if desc else ""
    defs = "".join(f'<path id="{gid}" d="{path}"/>' for gid, path in _DEFS.values() if f'#{gid}"' in body)
    _DEFS.clear()
    bgr = f'<rect width="{w}" height="{h}" fill="{C["bg"]}"/>' if bg else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{title}">'
        f"<title>{title}</title>{d}<defs>{defs}</defs>{bgr}{body}</svg>"
    )


def write(name, content):
    p = OUT / name
    p.write_text(content, encoding="utf-8")
    print(f"{name:22s} {p.stat().st_size/1024:5.1f} KB")


def rect(x, y, w, h, fill="none", stroke=None, sw=1.5, dash=None, rx=0):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    d = f' stroke-dasharray="{dash}"' if dash else ""
    r = f' rx="{rx}"' if rx else ""
    return f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" fill="{fill}"{s}{d}{r}/>'


def line(x1, y1, x2, y2, stroke, sw=1):
    return (f'<path d="M{num(x1)} {num(y1)}L{num(x2)} {num(y2)}" '
            f'stroke="{stroke}" stroke-width="{sw}" fill="none"/>')


def ruler(y, x1=M, x2=W - M, step=20, major=100):
    """Regla con marcas: detalle técnico de la retícula."""
    parts = [line(x1, y, x2, y, C["line"], 1)]
    d = []
    x = x1
    i = 0
    while x <= x2 + 0.1:
        t = 12 if i % (major // step) == 0 else 6
        d.append(f"M{num(x)} {y}v{t}")
        x += step
        i += 1
    parts.append(f'<path d="{"".join(d)}" stroke="{C["line"]}" stroke-width="1" fill="none"/>')
    return "".join(parts)


# ---------------------------------------------------------------- portada
def cover():
    H = 500
    b = [ruler(40)]

    # monograma N formado por casillas de una retícula (como ubicaciones de bodega)
    cell, gap = 58, 8
    n = 5
    size = n * cell + (n - 1) * gap
    x0, y0 = W - M - size, 96
    lit = {(r, 0) for r in range(n)} | {(r, n - 1) for r in range(n)} | {(1, 1), (2, 2), (3, 3)}
    for r in range(n):
        for c in range(n):
            x, y = x0 + c * (cell + gap), y0 + r * (cell + gap)
            if (r, c) in lit:
                fill = C["white"] if (r, c) == (2, 2) else (C["violet"] if c not in (0, n - 1) else C["purple"])
                b.append(rect(x, y, cell, cell, fill=fill))
            else:
                b.append(rect(x + .75, y + .75, cell - 1.5, cell - 1.5, stroke=C["line"], sw=1.5))
    # coordenadas de la retícula (decorativas)
    for c in range(n):
        b.append(text(MONO, "ABCDE"[c], x0 + c * (cell + gap) + cell / 2, y0 - 14, 18, C["gray"], "middle"))
    for r in range(n):
        b.append(text(MONO, str(r + 1), x0 - 18, y0 + r * (cell + gap) + cell / 2 + 6, 18, C["gray"], "end"))

    # nombre
    target = 500
    s = 100
    wmax = width(DISPLAY, "Cipagauta", s, -0.025)
    s = s * target / wmax
    b.append(text(DISPLAY, "Naren", M, 168, s, C["white"], tracking=-0.025))
    b.append(text(DISPLAY, "Cipagauta", M, 168 + s * 0.94, s, C["white"], tracking=-0.025))
    y = 168 + s * 0.94 + 62
    b.append(text(TEXT, "Desarrollo de software y web", M, y, 34, C["violet"]))
    b.append(text(TEXT, "Ingeniería de Sistemas", M, y + 44, 24, C["gray"]))
    b.append(text(TEXT, "Universidad Antonio Nariño, Bogotá", M, y + 76, 24, C["gray"]))

    # estado
    sy = 452
    b.append(rect(M, sy - 15, 15, 15, fill=C["purple"]))
    b.append(text(TEXT, "Buscando prácticas, oportunidades y proyectos", M + 30, sy, 24, C["white"]))
    b.append(line(M, 478, W - M, 478, C["line"], 1))
    return svg(W, H, "Naren Stiven Cipagauta, desarrollo de software y web", "".join(b))


# ---------------------------------------------------------------- encabezados de sección
SECTIONS = ["Perfil", "Tecnologías", "Proyecto destacado", "Formación e idiomas", "Contacto"]


def header(i, title):
    H = 92
    b = [line(M, 20, W - M, 20, C["line"], 1), line(M, 20, M + 64, 20, C["purple"], 4)]
    label = f"{i:02d}"
    ns = 52
    b.append(text(DISPLAY, label, M, 76, ns, C["purple"], tracking=-0.02))
    nx = M + width(DISPLAY, label, ns, -0.02) + 22
    b.append(text(DISPLAY, title, nx, 76, ns, C["white"], tracking=-0.02))
    # índice: una casilla por sección, la actual encendida
    cs, cg = 18, 6
    total = len(SECTIONS) * cs + (len(SECTIONS) - 1) * cg
    sx = W - M - total
    for k in range(len(SECTIONS)):
        x = sx + k * (cs + cg)
        if k == i - 1:
            b.append(rect(x, 46, cs, cs, fill=C["purple"]))
        else:
            b.append(rect(x + .75, 46.75, cs - 1.5, cs - 1.5, stroke=C["line"], sw=1.5))
    return svg(W, H, f"{label} {title}", "".join(b))


# ---------------------------------------------------------------- tecnologías
def chip(x, y, label, level, size=30, h=58, pad=22):
    w = width(TEXT, label, size) + 2 * pad
    ty = y + h / 2 + size * 0.34
    if level == "i":
        r = rect(x, y, w, h, fill=C["fill"])
    else:
        r = rect(x + .75, y + .75, w - 1.5, h - 1.5, stroke=C["purple"], sw=1.5)
    return r + text(TEXT, label, x + pad, ty, size, C["white"]), w


def flow(x, y, chips, limit, gap=12, step=70):
    """Coloca las etiquetas en línea y salta de renglón al llegar al límite. Devuelve (svg, borde inferior)."""
    out, cx, cy = [], x, y
    for name, lv in chips:
        w = width(TEXT, name, 30) + 44
        if cx + w > limit and cx > x:
            cx, cy = x, cy + step
        s_, _ = chip(cx, cy, name, lv)
        out.append(s_)
        cx += w + gap
    return "".join(out), cy + 58


def tech():
    b = []
    rows = [
        [("Web", M, W - M, [("HTML y CSS", "i"), ("JavaScript", "b"), ("TypeScript", "b"), ("React", "b"), ("PHP", "b")])],
        [("Programación general", M, W - M, [("Python", "i"), ("C++", "b"), ("Kotlin", "b")])],
        [("Datos", M, 340, [("MySQL", "b")]),
         ("Entorno de trabajo", 360, W - M, [("Docker", "i"), ("Git y GitHub", "i")])],
    ]
    y = 46
    for ri, row in enumerate(rows):
        bottom = 0
        for label, x, limit, chips in row:
            b.append(text(TEXT, label, x, y + 6, 26, C["gray"]))
            s_, bt = flow(x, y + 28, chips, limit)
            b.append(s_)
            bottom = max(bottom, bt)
        if ri < len(rows) - 1:
            b.append(line(M, bottom + 38, W - M, bottom + 38, C["line"], 1))
        y = bottom + 76
    ly = y + 4
    b.append(line(M, ly - 40, W - M, ly - 40, C["line"], 1))
    b.append(rect(M, ly - 20, 24, 24, fill=C["fill"]))
    b.append(text(TEXT, "Intermedio", M + 40, ly, 26, C["gray"]))
    lx = M + 40 + width(TEXT, "Intermedio", 26) + 48
    b.append(rect(lx + .75, ly - 19.25, 22.5, 22.5, stroke=C["purple"], sw=1.5))
    b.append(text(TEXT, "Básico", lx + 40, ly, 26, C["gray"]))
    H = int(ly + 44)
    alt = ("Tecnologías por categoría. Web: HTML y CSS (intermedio), JavaScript, TypeScript, React y PHP (básico). "
           "Programación general: Python (intermedio), C++ y Kotlin (básico). Datos: MySQL (básico). "
           "Entorno de trabajo: Docker y Git y GitHub (intermedio).")
    return svg(W, H, "Tecnologías por categoría y nivel", "".join(b), alt)


# ---------------------------------------------------------------- proyecto
def project():
    H = 526
    b = []
    b.append(text(DISPLAY, "Inventario Pro", M, 104, 76, C["white"], tracking=-0.025))
    # estado
    st = "Terminado y presentado"
    sw = width(TEXT, st, 24) + 44
    b.append(rect(W - M - sw, 58, sw, 46, fill=C["fill"]))
    b.append(text(TEXT, st, W - M - sw + 22, 90, 24, C["white"]))
    b.append(text(TEXT, "Proyecto de tesis, desarrollado en equipo", M, 152, 28, C["gray"]))

    # arquitectura dentro de Docker
    fy, fh = 196, 296
    b.append(rect(M + .75, fy, W - 2 * M - 1.5, fh, stroke=C["purple"], sw=1.5, dash="8 6"))
    b.append(text(TEXT, "Docker", M + 22, fy + 40, 24, C["violet"]))
    bw, bh, by = 248, 196, fy + 68
    gap = (W - 2 * M - 44 - 3 * bw) / 2
    blocks = [("Interfaz", ["React", "TypeScript", "Tailwind CSS"]),
              ("Servidor", ["PHP", "Apache"]),
              ("Base de datos", ["MySQL"])]
    for i, (t, items) in enumerate(blocks):
        x = M + 22 + i * (bw + gap)
        b.append(rect(x, by, bw, bh, fill=C["surface"], stroke=C["line"], sw=1.5))
        b.append(text(TEXT, t, x + 24, by + 52, 30, C["white"]))
        for k, it in enumerate(items):
            b.append(text(TEXT, it, x + 24, by + 100 + k * 38, 28, C["gray"]))
        if i < 2:
            ax1, ax2, ay = x + bw + 10, x + bw + gap - 10, by + bh / 2
            b.append(line(ax1, ay, ax2, ay, C["purple"], 2))
            b.append(f'<path d="M{num(ax2-10)} {num(ay-7)}L{num(ax2)} {num(ay)}L{num(ax2-10)} {num(ay+7)}" '
                     f'stroke="{C["purple"]}" stroke-width="2" fill="none"/>')
    alt = ("Inventario Pro, proyecto de tesis desarrollado en equipo, terminado y presentado. Arquitectura dentro de Docker: "
           "interfaz con React, TypeScript y Tailwind CSS; servidor con PHP y Apache; base de datos MySQL.")
    return svg(W, H, "Inventario Pro: arquitectura general", "".join(b), alt)


# ---------------------------------------------------------------- botones
def button(name, label, filled):
    w = int(width(TEXT, label, 26) + 64)
    h = 60
    if filled:
        body = rect(0, 0, w, h, fill=C["fill"]) + text(TEXT, label, w / 2, 39, 26, C["white"], "middle")
    else:
        body = rect(.75, .75, w - 1.5, h - 1.5, fill=C["bg"], stroke=C["purple"], sw=1.5) + text(TEXT, label, w / 2, 39, 26, C["white"], "middle")
    write(name, svg(w, h, label, body, bg=False))


# ---------------------------------------------------------------- pie
def footer():
    H = 120
    b = [ruler(24)]
    cell, gap, n = 14, 4, 5
    x0, y0 = M, 52
    lit = {(r, 0) for r in range(n)} | {(r, n - 1) for r in range(n)} | {(1, 1), (2, 2), (3, 3)}
    for r in range(n):
        for c in range(n):
            x, y = x0 + c * (cell + gap), y0 + r * (cell + gap)
            if (r, c) in lit:
                b.append(rect(x, y, cell, cell, fill=C["purple"]))
            else:
                b.append(rect(x + .5, y + .5, cell - 1, cell - 1, stroke=C["line"], sw=1))
    tx = x0 + n * cell + (n - 1) * gap + 28
    b.append(text(DISPLAY, "Soluciones limpias y estructuradas.", tx, 92, 36, C["white"], tracking=-0.02))
    return svg(W, H, "Soluciones limpias y estructuradas", "".join(b))


if __name__ == "__main__":
    write("cover.svg", cover())
    slugs = ["perfil", "tecnologias", "proyecto", "formacion", "contacto"]
    for i, (slug, title) in enumerate(zip(slugs, SECTIONS), 1):
        write(f"h-{slug}.svg", header(i, title))
    write("tech.svg", tech())
    write("project-inventario-pro.svg", project())
    button("btn-cv.svg", "Hoja de vida", True)
    button("btn-linkedin.svg", "LinkedIn", False)
    button("btn-correo.svg", "Correo", False)
    write("footer.svg", footer())
