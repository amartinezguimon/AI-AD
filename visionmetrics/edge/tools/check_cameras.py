"""Find the camera index to use (incl. virtual cams like Camo Studio / OBS).

Tries each index 0-5 with BOTH the default backend and DirectShow (DSHOW) — on
Windows, phone-as-webcam apps usually only open under DSHOW. Tell the demo the
index it reports for your camera.
"""

import sys

import cv2

print("Buscando cámaras (incluida Camo Studio)... abre Camo y conecta el móvil ANTES.\n")

backends = [("por defecto", 0)]
if sys.platform.startswith("win"):
    backends.append(("DirectShow", cv2.CAP_DSHOW))

found = []
for index in range(6):
    for name, api in backends:
        cap = cv2.VideoCapture(index, api) if api else cv2.VideoCapture(index)
        if not cap.isOpened():
            cap.release()
            continue
        ok, frame = cap.read()
        if ok and frame is not None:
            print(f"✅ Cámara en el número {index}  (backend: {name})  "
                  f"resolución {frame.shape[1]}x{frame.shape[0]}")
            cv2.imshow(f"Camara {index} ({name}) - se cierra en 2s", frame)
            cv2.waitKey(2000)
            cv2.destroyAllWindows()
            found.append(index)
            cap.release()
            break  # this index works; don't double-report it
        cap.release()

print()
if found:
    uniq = sorted(set(found))
    print(f"👉 Usa el número {uniq[0]}" + (f" (o prueba {uniq}) " if len(uniq) > 1 else "") +
          " en la demo cuando te pregunte '¿Número de cámara?'.")
else:
    print("❌ No se encontró ninguna cámara. Comprueba: ¿está Camo Studio abierto y el "
          "móvil conectado/streaming? ¿le diste permiso de cámara a Python/Windows?")
