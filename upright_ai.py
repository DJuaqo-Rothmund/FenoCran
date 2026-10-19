"""
upright_ai.py
=============
IA para contar verticales en una foto y sugerir el estado de cada uno (100 % local).

Tres tipos de foto (se pueden usar todos, incluso en el mismo registro):

* ``board``  verticales cortados y puestos sobre un fondo blanco (lo más preciso).
* ``side``   de lado, en la cama.
* ``top``    desde arriba, dentro de un marco.

Cómo sugiere:

1. **Dónde están los verticales** (recuadros):
   * modelo detector TFLite (``verticales.tflite``), si se entrenó uno con
     ``tools/train_upright_detector.py`` a partir de las fotos marcadas en la app;
   * si no hay modelo: en fondo blanco, segmentación de color (funciona desde el primer
     día); de lado y desde arriba, una ventana deslizante que compara cada zona de la
     foto con los verticales y el fondo que el evaluador ya marcó en fotos de ese tipo
     (aprende con cada foto aceptada; necesita unos ``MIN_POS`` verticales marcados).
2. **Estado de cada vertical**: k-NN con los recortes marcados (memoria de la IA) más
   los priors de color y de calendario del clasificador de la app.

Cada foto aceptada guarda sus recortes (verticales con su estado y trozos de fondo) en
la memoria común: así la IA mejora con el uso y el set queda listo para exportarse y
entrenar un detector de verdad (``export_yolo``).

Solo numpy + Pillow (sin scipy ni OpenCV: corre igual en Android).
"""
from __future__ import annotations

import json
import os
import random
import zipfile
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps

import phenology as ph
from ai_classifier import HandcraftedExtractor, PhenologyClassifier, color_profile

MODES = {
    "board": ("Sobre fondo blanco",
              "Corte los verticales y póngalos separados sobre una tabla o cartulina blanca. "
              "Es lo más preciso (recomendado)."),
    "side": ("De lado, en la cama",
             "Foto de costado a la altura de los verticales, con el fondo lo más parejo posible."),
    "top": ("Desde arriba (marco)",
            "Foto vertical sobre un marco (p. ej. 0,1 m²): se ven las puntas de los verticales."),
}
# Recuadro por defecto (ancho, alto, 0-1) al tocar la foto sin arrastrar.
DEFAULT_BOX = {"board": (.07, .32), "side": (.07, .34), "top": (.09, .09)}
MIN_POS = 10             # verticales marcados para empezar a sugerir de lado / desde arriba
MODEL_FILE = "verticales.tflite"


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float
    code: int | None = None
    conf: float = 0.0
    score: float = 0.0
    origin: str = "ai"

    def as_dict(self) -> dict:
        return {"x": round(self.x, 4), "y": round(self.y, 4), "w": round(self.w, 4),
                "h": round(self.h, 4), "code": self.code, "conf": round(self.conf, 3),
                "origin": self.origin}


@dataclass
class Detection:
    boxes: list[Box] = field(default_factory=list)
    method: str = ""          # modelo | segmentación | aprendida | ninguno
    message: str = ""


class CropExtractor(HandcraftedExtractor):
    """El mismo descriptor de la app, en recortes chicos (rápido para muchas ventanas)."""
    name = "cran-crop-hc64"
    input_size = 64


def load_rgb(path: str, max_side: int) -> Image.Image:
    img = Image.open(path)
    img.draft("RGB", (max_side, max_side))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side), Image.BILINEAR)
    return img


def iou(a: Box, b: Box) -> float:
    x0, y0 = max(a.x, b.x), max(a.y, b.y)
    x1, y1 = min(a.x + a.w, b.x + b.w), min(a.y + a.h, b.y + b.h)
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def nms(boxes: list[Box], thr: float = .3) -> list[Box]:
    out: list[Box] = []
    for b in sorted(boxes, key=lambda b: -b.score):
        if all(iou(b, o) < thr and not _center_inside(b, o) for o in out):
            out.append(b)
    return out


def _center_inside(a: Box, b: Box) -> bool:
    cx, cy = a.x + a.w / 2, a.y + a.h / 2
    return b.x <= cx <= b.x + b.w and b.y <= cy <= b.y + b.h


# ------------------------------------------------------------ morfología mínima
def _shift_or(mask: np.ndarray, r: int, op) -> np.ndarray:
    out = mask.copy()
    H, W = mask.shape
    pad = np.pad(mask, r, mode="constant", constant_values=(op is np.logical_and))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out = op(out, pad[r + dy:r + dy + H, r + dx:r + dx + W])
    return out


def dilate(m, r):
    return _shift_or(m, r, np.logical_or) if r > 0 else m


def erode(m, r):
    return _shift_or(m, r, np.logical_and) if r > 0 else m


