"""INICIAR / DETENER el servidor de forma controlada.

- iniciar: aplica migraciones, arranca uvicorn (un solo worker) en segundo plano, guarda su PID y abre el navegador.
- detener: termina SOLO el proceso cuyo PID guardó este script y cuya línea de comandos es la de NEUROAMBIENTAL
  (no cierra otros procesos de Python ni ajenos).
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser

from comun import BACKEND, RUN, entorno_backend, log_path, python_backend, titulo

PID = RUN / "servidor.pid"
URL = "http://127.0.0.1:8000"
FIRMA = "uvicorn app.main:app"


def puerto_ocupado() -> bool:
    s = socket.socket()
    try:
        return s.connect_ex(("127.0.0.1", 8000)) == 0
    finally:
        s.close()


def linea_de_comandos(pid: int) -> str:
    if os.name != "nt":
        try:
            return open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode()
        except OSError:
            return ""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
                       capture_output=True, text=True)
    return r.stdout.strip()


def iniciar() -> int:
    titulo("NEUROAMBIENTAL IA · inicio")
    if puerto_ocupado():
        print(f"El puerto 8000 ya está en uso. Si es NEUROAMBIENTAL, ábralo en {URL}; si no, ciérrelo primero.")
        return 1
    py, env = python_backend(), entorno_backend()
    r = subprocess.run([py, "-m", "app.cli", "migrate"], cwd=BACKEND, env=env, capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    if r.returncode != 0:
        print("ERROR al preparar la base de datos. ¿Ejecutó INSTALAR_DEPENDENCIAS.bat?")
        return 1
    RUN.mkdir(exist_ok=True)
    lp = log_path("servidor")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000 if os.name == "nt" else 0   # sin ventana extra
    with lp.open("w", encoding="utf-8") as log:
        p = subprocess.Popen([py, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000",
                              "--workers", "1"], cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=flags)
    PID.write_text(str(p.pid), encoding="ascii")
    for _ in range(60):
        if puerto_ocupado():
            print(f"Servidor en marcha (PID {p.pid}). Registro: {lp}")
            webbrowser.open(URL)
            print(f"Abra {URL}. Para detenerlo use DETENER_SISTEMA.bat.")
            return 0
        if p.poll() is not None:
            break
        time.sleep(1)
    print(f"ERROR: el servidor no arrancó. Revise el registro: {lp}")
    return 1


def detener() -> int:
    titulo("NEUROAMBIENTAL IA · detener")
    if not PID.is_file():
        print("No hay un servidor iniciado por estos scripts (no existe run/servidor.pid).")
        return 0
    pid = int(PID.read_text(encoding="ascii").strip() or 0)
    cmd = linea_de_comandos(pid)
    if FIRMA not in cmd:
        print(f"El PID {pid} ya no corresponde a NEUROAMBIENTAL (no se cierra nada ajeno).")
        PID.unlink(missing_ok=True)
        return 0
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        os.kill(pid, 15)
    PID.unlink(missing_ok=True)
    print(f"Servidor detenido (PID {pid}).")
    return 0


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "iniciar"
    raise SystemExit(iniciar() if accion == "iniciar" else detener())
