@echo off
rem Variables comunes. Las dependencias de Python viven en backend\.deps
rem (no se usa un .venv porque algunos antivirus bloquean la copia de python.exe).
set "RAIZ=%~dp0.."
set "BACKEND=%RAIZ%\backend"
set "FRONTEND=%RAIZ%\frontend"
set "PYTHONPATH=%BACKEND%\.deps;%BACKEND%"
set "PYTHONUTF8=1"
set "PY=python"
where %PY% >nul 2>nul || (echo [ERROR] No se encontro Python en el PATH. Instale Python 3.12+ desde python.org & exit /b 1)
