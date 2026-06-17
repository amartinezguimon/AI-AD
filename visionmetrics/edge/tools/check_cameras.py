"""Find which camera number to use (incl. Camo Studio / OBS), and whether it has
a REAL image or just black.

Tries each index 0-5 (DirectShow on Windows, where virtual cams live), warms the
camera up for ~2s and measures brightness, so a device that opens but stays black
(e.g. Camo when it isn't streaming the phone) is flagged. Use the number it marks
'IMAGEN OK' in the demo.
"""

import sys
import time

import cv2

print("Buscando cámaras (incluida Camo Studio). Abre Camo y conecta el móvil ANTES.\n")

api = cv2.CAP_DSHOW if sys.platform.startswith("win") else 0
best_ok = None
for index in range(6):
    cap = cv2.VideoCapture(index, api) if api else cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        continue

    brightest, res, t0 = -1.0, None, time.time()
    while time.time() - t0 < 2.0:
        ok, frame = cap.read()
        if ok and frame is not None:
            res = (frame.shape[1], frame.shape[0])
            brightest = max(brightest, float(frame.mean()))
            if brightest >= 8:
                break
        time.sleep(0.03)
    cap.release()

    if res is None:
        continue
    if brightest < 8:
        print(f"  cam {index}: {res[0]}x{res[1]}  -> NEGRA (abre pero sin imagen: "
              f"Camo apagado / movil sin conectar)")
    else:
        estado = "IMAGEN OK" if brightest >= 30 else "imagen (algo oscura)"
        print(f"  cam {index}: {res[0]}x{res[1]}  -> {estado}")
        if best_ok is None:
            best_ok = index

print()
if best_ok is not None:
    print(f">> Usa el numero {best_ok} en la demo (es el primero con imagen real).")
    print("   Si tu Camo no aparece con IMAGEN OK, es que no esta emitiendo:")
    print("   abrelo, conecta el movil y comprueba que VES el video en la app.")
else:
    print("X  Ninguna camara dio imagen. Abre Camo Studio + conecta el movil, o revisa "
          "los permisos de camara de Windows, y reintenta.")
