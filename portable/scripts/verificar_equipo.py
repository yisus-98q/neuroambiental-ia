"""VERIFICAR_EQUIPO: hardware, almacenamiento, Python, dependencias y perfil recomendado."""
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import socket
import subprocess
import sys

from comun import BACKEND, CODIGO, RAIZ, entorno_backend, log_path, python_backend, titulo

GB = 1024 ** 3


def ram() -> tuple[float, float]:
    if os.name == "nt":
        class M(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("u", ctypes.c_ulong), ("t", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong),
                        ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong),
                        ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
        m = M()
        m.l = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.t / GB, m.a / GB
    return 0.0, 0.0


def main() -> int:
    out = []
    p = lambda s="": (print(s), out.append(s))  # noqa: E731
    titulo("NEUROAMBIENTAL IA · verificación del equipo")
    total, libre = ram()
    p(f"Sistema: {platform.platform()} · CPU: {platform.processor() or 'desconocida'} · hilos: {os.cpu_count()}")
    p(f"RAM: {total:.1f} GB en total, {libre:.1f} GB libres")
    perfil = "potente" if total >= 24 else "estandar" if total >= 8 else "ligero"
    p(f"Perfil recomendado: {perfil}  (config/perfil_{perfil}.env)")
    du = shutil.disk_usage(RAIZ)
    p(f"Disco de la carpeta portátil: {du.free / GB:.1f} GB libres de {du.total / GB:.1f} GB")
    p(f"Python: {sys.version.split()[0]} en {sys.executable}")
    problemas = []
    if sys.version_info < (3, 12):
        problemas.append("Se requiere Python 3.12 o superior (recomendado 3.14, el usado al desarrollar).")
    if du.free < 2 * GB:
        problemas.append("Menos de 2 GB libres: la instalación de dependencias puede fallar.")
    if total and total < 3.5:
        problemas.append("Menos de 4 GB de RAM: use el perfil «ligero» y cierre otros programas.")
    py = python_backend()
    r = subprocess.run([py, "-c", "import fastapi, sqlalchemy, numpy, sklearn, rasterio; print('ok')"],
                       capture_output=True, text=True, env=entorno_backend(), cwd=BACKEND)
    deps_ok = r.returncode == 0 and "ok" in r.stdout
    p(f"Dependencias del backend: {'instaladas' if deps_ok else 'NO instaladas (ejecute INSTALAR_DEPENDENCIAS.bat)'}")
    p(f"Frontend compilado: {'sí' if (CODIGO / 'frontend' / 'dist' / 'index.html').is_file() else 'NO'}")
    s = socket.socket()
    libre_8000 = s.connect_ex(("127.0.0.1", 8000)) != 0
    s.close()
    p(f"Puerto 8000: {'libre' if libre_8000 else 'ocupado (¿NEUROAMBIENTAL ya está en marcha?)'}")
    p(f"GPU: no se usa; el entrenamiento es por CPU (scikit-learn).")
    if problemas:
        p("\nPROBLEMAS:")
        for x in problemas:
            p(f"  - {x}")
    else:
        p("\nEl equipo cumple los requisitos mínimos.")
    lp = log_path("verificar_equipo")
    lp.write_text("\n".join(out), encoding="utf-8")
    print(f"\nRegistro guardado en {lp}")
    return 1 if problemas and sys.version_info < (3, 12) else 0


if __name__ == "__main__":
    raise SystemExit(main())
