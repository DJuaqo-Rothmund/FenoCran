"""
tools/train_upright_detector.py
===============================
Entrena el detector de verticales (YOLOv8n: dónde está cada vertical y su estado E1-E11)
con el set exportado desde la app (IA › Modelo › «Exportar fotos marcadas (set YOLO)») y
lo exporta a TFLite para usarlo en el teléfono sin conexión.

En un PC con GPU o en Google Colab:

    pip install ultralytics
    python tools/train_upright_detector.py verticales_yolo_20261019.zip [--epochs 120]

Resultado: ``verticales.tflite``. Cópielo en la carpeta «models» de los datos de la app
(Android: Android/data/org.cran.fenocran/files/models/) o en assets/models/ antes de
compilar. Desde ahí la app usa el modelo para sugerir los recuadros y estados en los tres
tipos de foto; las correcciones del evaluador siguen sumándose al set para re-entrenar.
"""
import argparse
import os
import shutil
import tempfile
import zipfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="ZIP exportado por la app (formato YOLO)")
    ap.add_argument("--epochs", type=int, default=120)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--out", default="verticales.tflite")
    args = ap.parse_args()

    from ultralytics import YOLO  # pip install ultralytics

    work = tempfile.mkdtemp(prefix="verticales_")
    with zipfile.ZipFile(args.dataset) as zf:
        zf.extractall(work)
    yaml = os.path.join(work, "data.yaml")
    text = open(yaml, encoding="utf-8").read().replace("path: .", f"path: {work}")
    open(yaml, "w", encoding="utf-8").write(text)

    model = YOLO("yolov8n.pt")
    model.train(data=yaml, epochs=args.epochs, imgsz=args.imgsz, batch=16, patience=30,
                fliplr=.5, degrees=10, hsv_h=.01, project=work, name="run")
    best = os.path.join(work, "run", "weights", "best.pt")
    exported = YOLO(best).export(format="tflite", imgsz=args.imgsz)
    path = exported if str(exported).endswith(".tflite") else next(
        os.path.join(r, f) for r, _d, fs in os.walk(os.path.dirname(best)) for f in fs
        if f.endswith("float32.tflite"))
    shutil.copy(path, args.out)
    print("Listo:", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
