@echo off
rem Instala dependencias, compila el frontend y crea/actualiza la base de datos.
call "%~dp0_entorno.bat" || exit /b 1
pushd "%BACKEND%"
echo === Backend: dependencias en backend\.deps ===
where uv >nul 2>nul
if %errorlevel%==0 (
  uv pip install --system-certs --python %PY% --target .deps -r requirements-dev.txt || goto :error
) else (
  %PY% -m pip install --target .deps -r requirements-dev.txt || goto :error
)
echo === Base de datos: migraciones ===
%PY% -m app.cli migrate || goto :error
popd
pushd "%FRONTEND%"
echo === Frontend: dependencias y compilacion ===
call npm install --no-fund --no-audit || goto :error
call npm run build || goto :error
popd
echo.
echo Instalacion completa. Siguiente paso: scripts\crear-admin.bat y luego scripts\iniciar.bat
exit /b 0
:error
echo [ERROR] La instalacion fallo. Revise el mensaje anterior.
popd
exit /b 1
