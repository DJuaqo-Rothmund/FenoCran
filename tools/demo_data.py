"""
Genera una base de datos de demostración con fotos sintéticas (para probar
la UI, la IA y los informes en PC sin salir a terreno).

Uso:
    FENOCRAN_DATA=/tmp/fenocran-demo python tools/demo_data.py [--weeks 14]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import phenology as ph  # noqa: E402
from ai_classifier import PhenologyClassifier  # noqa: E402
from database import Database, default_db_path  # noqa: E402
from platform_utils import data_subdir  # noqa: E402


def synthetic_photo(code: int, kind: str, path: str, seed: int) -> str:
    """Dibuja una escena esquemática coherente con el estado del cranberry (1-11)."""
    import math
    rnd = random.Random(seed)
    size = (800, 600)
    macro = ph.macro_of(code)
    sky = (205, 214, 190) if kind == "canopy" else (60, 80, 45)
    img = Image.new("RGB", size, sky)
    d = ImageDraw.Draw(img)
    if macro == 0:   # canopia rojiza en reposo
        d.rectangle((0, 0, *size), fill=(96, 52, 44))
    n_leaves = {0: 60, 3: 90}.get(macro, 120)
    for _ in range(n_leaves if kind == "canopy" else n_leaves // 2):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        r = rnd.randint(14, 34)
        g = (rnd.randint(50, 90), rnd.randint(100, 150), rnd.randint(40, 70))
        if macro == 0:
            g = (rnd.randint(110, 150), rnd.randint(40, 70), rnd.randint(45, 70))
        d.ellipse((x - r, y - r // 2, x + r, y + r // 2), fill=g)
    organs = 8 if kind == "canopy" else 22
    for _ in range(organs):
        x, y = rnd.randrange(60, size[0] - 60), rnd.randrange(60, size[1] - 60)
        r = rnd.randint(10, 22) if kind == "canopy" else rnd.randint(18, 40)
        if macro == 0:
            tip = (240, 236, 226) if code >= 2 else (140, 40, 50)
            d.ellipse((x - r // 2, y - r, x + r // 2, y + r), fill=(120, 36, 46))
            d.ellipse((x - r // 4, y - r, x + r // 4, y - r // 3), fill=tip)
        elif macro in (3, 5):
            d.rectangle((x - 3, y - r, x + 3, y + r), fill=(110, 150, 70))
            d.ellipse((x - r // 2, y - r, x + r // 2, y), fill=(150, 175, 90))
        elif macro == 6:
            for a in range(4):
                ang = (45 + a * 90) * math.pi / 180
                px, py = x + int(r * 0.7 * math.cos(ang)), y + int(r * 0.7 * math.sin(ang))
                d.ellipse((px - r // 2, py - r // 3, px + r // 2, py + r // 3), fill=(246, 232, 236))
            d.ellipse((x - r // 4, y - r // 4, x + r // 4, y + r // 4), fill=(215, 190, 90))
        elif macro == 7:
            d.ellipse((x - r, y - r, x + r, y + r), fill=(170, 200, 110))
        elif macro == 8:
            d.ellipse((x - r, y - r, x + r, y + r), fill=(150, 20, 40))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    img.save(path, "JPEG", quality=85)
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=14)
    ap.add_argument("--season", type=int, default=ph.season_of(_dt.date.today()))
    args = ap.parse_args()

    db = Database(default_db_path())
    clf = PhenologyClassifier(db)
    photo_dir = data_subdir("photos", "demo")
    varieties = db.list_varieties()
    db.ensure_weeks(args.season, args.weeks)
    for vi, v in enumerate(varieties):
        offset = (vi % 5) - 2  # precocidad relativa simulada
        db.save_metrics(v["id"], args.season, historical_yield=round(24 + vi * 1.5, 1),
                        projected_yield=round(26 + vi * 1.2, 1), basal_canes=480 + vi * 20,
                        laterals=3 + vi % 3)
        db.set_custom_field(v["id"], args.season, "TAcy", f"{32 + vi * 3:.0f}", "mg/100 g")
        for w in db.list_weeks(args.season):
            n = w["week_number"]
            code = ph.code_from_pos(ph.expected_bbch_for_week(n + offset * 0.6))
            obs = db.get_or_create_observation(v["id"], w["id"])
            for kind in ("canopy", "detail"):
                path = os.path.join(photo_dir, f"v{v['id']}_s{n:02d}_{kind}.jpg")
                synthetic_photo(code, kind, path, seed=vi * 1000 + n * 10 + (kind == "detail"))
                db.set_photo(obs["id"], kind, path, source="demo")
            db.update_observation(obs["id"], bbch_code=code, bbch_label=ph.bbch_label(code),
                                  notes=f"Registro de demostración. {ph.bbch_label(code)}.",
                                  observed_at=w["start_date"])
            if vi < 4:  # semillas para el k-NN
                ph_row = db.get_photos(obs["id"])["detail"]
                clf.add_reference(ph_row["path"], code, photo_id=ph_row["id"])
    print(f"Demo creada en {db.path}: {len(varieties)} variedades × {args.weeks} semanas")


if __name__ == "__main__":
    main()
