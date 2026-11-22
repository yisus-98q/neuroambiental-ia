@echo off
rem Ejecuta todas las verificaciones: pruebas del backend, tipos y compilacion del frontend.
call "%~dp0_entorno.bat" || exit /b 1
pushd "%RAIZ%"
echo === Pruebas del backend (pytest) ===
%PY% -m pytest || goto :error
popd
pushd "%FRONTEND%"
echo === Frontend: verificacion de tipos y compilacion ===
call npm run build || goto :error
popd
echo.
echo TODAS LAS VERIFICACIONES PASARON.
exit /b 0
:error
popd
echo [ERROR] Alguna verificacion fallo.
exit /b 1
