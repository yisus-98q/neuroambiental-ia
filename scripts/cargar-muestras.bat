@echo off
rem Carga data\samples\ como datos SIMULADOS (quedan marcados como tales).
call "%~dp0_entorno.bat" || exit /b 1
pushd "%BACKEND%"
set "USUARIO=%~1"
if "%USUARIO%"=="" set "USUARIO=admin"
%PY% -m app.cli load-samples --username %USUARIO%
popd
