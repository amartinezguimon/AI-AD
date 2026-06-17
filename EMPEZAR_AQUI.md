# EMPEZAR AQUÍ 👋 (para Hector / cualquier compañero)

Todo desde **un solo sitio**, paso a paso. Sin abrir 500 pestañas.

## 1) Una sola vez — instalar
Necesitas **Python 3.10+** y **Git** instalados. Luego, en PowerShell, dentro de la carpeta del proyecto:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> Si lo bajas de cero: `git clone https://github.com/amartinezguimon/AI-AD.git` → `cd AI-AD` → y luego lo de arriba. (Ya está todo en `main`, no hay que cambiar de rama.)

## 2) Cada vez que quieras usarlo
**Doble clic en `DEMO.bat`** (o en PowerShell: `python run.py`).

Sale un menú. Escribe el número y Enter:

| Opción | Qué hace | Qué me envías |
|---|---|---|
| **1) Probar en vivo** | Abre la cámara con los datos en directo. Pulsa **Q** para terminar. | El archivo `results\demo_….json` que te indica al final |
| **2) Grabar datos** | Te pide tu nombre y graba ejemplos (**L**=mira, **A**=no, **T**=grabar seguido, **G**=gafas, **H**=gorra, **Q**=guardar). | El archivo `data\raw_sessions\….csv` que te indica al final |
| **3) Dibujar la zona** | Marcas con clics la acera que cuenta (**S**=guardar). | (nada; queda guardado para las pruebas) |
| **4) Ver cámaras** | Si la cámara no abre, te dice los números disponibles. | — |
| **0) Salir** | | |

## 3) Enviarme los archivos
Cuando una opción termina, te escribe en pantalla **la ruta exacta** del archivo.
Mándamelo por **WhatsApp o email**. **No hace falta tocar GitHub.**

## Notas
- Al **grabar** (opción 2): recuerda que **“mirar” = mirar a la cámara** (la cámara hace de escaparate). Graba variedad: con/sin gafas y gorra, de cerca y de lejos.
- Al **probar en vivo** (opción 1): si cuenta de más por gente lejana o de la otra calle, usa la opción **3** para dibujar la zona sobre la acera de delante y vuelve a probar.
- Si algo falla, hazme una **captura de la pantalla** con el error y me la mandas.
