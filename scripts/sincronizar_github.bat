@echo off
setlocal
chcp 65001 >/dev/null
title NEUROAMBIENTAL IA - sincronizar con GitHub
cd /d "%~dp0.."
set "PY="
where py >/dev/null 2>/dev/null && set "PY=py -3"
if not defined PY where python >/dev/null 2>/dev/null && set "PY=python"
if not defined PY (
  echo [ERROR] No se encontro Python.
  pause
  exit /b 1
)
%PY% scripts\sincronizar_github.py
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (echo [ERROR] Codigo %RC%: revise los mensajes anteriores.) else (echo [OK] Terminado.)
pause
exit /b %RC%
