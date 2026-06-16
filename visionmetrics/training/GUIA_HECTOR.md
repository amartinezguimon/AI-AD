# Guía rápida — grabar ejemplos para entrenar (Hector)

1. Abre PowerShell en la carpeta del proyecto y ejecuta:
   ```
   python -m visionmetrics.training.collect --collector hector
   ```
2. Se abre la cámara. Que la persona se ponga delante, **de cerca y de lejos** (camina hacia/desde la cámara).
   > Al grabar no hay escaparate: **la cámara hace de escaparate.** "Mirar" = mirar **a la cámara**.
   > (En cada tienda real ya se ajusta luego con la calibración.)
3. Marca con el teclado lo que pasa:
   - **L** = está **MIRANDO a la cámara** (= mirando el escaparate)
   - **A** = **NO** mira (mira a otro lado / solo pasa)
   - **T** = captura continua ON/OFF — la forma fácil: pose + T graba muchos solo (no hay que machacar L/A)
   - **M** = cambia la etiqueta de la captura continua (mira / no mira)
   - **G** = marca **GAFAS** (no → sí)   ·   **H** = marca **GORRA** (ninguna → gorra → …)
4. Graba **variedad**: varias personas, con y sin gafas/gorra, de cerca y de lejos. (Mira arriba a la izquierda: te dice gafas/gorra actuales y cuántos "mira/no mira" llevas.)
5. Pulsa **Q** para terminar. Te imprimirá la **ruta de un archivo `.csv`**.
   **Mándame ESE archivo por WhatsApp.** Ya está — yo me encargo del resto.

> No hace falta tocar GitHub ni nada. Un comando, grabas, me mandas el archivo.
