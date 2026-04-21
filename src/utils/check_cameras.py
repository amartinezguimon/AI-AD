import cv2

print("Buscando cámaras conectadas a tu PC...")

for index in range(5):
    print(f"\nProbando el CAMERA_INDEX = {index} ...")
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"❌ Índice {index}: No hay ninguna cámara aquí.")
        continue
    
    success, frame = cap.read()
    if success:
        print(f"✅ Índice {index}: ¡Cámara encontrada! Resolución: {frame.shape[1]}x{frame.shape[0]}")
        cv2.imshow(f"Cámara {index}", frame)
        cv2.waitKey(2000)  # Muestra la cámara durante 2 segundos
        cv2.destroyAllWindows()
    else:
        print(f"⚠️ Índice {index}: La cámara existe pero la imagen está vacía o bloqueada.")
        
    cap.release()

print("\nBúsqueda completada. Revisa los resultados arriba para saber qué número de índice es tu iPhone.")
