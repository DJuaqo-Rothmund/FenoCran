"""
tools/make_cran_art.py
======================
Dibuja el arte base de FenoCran con el mismo estilo de FenoRubus (ilustración plana de
trazo oscuro, sombra interior y brillo):

* assets/logo_source.png      cranberry-reloj dentro del círculo punteado con los dibujos
                              del ciclo (yema, flor, fruta verde, fruta roja). Misma
                              composición que el logo de FenoRubus, para que
                              tools/make_splash_layers.py lo separe en capas igual.
* assets/wordmark_source.png  letra «FenoCran App» en trazo negro con volumen y achurado
                              (make_ui_assets.make_wordmark la tiñe con el degradé).
* assets/ui/berries/*.png     un ramillete por variedad (color y gris).
* assets/ui/logo_line*.png    el logo a línea (pantalla de inicio e informe PDF).
* assets/ui/start_predio.png  botón «Predio»: cama de cranberry con hoja y frutos, a línea.
* assets/ui/start_id.png      botón «I+D» recoloreado en burdeos.

    python tools/make_cran_art.py
    python tools/make_ui_assets.py && python tools/make_start_assets.py
    python tools/make_splash_layers.py && python tools/make_splash_lottie.py
"""
from __future__ import annotations

import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SS = 4   # supersampling

OUTLINE = (52, 12, 22, 255)
BERRY = (142, 27, 44)          # theme.BERRY
BERRY_SHADE = (94, 15, 28)     # theme.BERRY_DARK
BERRY_LIGHT = (196, 86, 106)   # theme.BERRY_LIGHT
LEAF = (78, 128, 82)
LEAF_DARK = (31, 77, 58)       # theme.LEAF
LEAF_LINE = (24, 58, 40, 255)
STEM = (96, 78, 52)
RING_RGB = (180, 172, 168)     # = make_splash_layers.RING_RGB
HAND_RGB = (61, 63, 59)        # = make_splash_layers.HAND_RGB


def _s(v):
    return v * SS


def berry(d: ImageDraw.ImageDraw, cx, cy, rx, ry, base=BERRY, shade=BERRY_SHADE,
          light=BERRY_LIGHT, line=4.0, calyx=True, angle=0.0):
    """Cranberry: óvalo con sombra hacia abajo-derecha, brillo arriba-izquierda y la
    estrellita del cáliz (extremo floral)."""
    box = [_s(cx - rx), _s(cy - ry), _s(cx + rx), _s(cy + ry)]
    d.ellipse(box, fill=OUTLINE)
    w = _s(line)
    d.ellipse([box[0] + w, box[1] + w, box[2] - w, box[3] - w], fill=shade + (255,))
    # cuerpo (desplazado arriba-izquierda: deja una media luna de sombra)
    k = .82
    ox, oy = -rx * .1, -ry * .1
    d.ellipse([_s(cx + ox - rx * k), _s(cy + oy - ry * k), _s(cx + ox + rx * k),
               _s(cy + oy + ry * k)], fill=base + (255,))
    # brillo
    hx, hy = cx - rx * .42, cy - ry * .45
    d.ellipse([_s(hx - rx * .22), _s(hy - ry * .13), _s(hx + rx * .22), _s(hy + ry * .13)],
              fill=light + (255,))
    d.ellipse([_s(hx - rx * .08), _s(hy - ry * .05), _s(hx + rx * .06), _s(hy + ry * .05)],
              fill=(250, 226, 230, 255))
    if calyx:
        ax, ay = cx + math.sin(angle) * ry * .55, cy + math.cos(angle) * ry * .55
        r = max(rx, ry) * .14
        for i in range(5):
            t = angle + i * 2 * math.pi / 5
            d.line([_s(ax), _s(ay), _s(ax + math.cos(t) * r), _s(ay + math.sin(t) * r)],
                   fill=OUTLINE, width=max(1, round(_s(line * .55))))


