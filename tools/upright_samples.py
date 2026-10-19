"""
tools/upright_samples.py
========================
Fotos sintéticas de verticales (pruebas y demostración del conteo desde foto):
sobre fondo blanco, de lado en la cama y desde arriba. Devuelven la ruta y los recuadros
reales (0-1) con el estado de cada vertical.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter

TIP = {1: (110, 28, 40), 2: (236, 230, 220), 3: (176, 120, 95), 4: (150, 190, 90),
       5: (110, 170, 85), 6: (226, 206, 192), 7: (232, 205, 210), 8: (246, 232, 236),
       9: (200, 210, 120), 10: (150, 196, 100), 11: (160, 20, 40)}


def _upright(d, x, base, top, code, rnd, s=1.0):
    stem = (96, 70, 50) if code <= 4 else (100, 125, 65)
    d.line([x, base, x, top], fill=stem, width=max(2, int(3 * s)))
    leaf = (120, 38, 46) if code <= 2 else ((140, 70, 60) if code <= 4 else (80, 135, 70))
    n = 7
    for i in range(n):
        y = base - (base - top) * (i + .5) / (n + 1)
        side = 1 if i % 2 else -1
        d.ellipse([x + side * 2 * s - (0 if side > 0 else 13 * s), y - 4 * s,
                   x + side * 2 * s + (13 * s if side > 0 else 0), y + 4 * s], fill=leaf)
    r = (6 + (code > 4) * 3 + (code >= 9) * 2) * s
    d.ellipse([x - r, top - 2 * r, x + r, top], fill=TIP[code])
    if code in (6, 7, 8):
        for k in range(3):
            yy = top + (8 + k * 9) * s
            dx = (10 if k % 2 else -10) * s
            d.ellipse([x + dx - 4 * s, yy - 4 * s, x + dx + 4 * s, yy + 4 * s], fill=TIP[code])


def make(mode: str, path: str, codes: list[int], seed: int = 0, size=(900, 650)):
    rnd = random.Random(seed)
    W, H = size
    bg = {"board": (246, 245, 240), "side": (64, 82, 48), "top": (70, 60, 44)}[mode]
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    if mode != "board":
        for _ in range(1500):
            x, y = rnd.uniform(0, W), rnd.uniform(0, H)
            r = rnd.uniform(3, 7)
            c = (rnd.randint(55, 100), rnd.randint(60, 105), rnd.randint(35, 60))
            d.ellipse([x - r, y - r / 2, x + r, y + r / 2], fill=c)
    boxes = []
    n = len(codes)
    for i, code in enumerate(codes):
        if mode == "top":
            cols = max(1, int(math.ceil(math.sqrt(n))))
            cx = W * (i % cols + .5) / cols + rnd.uniform(-15, 15)
            cy = H * (i // cols + .5) / math.ceil(n / cols) + rnd.uniform(-15, 15)
            r = 26
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(80, 135, 70) if code > 4 else (120, 38, 46))
            d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=TIP[code])
            boxes.append({"x": (cx - r - 3) / W, "y": (cy - r - 3) / H, "w": (2 * r + 6) / W,
                          "h": (2 * r + 6) / H, "code": code})
            continue
        x = W * (i + .5) / n + rnd.uniform(-8, 8)
        base = H * (.9 if mode == "side" else .88) + rnd.uniform(-10, 10)
        top = H * rnd.uniform(.2, .32)
        _upright(d, x, base, top, code, rnd)
        r = (6 + (code > 4) * 3 + (code >= 9) * 2)
        x0, x1 = x - 22, x + 22
        y0 = top - 2 * r - 4
        boxes.append({"x": x0 / W, "y": y0 / H, "w": (x1 - x0) / W, "h": (base - y0 + 4) / H,
                      "code": code})
    im = im.filter(ImageFilter.GaussianBlur(.8))
    im.save(path, "JPEG", quality=90)
    return path, boxes