def components(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """Componentes conexas (8 vecinos): [(x0, y0, x1, y1, área)]."""
    H, W = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    ys, xs = np.nonzero(mask)
    for sy, sx in zip(ys.tolist(), xs.tolist()):
        if seen[sy, sx]:
            continue
        q = deque([(sy, sx)])
        seen[sy, sx] = True
        x0 = x1 = sx
        y0 = y1 = sy
        n = 0
        while q:
            y, x = q.popleft()
            n += 1
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
        out.append((x0, y0, x1, y1, n))
    return out


def segment_board(img: Image.Image, max_side: int = 300) -> list[Box]:
    """Verticales sobre fondo blanco: todo lo que no es blanco/gris claro, agrupado."""
    small = img.copy()
    small.thumbnail((max_side, max_side), Image.BILINEAR)
    hsv = np.asarray(small.convert("HSV")).astype(np.float32)
    s, v = hsv[..., 1] / 255, hsv[..., 2] / 255
    fg = (s >= .16) | (v < .5)
    H, W = fg.shape
    # sin el borde de la foto (mesa, sombra del marco)
    edge = max(2, int(min(H, W) * .02))
    fg[:edge], fg[-edge:], fg[:, :edge], fg[:, -edge:] = False, False, False, False
    # Cierre: une hojas y botones con su tallo (sin apertura: el tallo mide 1-2 px y se
    # perdería; las motas se descartan por área).
    r = max(3, int(max(H, W) * .022))
    fg = erode(dilate(fg, r), r - 1)
    min_area = H * W * .002
    boxes = []
    for x0, y0, x1, y1, n in components(fg):
        if n < min_area or (y1 - y0 + 1) < H * .04:
            continue
        pad = 1
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
        x1, y1 = min(W - 1, x1 + pad), min(H - 1, y1 + pad)
        boxes.append(Box(x0 / W, y0 / H, (x1 - x0 + 1) / W, (y1 - y0 + 1) / H,
                         score=float(n), origin="ai"))
    return boxes


def foreground_profile(img: Image.Image) -> dict[str, float]:
    """Perfil de color solo del vertical (sin el fondo blanco de la tabla)."""
    from ai_classifier import color_masks
    hsv = np.asarray(img.convert("HSV"))
    s, v = hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    fg = (s >= .16) | (v < .5)
    n = max(1.0, float(fg.sum()))
    prof = {k: float((m & fg).sum()) / n for k, m in color_masks(hsv).items()}
    # Pétalos y yema blanca: blanco con borde de color, no el papel (cuenta poco).
    prof["white"] = float((color_masks(hsv)["white"] & dilate(fg, 2) & ~fg).sum()) / n * .3
    return prof


def crop(img: Image.Image, b: Box, margin: float = .08) -> Image.Image:
    W, H = img.size
    mx, my = b.w * margin, b.h * margin
    x0, y0 = max(0, int((b.x - mx) * W)), max(0, int((b.y - my) * H))
    x1, y1 = min(W, int((b.x + b.w + mx) * W) + 1), min(H, int((b.y + b.h + my) * H) + 1)
    return img.crop((x0, y0, max(x1, x0 + 2), max(y1, y0 + 2)))


# -------------------------------------------------------------- detector TFLite
def decode_yolo(out: np.ndarray, n_classes: int = 11, conf: float = .35,
                input_size: int = 640) -> list[Box]:
    """Salida YOLOv8 exportada a TFLite: (1, 4+nc, N) o (1, N, 4+nc) con cx, cy, w, h
    (en píxeles del modelo o normalizados) y una puntuación por clase (E1…E11)."""
    a = np.asarray(out, dtype=np.float32).reshape(out.shape[-2:])
    if a.shape[0] == 4 + n_classes and a.shape[1] != 4 + n_classes:
        a = a.T
    xywh, scores = a[:, :4], a[:, 4:4 + n_classes]
    if xywh.max() > 2.0:
        xywh = xywh / float(input_size)
    best = scores.argmax(1)
    p = scores[np.arange(len(best)), best]
    boxes = [Box(float(cx - w / 2), float(cy - h / 2), float(w), float(h), code=int(k) + 1,
                 conf=float(s), score=float(s), origin="ai")
             for (cx, cy, w, h), k, s in zip(xywh, best, p) if s >= conf]
    return nms(boxes, .45)


class TFLiteDetector:
    def __init__(self, path: str):
        try:
            from tflite_runtime.interpreter import Interpreter  # type: ignore
        except ImportError:
            from tensorflow.lite import Interpreter  # type: ignore
        self.it = Interpreter(model_path=path, num_threads=2)
        self.it.allocate_tensors()
        self.inp = self.it.get_input_details()[0]
        self.out = self.it.get_output_details()[0]
        self.size = int(self.inp["shape"][1])

    def detect(self, img: Image.Image) -> list[Box]:
        arr = np.asarray(img.resize((self.size, self.size), Image.BILINEAR), np.float32) / 255.0
        self.it.set_tensor(self.inp["index"], arr[None].astype(self.inp["dtype"]))
        self.it.invoke()
        return decode_yolo(self.it.get_tensor(self.out["index"]), input_size=self.size)


# ------------------------------------------------------------------- la IA
class UprightAI:
    K = 5
    TAU = .03

    def __init__(self, db, model_dir: str | None = None):
        self.db = db
        self.ext = CropExtractor()
        self._cache: dict = {}
        self.detector = None
        for d in [model_dir] if model_dir else _model_dirs():
            path = os.path.join(d, MODEL_FILE) if d else ""
            if path and os.path.exists(path):
                try:
                    self.detector = TFLiteDetector(path)
                except Exception as exc:  # noqa: BLE001 (sin runtime: se sigue sin modelo)
                    print("detector de verticales no disponible:", exc)
                break

    # ------------------------------------------------------------ memoria
    def _refs(self, mode: str | None):
        key = mode or "*"
        if key not in self._cache:
            rows = self.db.list_upright_refs(self.ext.name, mode)
            X = (np.stack([np.frombuffer(r["embedding"], np.float32) for r in rows])
                 if rows else np.zeros((0, self.ext.dim), np.float32))
            self._cache[key] = (X, np.array([r["code"] for r in rows], np.int32),
                                [(r["w"], r["h"]) for r in rows])
        return self._cache[key]

    def invalidate(self):
        self._cache.clear()

    def learned(self, mode: str) -> int:
        _X, y, _s = self._refs(mode)
        return int((y > 0).sum())

    # ----------------------------------------------------------- sugerir
    def suggest(self, path: str, mode: str, week_number: int | None = None) -> Detection:
        img = load_rgb(path, 640)
        det = Detection()
        if self.detector is not None:
            det.boxes, det.method = self.detector.detect(img), "modelo"
        elif mode == "board":
            det.boxes, det.method = segment_board(img), "segmentación"
        else:
            n = self.learned(mode)
            if n < MIN_POS:
                det.method = "ninguno"
                det.message = (f"La IA aún está aprendiendo este tipo de foto ({n} de {MIN_POS} "
                               "verticales marcados): marque usted cada vertical y acepte.")
                return det
            det.boxes, det.method = self._sliding(img, mode), "aprendida"
        for b in det.boxes:
            if b.code is None or det.method != "modelo":
                b.code, b.conf = self.classify(crop(img, b), mode, week_number)
        if not det.message:
            det.message = (f"{len(det.boxes)} verticales sugeridos · revise y corrija"
                           if det.boxes else "No se encontraron verticales: márquelos usted.")
        return det

    def _sliding(self, img: Image.Image, mode: str) -> list[Box]:
        X, y, sizes = self._refs(mode)
        pos, neg = X[y > 0], X[y == 0]
        wh = np.array([s for s, c in zip(sizes, y) if c > 0 and s[0]], np.float32)
        bw, bh = (np.median(wh, 0) if len(wh) else DEFAULT_BOX[mode])
        small = img.copy()
        small.thumbnail((420, 420), Image.BILINEAR)
        cands = []
        for k in (.85, 1.15):
            w, h = min(.9, bw * k), min(.9, bh * k)
            sx, sy = max(w * .45, .02), max(h * .45, .02)
            for yy in np.arange(0, 1 - h + 1e-6, sy):
                for xx in np.arange(0, 1 - w + 1e-6, sx):
                    cands.append(Box(float(xx), float(yy), float(w), float(h)))
        if not cands:
            return []
        E = np.stack([self.ext.extract(crop(small, b, 0)) for b in cands])
        sp = np.sort(E @ pos.T, axis=1)[:, -3:].mean(1)
        sn = np.sort(E @ neg.T, axis=1)[:, -3:].mean(1) if len(neg) else np.zeros(len(E))
        score = sp - sn
        for b, s, p in zip(cands, score, sp):
            b.score = float(s)
            b.conf = float(p)
        thr = max(.015, float(np.percentile(score, 85)) * .5)
        return nms([b for b in cands if b.score > thr], .25)

    def classify(self, img: Image.Image, mode: str, week_number: int | None = None):
        """Estado del vertical recortado: k-NN con los marcados + priors de color/calendario."""
        ids = np.array(sorted(ph.STAGE_POS), dtype=np.int64)
        codes = np.array([ph.bbch_value(c) for c in ids], dtype=np.float64)
        logp = np.zeros(len(ids))
        X, y, _s = self._refs(mode)
        if (y > 0).sum() < 3:
            X, y, _s = self._refs(None)
        mask = y > 0
        if mask.sum() >= 3:
            q = self.ext.extract(img)
            sims = X[mask] @ q
            labels = y[mask]
            idx = np.argsort(-sims)[:self.K]
            w = np.exp((sims[idx] - sims[idx].max()) / self.TAU)
            p = np.full(len(ids), 1e-3)
            for i, wi in zip(idx, w):
                p += wi * np.exp(-0.5 * ((codes - ph.bbch_value(int(labels[i]))) / 2.5) ** 2)
            logp += 1.2 * np.log(p / p.sum())
        prof = foreground_profile(img) if mode == "board" else color_profile(img)
        pc, _info = PhenologyClassifier._color(codes, prof)
        logp += (.4 if mode == "board" else .6) * np.log(pc)
        if week_number:
            pt, _ti = PhenologyClassifier._temporal(codes, week_number, None)
            logp += .5 * np.log(pt)
        p = np.exp(logp - logp.max())
        p /= p.sum()
        k = int(np.argmax(p))
        return int(ids[k]), float(p[k])

    # ----------------------------------------------------------- aprender
    def learn(self, path: str, mode: str, marks: list[dict], negatives: int = 2,
              seed: int = 0) -> int:
        """Guarda los verticales marcados (con su estado) y trozos de fondo de la foto."""
        self.db.forget_upright_refs(path)
        if not marks:
            return 0
        img = load_rgb(path, 640)
        n = 0
        boxes = [Box(m["x"], m["y"], m["w"], m["h"], code=int(m["code"])) for m in marks]
        for b in boxes:
            e = self.ext.extract(crop(img, b, 0))
            self.db.add_upright_ref(mode, b.code, self.ext.name, e.tobytes(), b.w, b.h, path)
            n += 1
        rnd = random.Random(seed)
        bw = float(np.median([b.w for b in boxes]))
        bh = float(np.median([b.h for b in boxes]))
        want, tries = negatives * len(boxes), 0
        small = img.copy()
        small.thumbnail((420, 420), Image.BILINEAR)
        while want > 0 and tries < want * 30:
            tries += 1
            c = Box(rnd.uniform(0, max(1e-3, 1 - bw)), rnd.uniform(0, max(1e-3, 1 - bh)), bw, bh)
            if any(iou(c, b) > .05 or _center_inside(c, b) or _center_inside(b, c) for b in boxes):
                continue
            e = self.ext.extract(crop(small, c, 0))
            self.db.add_upright_ref(mode, 0, self.ext.name, e.tobytes(), bw, bh, path)
            want -= 1
        self.invalidate()
        return n


def _model_dirs() -> list[str]:
    from platform_utils import data_subdir, resource_path
    return [data_subdir("models"), resource_path("assets", "models")]


# ------------------------------------------------------------ exportación
def export_yolo(dbs, dest_zip: str) -> dict:
    """Set de entrenamiento en formato YOLO (imágenes + etiquetas, clases E1…E11) con todas
    las fotos de conteo aceptadas. dbs: una base o varias (ensayos y predios)."""
    if not isinstance(dbs, (list, tuple)):
        dbs = [dbs]
    n_img = n_box = 0
    per_mode = {m: 0 for m in MODES}
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for db in dbs:
            for cp in db.marked_count_photos():
                if not os.path.exists(cp["path"]):
                    continue
                split = "val" if (n_img % 5 == 4) else "train"
                stem = f"{db.code or 'X'}_{cp['id']:05d}_{cp['mode']}"
                img = load_rgb(cp["path"], 1280)
                buf = f"images/{split}/{stem}.jpg"
                tmp = dest_zip + ".tmp.jpg"
                img.save(tmp, "JPEG", quality=90)
                zf.write(tmp, buf)
                os.remove(tmp)
                lines = [f"{m['code'] - 1} {m['x'] + m['w'] / 2:.5f} {m['y'] + m['h'] / 2:.5f} "
                         f"{m['w']:.5f} {m['h']:.5f}" for m in cp["marks"]]
                zf.writestr(f"labels/{split}/{stem}.txt", "\n".join(lines) + "\n")
                n_img += 1
                n_box += len(lines)
                per_mode[cp["mode"]] += 1
        names = [f"E{c} {ph.STAGE_NAMES[c]}" for c in sorted(ph.STAGE_NAMES)]
        zf.writestr("data.yaml", "path: .\ntrain: images/train\nval: images/val\n"
                                 f"nc: {len(names)}\nnames: {json.dumps(names, ensure_ascii=False)}\n")
        zf.writestr("LEEME.txt", "Set de verticales de FenoCran (formato YOLO).\n"
                                 "Entrenar con: python tools/train_upright_detector.py este.zip\n"
                                 "y copiar verticales.tflite a la carpeta «models» de la app.\n")
    return {"images": n_img, "boxes": n_box, "modes": per_mode}