def leaf(d: ImageDraw.ImageDraw, x, y, length, width, ang, fill=LEAF, line=3.0):
    """Hoja ovalada y brillante del cranberry (pequeña, con nervio central)."""
    pts = []
    for i in range(41):
        t = i / 40 * 2 * math.pi
        px, py = math.cos(t) * length / 2, math.sin(t) * width / 2
        px += length / 2
        c, s = math.cos(ang), math.sin(ang)
        pts.append((_s(x + px * c - py * s), _s(y + px * s + py * c)))
    d.polygon(pts, fill=fill + (255,), outline=LEAF_LINE)
    d.line(pts + [pts[0]], fill=LEAF_LINE, width=round(_s(line)), joint="curve")
    c, s = math.cos(ang), math.sin(ang)
    d.line([_s(x + length * .12 * c), _s(y + length * .12 * s), _s(x + length * .8 * c),
            _s(y + length * .8 * s)], fill=LEAF_LINE, width=round(_s(line * .55)))


def curve(d, pts, width, fill):
    """Polilínea suave (Bezier cuadrática por tramos)."""
    out = []
    for (x0, y0), (x1, y1), (x2, y2) in zip(pts, pts[1:], pts[2:]):
        for i in range(12):
            t = i / 12
            out.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t * t * x2,
                        (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t * t * y2))
    out.append(pts[-1])
    d.line([(_s(x), _s(y)) for x, y in out], fill=fill, width=round(_s(width)), joint="curve")


def flower(d, cx, cy, r):
    """Flor del cranberry: pétalos reflejos blanco rosado y la columna de anteras."""
    for i in range(4):
        t = math.radians(45 + i * 90)
        px, py = cx + math.cos(t) * r * .55, cy + math.sin(t) * r * .55
        d.ellipse([_s(px - r * .5), _s(py - r * .32), _s(px + r * .5), _s(py + r * .32)],
                  fill=(246, 230, 234, 255), outline=(120, 96, 100, 255), width=_s(2))
    d.ellipse([_s(cx - r * .22), _s(cy - r * .22), _s(cx + r * .22), _s(cy + r * .22)],
              fill=(214, 178, 82, 255), outline=(120, 90, 40, 255), width=_s(2))


def bud(d, cx, cy, r, color=(120, 40, 52), light=(176, 92, 104)):
    """Yema apretada: brácteas rojizas superpuestas en punta."""
    for i, (dx, sc) in enumerate(((-.38, .8), (.38, .8), (0, 1.0))):
        pts = [(cx + dx * r, cy - r * 1.05 * sc), (cx + dx * r + r * .5, cy + r * .45),
               (cx + dx * r, cy + r * .75), (cx + dx * r - r * .5, cy + r * .45)]
        d.polygon([(_s(x), _s(y)) for x, y in pts], fill=(light if i == 2 else color) + (255,),
                  outline=OUTLINE)
        d.line([(_s(x), _s(y)) for x, y in pts + [pts[0]]], fill=OUTLINE, width=_s(2))
    d.line([_s(cx), _s(cy + r * .7), _s(cx), _s(cy + r * 1.3)], fill=STEM + (255,), width=_s(3))


def clock(d, fx, fy, r):
    """Esfera blanca con 4 marcas y manijas a las 10:10 (ver make_splash_layers)."""
    d.ellipse([_s(fx - r - 4), _s(fy - r - 4), _s(fx + r + 4), _s(fy + r + 4)],
              fill=(46, 48, 44, 255))
    d.ellipse([_s(fx - r), _s(fy - r), _s(fx + r), _s(fy + r)], fill=(255, 255, 255, 255))
    for t in (0, 90, 180, 270):
        a = math.radians(t)
        x0, y0 = fx + math.cos(a) * r * .72, fy - math.sin(a) * r * .72
        x1, y1 = fx + math.cos(a) * r * .9, fy - math.sin(a) * r * .9
        d.line([_s(x0), _s(y0), _s(x1), _s(y1)], fill=HAND_RGB + (255,), width=_s(4))
    for ln, deg in ((26.8, 152.0), (37.1, 32.6)):
        a = math.radians(deg)
        d.line([_s(fx), _s(fy), _s(fx + math.cos(a) * ln), _s(fy - math.sin(a) * ln)],
               fill=HAND_RGB + (255,), width=round(_s(5.6)))
    d.ellipse([_s(fx - 6), _s(fy - 6), _s(fx + 6), _s(fy + 6)], fill=HAND_RGB + (255,))


