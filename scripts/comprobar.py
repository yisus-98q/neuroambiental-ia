"""Verificación completa: pruebas del backend (pytest), tipos y compilación del frontend.

Uso (desde la carpeta del proyecto):  python scripts\\comprobar.py
(Es un script de Python y no un .bat porque el antivirus de este equipo eliminaba
los .bat que lanzaban las pruebas.)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(title: str, cmd: list[str], cwd: Path, env: dict | None = None) -> bool:
    print(f"=== {title} ===", flush=True)
    return subprocess.run(cmd, cwd=cwd, env=env).returncode == 0


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "backend" / ".deps"), str(ROOT / "backend")])
    env["PYTHONUTF8"] = "1"
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        print("[ERROR] No se encontró npm en el PATH.")
        return 1
    ok = run("Pruebas del backend (pytest)", [sys.executable, "-m", "pytest"], ROOT, env)
    ok = ok and run("Frontend: tipos y compilación", [npm, "run", "build"], ROOT / "frontend")
    print("\nTODAS LAS VERIFICACIONES PASARON." if ok else "\n[ERROR] Alguna verificación falló.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
