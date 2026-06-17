#!/usr/bin/env python3
"""VisionMetrics — lanzador único (menú) para probar y grabar SIN LIARSE.

    python run.py        (o, en Windows, doble clic en DEMO.bat)

Un solo sitio, paso a paso: probar el modelo en vivo, grabar datos para entrenar,
dibujar la zona de conteo. Cada opción te dice qué archivo enviar a Álvaro.
Pensado para una demo local (portátil + webcam); la versión por tienda vendrá luego.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable

# Show accents correctly even on a plain Windows console.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def _check_deps() -> bool:
    missing = []
    for mod in ("cv2", "ultralytics", "mediapipe", "torch", "yaml"):
        try:
            __import__(mod)
        except Exception:
            missing.append("opencv-python" if mod == "cv2" else
                           "pyyaml" if mod == "yaml" else mod)
    if missing:
        print("\n  Faltan dependencias:", ", ".join(missing))
        print("  Instálalas UNA vez (desde esta carpeta):\n")
        print("    python -m venv venv")
        print("    venv\\Scripts\\activate      (Windows)")
        print("    source venv/bin/activate    (Mac/Linux)")
        print("    pip install -r requirements.txt\n")
        return False
    return True


def _run(args: list[str]) -> None:
    print("\n  > " + " ".join([Path(PY).name, *args]) + "\n")
    subprocess.run([PY, *args], cwd=ROOT)


def demo_en_vivo() -> None:
    (ROOT / "results").mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = f"results/demo_{stamp}.json"
    print("\n  Se abrirá una ventana con la cámara y los datos en directo.")
    print("  Colócate / que pase gente delante. Pulsa Q en la ventana para terminar.")
    _run(["-m", "visionmetrics.edge.agent.service",
          "--config", "configs/demo.yaml", "--debug", "--report", report])
    print("\n  *** LISTO. Envíale a Álvaro este archivo (WhatsApp / email): ***")
    print(f"      {ROOT / report}")


def grabar_datos() -> None:
    nombre = input("\n  Tu nombre (p. ej. hector): ").strip() or "hector"
    print("\n  Se abrirá la cámara. MIRA A LA CÁMARA = 'mirando'.")
    print("  L=mira  A=no mira  T=grabar seguido  M=cambia  G=gafas  H=gorra  Q=guardar.")
    _run(["-m", "visionmetrics.training.collect", "--collector", nombre])
    print("\n  *** Al terminar te dijo la ruta de UN archivo .csv: envíaselo a Álvaro. ***")


def dibujar_zona() -> None:
    print("\n  Haz clic en las esquinas de la acera que SÍ cuenta (deja margen en los bordes).")
    print("  S=guardar   U=deshacer   C=limpiar   Q=salir.")
    _run(["-m", "visionmetrics.edge.tools.draw_zone",
          "--source", "0", "--config", "configs/demo_zone.json"])


def ver_camaras() -> None:
    _run(["src/utils/check_cameras.py"])


MENU = {
    "1": ("Probar el modelo EN VIVO (cámara) + guardar informe", demo_en_vivo),
    "2": ("Grabar datos para entrenar (y enviármelos)", grabar_datos),
    "3": ("Dibujar la zona de conteo (la acera)", dibujar_zona),
    "4": ("Ver qué cámaras hay (si la cámara no abre)", ver_camaras),
}


def main() -> int:
    print("\n=== VisionMetrics — demo ===")
    if not _check_deps():
        input("\n  (pulsa Enter para salir) ")
        return 1
    while True:
        print("\n----------------  MENÚ  ----------------")
        for key, (label, _) in MENU.items():
            print(f"  {key}) {label}")
        print("  0) Salir")
        choice = input("  Elige una opción: ").strip()
        if choice == "0":
            print("  ¡Hasta luego!")
            return 0
        item = MENU.get(choice)
        if not item:
            print("  Opción no válida.")
            continue
        try:
            item[1]()
        except KeyboardInterrupt:
            print("\n  (interrumpido)")
        except Exception as exc:  # noqa: BLE001 - keep the menu alive for a non-tech user
            print(f"  Error: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