def finish(img: Image.Image, size) -> Image.Image:
    return img.resize(size, Image.LANCZOS)


# ------------------------------------------------------------------ logo
def make_logo():
    W, H = 384, 369
    img = Image.new("RGBA", (_s(W), _s(H)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rcx, rcy, R = 192, 186, 168
    # círculo punteado
    n = 44
    for i in range(n):
        if i in (0, 11, 22, 33, 6, 17, 28, 39):   # huecos donde van los dibujos
            continue
        a0, a1 = 360 * i / n, 360 * (i + .55) / n
        d.arc([_s(rcx - R), _s(rcy - R), _s(rcx + R), _s(rcy + R)], a0, a1,
              fill=RING_RGB + (255,), width=_s(6))
    # tallo y hojas (unidos al racimo: forman una sola pieza con el fruto)
    curve(d, [(206, 104), (205, 72), (216, 44)], 7, OUTLINE)
    curve(d, [(206, 104), (205, 72), (216, 44)], 4, (90, 150, 70, 255))
    for x, y, ln, wd, ang in ((205, 80, 52, 24, math.radians(-165)),
                              (206, 76, 54, 24, math.radians(-20)),
                              (211, 56, 38, 18, math.radians(-125)),
                              (212, 58, 38, 18, math.radians(-55))):
        leaf(d, x, y, ln, wd, ang, line=3.2)
    curve(d, [(206, 100), (170, 108), (150, 150)], 5, OUTLINE)
    curve(d, [(206, 100), (196, 140), (186, 214)], 5, OUTLINE)
    # racimo: dos cranberries chicos y el grande con el reloj
    berry(d, 138, 196, 52, 56, angle=math.radians(25))
    berry(d, 180, 262, 50, 46, angle=math.radians(-10))
    berry(d, 236, 180, 76, 80, angle=math.radians(-30), calyx=False)
    clock(d, 236.25, 177.5, 40)
    # dibujos del ciclo sobre el círculo (piezas separadas)
    bud(d, rcx + R * math.cos(math.radians(180)), rcy, 20)                         # yema
    flower(d, rcx + R * math.cos(math.radians(140)), rcy + R * math.sin(math.radians(140)), 22)
    gx, gy = rcx + R * math.cos(math.radians(90)), rcy + R * math.sin(math.radians(90))
    berry(d, gx, gy, 15, 15, base=(142, 182, 96), shade=(84, 120, 56), light=(196, 222, 160),
          line=2.5)                                                               # fruta verde
    for deg in (40, -10):
        x, y = rcx + R * math.cos(math.radians(deg)), rcy + R * math.sin(math.radians(deg))
        berry(d, x - 7, y + 3, 14, 14, line=2.5)
        berry(d, x + 9, y - 6, 12, 12, line=2.5, calyx=False)
    finish(img, (W, H)).save(os.path.join(ASSETS, "logo_source.png"))


# ------------------------------------------------------------- wordmark
def _font(size):
    for f in ("/usr/share/fonts/opentype/inter/Inter-Black.otf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _word(text, size, rnd):
    """Letras gruesas con volumen hacia abajo-izquierda, achurado y trazo negro."""
    font = _font(size)
    glyphs = []
    for ch in text:
        box = font.getbbox(ch)
        w, h = box[2] - box[0], size * 1.25
        g = Image.new("L", (int(w + size * .6), int(h + size * .6)), 0)
        ImageDraw.Draw(g).text((size * .3 - box[0], size * .3), ch, font=font, fill=255)
        g = g.rotate(rnd.uniform(-6, 6), resample=Image.BICUBIC, expand=False)
        glyphs.append((g, w))
    W = int(sum(w for _g, w in glyphs) + size * 1.2)
    H = int(size * 1.9)
    mask = Image.new("L", (W, H), 0)
    x = size * .35
    for g, w in glyphs:
        mask.paste(g, (int(x - size * .3), int(rnd.uniform(-.04, .04) * size)), g)
        x += w + size * .09
    depth = size * .09
    ext = Image.new("L", mask.size, 0)
    for i in range(1, int(depth) + 1):
        ext = ImageChops.lighter(ext, ImageChops.offset(mask, -i, i))
    stroke = max(3, int(size * .045))
    out = Image.new("L", mask.size, 255)                       # papel blanco
    hatch = Image.new("L", mask.size, 255)
    hd = ImageDraw.Draw(hatch)
    for k in range(-H, W, max(4, int(size * .06))):
        hd.line([k, H, k + H, 0], fill=0, width=max(2, int(size * .018)))
    ext_only = ImageChops.subtract(ext, mask)
    ext_fat = ext_only.filter(ImageFilter.MaxFilter(3))
    out.paste(0, (0, 0), ext_fat)                              # volumen negro…
    light = ImageChops.subtract(ext_only, mask.filter(ImageFilter.MaxFilter(stroke * 2 + 1)))
    out.paste(hatch, (0, 0), light.point(lambda v: 255 if v > 128 else 0))   # …achurado
    edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(stroke * 2 + 1)), mask)
    out.paste(0, (0, 0), edge)                                 # contorno
    inner = mask.filter(ImageFilter.MinFilter(stroke + 1 if stroke % 2 == 0 else stroke))
    shade = ImageChops.subtract(inner, ImageChops.offset(inner, -int(size * .05), int(size * .05)))
    sh = Image.new("L", mask.size, 255)
    sh.paste(hatch, (0, 0), shade.point(lambda v: 255 if v > 128 else 0))
    out = ImageChops.darker(out, sh)
    alpha = ImageChops.lighter(mask.filter(ImageFilter.MaxFilter(stroke * 2 + 1)), ext_fat)
    rgba = Image.merge("RGBA", (out, out, out, alpha))
    return rgba.crop(alpha.getbbox())


def make_wordmark():
    rnd = random.Random(7)
    top = _word("FenoCran", 150, rnd)
    bottom = _word("App", 150, rnd)
    W = max(top.width, bottom.width)
    H = top.height + bottom.height + 10
    out = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    out.alpha_composite(top, ((W - top.width) // 2, 0))
    out.alpha_composite(bottom, ((W - bottom.width) // 2, top.height + 10))
    out = out.resize((W // 2, H // 2), Image.LANCZOS)
    out.save(os.path.join(ASSETS, "wordmark_source.png"))


# --------------------------------------------------------- variedades
# (clave, forma (rx, ry), color base, sombra, brillo, n.º de frutos)
VARIETIES = {
    "stevens": ((30, 30), (142, 27, 44), (94, 15, 28), (196, 86, 106), 3),
    "ben_lear": ((26, 32), (110, 18, 36), (70, 10, 22), (170, 70, 88), 3),
    "pilgrim": ((30, 36), (128, 32, 70), (82, 18, 46), (186, 104, 140), 2),
    "mullica_queen": ((32, 31), (176, 30, 48), (118, 18, 32), (226, 110, 124), 4),
}


def _gray(im: Image.Image) -> Image.Image:
    g = im.convert("LA").convert("RGBA")
    r, gg, b, a = g.split()
    light = Image.merge("RGB", (r, gg, b)).point(lambda v: int(150 + v * .4))
    return Image.merge("RGBA", (*light.split(), a))


def make_varieties():
    out_dir = os.path.join(ASSETS, "ui", "berries")
    for f in os.listdir(out_dir):
        if f.endswith(".png"):
            os.remove(os.path.join(out_dir, f))
    for key, ((rx, ry), base, shade, light, n) in VARIETIES.items():
        W, H = 202, 239
        img = Image.new("RGBA", (_s(W), _s(H)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # vertical con hojitas
        curve(d, [(101, 228), (98, 150), (104, 70)], 6, OUTLINE)
        curve(d, [(101, 228), (98, 150), (104, 70)], 3, (96, 140, 70, 255))
        for i, y in enumerate(range(54, 150, 18)):
            side = -1 if i % 2 else 1
            leaf(d, 101, y, 40 - i * 3, 17 - i, math.radians(-90 + side * 55), fill=LEAF,
                 line=2.4)
        spots = [(68, 168), (134, 172), (100, 200), (72, 116)][:n]
        for x, y in spots:
            curve(d, [(101, 150), ((101 + x) / 2, y - 30), (x, y - ry + 4)], 3, OUTLINE)
        for x, y in sorted(spots, key=lambda p: p[1]):
            berry(d, x, y, rx, ry, base=base, shade=shade, light=light, line=3.5,
                  angle=math.radians(random.Random(key).uniform(-30, 30)))
        im = finish(img, (W, H))
        im.save(os.path.join(out_dir, f"{key}.png"))
        _gray(im).save(os.path.join(out_dir, f"{key}_gris.png"))


# ------------------------------------------------------------ a línea
def _line_logo(side, ink, bg=None):
    """Mismo logo, solo trazos de un color (estilo de los íconos de inicio)."""
    W = 384
    img = Image.new("RGBA", (_s(W), _s(W)), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = _s(7)
    rcx, rcy, R = 192, 194, 170
    n = 40
    for i in range(n):
        a0, a1 = 360 * i / n, 360 * (i + .55) / n
        d.arc([_s(rcx - R), _s(rcy - R), _s(rcx + R), _s(rcy + R)], a0, a1, fill=ink, width=_s(6))

    def ring(cx, cy, rx, ry, w=lw, fill=None):
        d.ellipse([_s(cx - rx), _s(cy - ry), _s(cx + rx), _s(cy + ry)], outline=ink, width=w,
                  fill=fill or (bg or (0, 0, 0, 0)))

    curve(d, [(206, 112), (205, 80), (216, 52)], 7, ink)
    for x, y, ln, wd, ang in ((205, 88, 52, 24, -165), (206, 84, 54, 24, -20),
                              (211, 64, 38, 18, -125), (212, 66, 38, 18, -55)):
        pts = []
        a = math.radians(ang)
        for i in range(41):
            t = i / 40 * 2 * math.pi
            px, py = math.cos(t) * ln / 2 + ln / 2, math.sin(t) * wd / 2
            pts.append((_s(x + px * math.cos(a) - py * math.sin(a)),
                        _s(y + px * math.sin(a) + py * math.cos(a))))
        d.polygon(pts, fill=bg or (0, 0, 0, 0))
        d.line(pts + [pts[0]], fill=ink, width=_s(5), joint="curve")
    for cx, cy, rx, ry in ((138, 204, 52, 56), (180, 270, 50, 46), (236, 188, 76, 80)):
        ring(cx, cy, rx, ry)
        if rx < 70:   # el grande lleva el reloj: sin brillo
            d.arc([_s(cx - rx * .62), _s(cy - ry * .62), _s(cx + rx * .62), _s(cy + ry * .62)],
                  200, 250, fill=ink, width=_s(5))
    ring(236, 185, 44, 44)
    ring(236, 185, 36, 36, w=_s(4))
    for t in (0, 90, 180, 270):
        a = math.radians(t)
        d.line([_s(236 + math.cos(a) * 26), _s(185 - math.sin(a) * 26),
                _s(236 + math.cos(a) * 32), _s(185 - math.sin(a) * 32)], fill=ink, width=_s(4))
    for ln, deg in ((20, 152.0), (28, 32.6)):
        a = math.radians(deg)
        d.line([_s(236), _s(185), _s(236 + math.cos(a) * ln), _s(185 - math.sin(a) * ln)],
               fill=ink, width=_s(5))
    for deg, r in ((180, 15), (140, 13), (90, 12), (40, 13), (-10, 13)):
        x, y = rcx + R * math.cos(math.radians(deg)), rcy + R * math.sin(math.radians(deg))
        d.ellipse([_s(x - r - 6), _s(y - r - 6), _s(x + r + 6), _s(y + r + 6)], fill=bg or (0, 0, 0, 0))
        if deg == 140:
            for i in range(4):
                t = math.radians(45 + i * 90)
                px, py = x + math.cos(t) * r * .6, y + math.sin(t) * r * .6
                ring(px, py, r * .5, r * .5, w=_s(3))
        else:
            ring(x, y, r, r * (1.2 if deg == 180 else 1), w=_s(4))
    return img.resize((side, side), Image.LANCZOS)


def make_line_assets():
    ui_dir = os.path.join(ASSETS, "ui")
    _line_logo(420, BERRY + (255,)).save(os.path.join(ui_dir, "logo_line.png"))
    _line_logo(468, (0, 0, 0, 255), bg=(255, 255, 255, 255)).convert("RGB").save(
        os.path.join(ui_dir, "logo_line_report.png"))
    # Botón «Predio»: cama (bancal) con hileras, una hoja y tres cranberries, a línea.
    ink = (31, 77, 58, 255)
    W = 360
    img = Image.new("RGBA", (_s(W), _s(W)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bed = [(30, 150), (250, 60), (334, 120), (120, 230)]
    d.polygon([(_s(x), _s(y)) for x, y in bed], outline=ink, width=_s(9))
    d.line([(_s(x), _s(y)) for x, y in bed + [bed[0]]], fill=ink, width=_s(9), joint="curve")
    for i in range(1, 6):
        t = i / 6
        x0, y0 = 30 + (250 - 30) * t, 150 + (60 - 150) * t
        x1, y1 = 120 + (334 - 120) * t, 230 + (120 - 230) * t
        pts = [(x0 + (x1 - x0) * u + math.sin(u * 9 + i) * 3, y0 + (y1 - y0) * u) for u in
               [j / 10 for j in range(11)]]
        d.line([(_s(x), _s(y)) for x, y in pts], fill=ink, width=_s(5), joint="curve")
    d.line([_s(30), _s(150), _s(30), _s(185), _s(120), _s(268), _s(334), _s(156), _s(334), _s(120)],
           fill=ink, width=_s(9), joint="curve")
    pts = []
    for i in range(41):
        t = i / 40 * 2 * math.pi
        px, py = math.cos(t) * 70 + 70, math.sin(t) * 34
        a = math.radians(-58)
        pts.append((_s(110 + px * math.cos(a) - py * math.sin(a)),
                    _s(325 + px * math.sin(a) + py * math.cos(a))))
    d.polygon(pts, fill=(0, 0, 0, 0))
    d.line(pts + [pts[0]], fill=ink, width=_s(8), joint="curve")
    d.line([_s(110), _s(325), _s(180), _s(208)], fill=ink, width=_s(6))
    for cx, cy, r in ((250, 270, 40), (310, 250, 32), (290, 316, 30)):
        d.ellipse([_s(cx - r), _s(cy - r), _s(cx + r), _s(cy + r)], fill=(0, 0, 0, 0),
                  outline=ink, width=_s(8))
        d.arc([_s(cx - r * .6), _s(cy - r * .6), _s(cx + r * .6), _s(cy + r * .6)], 200, 250,
              fill=ink, width=_s(6))
    for x, y, r in ((300, 40, 12), (40, 60, 9), (345, 200, 8)):
        d.polygon([(_s(x), _s(y - r)), (_s(x + r * .3), _s(y - r * .3)), (_s(x + r), _s(y)),
                   (_s(x + r * .3), _s(y + r * .3)), (_s(x), _s(y + r)), (_s(x - r * .3), _s(y + r * .3)),
                   (_s(x - r), _s(y)), (_s(x - r * .3), _s(y - r * .3))], fill=ink)
    img.resize((W, W), Image.LANCZOS).save(os.path.join(ui_dir, "start_predio.png"))
    # Botón «I+D»: el mismo dibujo, en burdeos.
    sid = Image.open(os.path.join(ui_dir, "start_id.png")).convert("RGBA")
    a = sid.split()[3]
    Image.merge("RGBA", (*Image.new("RGB", sid.size, BERRY).split(), a)).save(
        os.path.join(ui_dir, "start_id.png"))


if __name__ == "__main__":
    make_logo()
    make_wordmark()
    make_varieties()
    make_line_assets()
    print("Arte cranberry generado en", ASSETS)
