@echo off
rem Modo desarrollo: backend (8000) y Vite con recarga en caliente (5173), en dos ventanas.
rem Consume mas memoria que scripts\iniciar.bat. Detener: scripts\detener.bat
call "%~dp0_entorno.bat" || exit /b 1
pushd "%BACKEND%"
%PY% -m app.cli migrate || (popd & exit /b 1)
start "NEURO backend" cmd /k "%PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
popd
start "NEURO frontend" cmd /k "cd /d %FRONTEND% && npm run dev"
echo Backend: http://127.0.0.1:8000/docs   Interfaz: http://localhost:5173
