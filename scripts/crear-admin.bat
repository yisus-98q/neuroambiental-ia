@echo off
rem Crea el usuario administrador (pide la contrasena sin mostrarla).
call "%~dp0_entorno.bat" || exit /b 1
pushd "%BACKEND%"
%PY% -m app.cli migrate
set "USUARIO=%~1"
if "%USUARIO%"=="" set "USUARIO=admin"
%PY% -m app.cli create-admin --username %USUARIO%
popd
