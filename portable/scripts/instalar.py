"""INSTALAR_DEPENDENCIAS: crea un entorno LOCAL en esta computadora e instala versiones fijadas.

- Primero intenta un entorno virtual en codigo/.venv (lo normal).
- Si un antivirus borra el python.exe del entorno (ocurre con Avast), instala en codigo/backend/.deps.
- Si existe dependencias/wheelhouse/, instala SIN internet desde ahí (--no-index).
"""
from __future__ import annotations

import os
import subprocess
import sys

from comun import BACKEND, CODIGO, RAIZ, log_path, titulo

LOCK = RAIZ / "dependencias" / "requirements-lock.txt"
WHEELS = RAIZ / "dependencias" / "wheelhouse"


def run(cmd: list[str], log) -> int:
    print("> " + " ".join(cmd))
    log.write("> " + " ".join(cmd) + "\n")
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log.write(p.stdout)
    print(p.stdout[-3000:])
    return p.returncode


def main() -> int:
    titulo("NEUROAMBIENTAL IA · instalación de dependencias")
    if not LOCK.is_file():
        print(f"No se encuentra {LOCK}.")
        return 1
    extra = ["--no-index", "--find-links", str(WHEELS)] if WHEELS.is_dir() and any(WHEELS.iterdir()) else []
    print("Origen de paquetes:", "wheelhouse local (sin internet)" if extra else "PyPI (requiere internet)")
    lp = log_path("instalar")
    with lp.open("w", encoding="utf-8") as log:
        venv = CODIGO / ".venv"
        py_venv = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        rc = run([sys.executable, "-m", "venv", str(venv)], log) if not py_venv.is_file() else 0
        if rc == 0 and py_venv.is_file():
            rc = run([str(py_venv), "-m", "pip", "install", "--disable-pip-version-check", *extra, "-r", str(LOCK)], log)
            if rc == 0:
                print(f"\nListo: entorno local en {venv}. Registro: {lp}")
                return 0
            print("\nFalló la instalación en el entorno virtual; se intenta la alternativa .deps.")
        else:
            print("\nNo se pudo crear el entorno virtual (¿un antivirus borró python.exe?); se usa la alternativa .deps.")
        rc = run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *extra, "--target",
                  str(BACKEND / ".deps"), "-r", str(LOCK)], log)
    print(f"\n{'Listo (alternativa .deps)' if rc == 0 else 'ERROR en la instalación'}. Registro: {lp}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
