@echo off
rem Detiene los procesos que escuchan en los puertos 8000 (backend) y 5173 (Vite).
for %%P in (8000 5173) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /r /c:"127.0.0.1:%%P .*LISTENING" /c:"0.0.0.0:%%P .*LISTENING" /c:"\[::1\]:%%P .*LISTENING"') do (
    echo Deteniendo proceso %%I en el puerto %%P
    taskkill /PID %%I /T /F >nul 2>nul
  )
)
echo Listo.
