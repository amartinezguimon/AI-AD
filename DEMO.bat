@echo off
REM Doble clic para abrir el menu de VisionMetrics (probar / grabar / zona).
chcp 65001 >nul
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" run.py
) else (
    python run.py
)
echo.
pause
