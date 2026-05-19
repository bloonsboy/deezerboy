@echo off
REM Lancer l'export CSV rapidement
echo.
echo 🎵 DeezerBoy - Export CSV
echo ========================
echo.

REM Activer l'environnement
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo ⚠️  Environment non trouvé. Lancez 'uv sync' d'abord
    pause
    exit /b 1
)

REM Lancer l'export
python export_quick.py

pause
