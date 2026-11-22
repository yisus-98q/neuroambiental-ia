@echo off
rem Inicia NEUROAMBIENTAL IA en un solo proceso (API + interfaz compilada).
rem Abrir: http://127.0.0.1:8000   Detener: Ctrl+C en esta ventana o scripts\detener.bat
call "%~dp0_entorno.bat" || exit /b 1
if not exist "%FRONTEND%\dist\index.html" (
  echo [AVISO] No existe frontend\dist. Ejecute primero scripts\instalar.bat
)
pushd "%BACKEND%"
%PY% -m app.cli migrate || (popd & exit /b 1)
echo.
echo NEUROAMBIENTAL IA en http://127.0.0.1:8000  (Ctrl+C para detener)
start "" http://127.0.0.1:8000
%PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
popd
