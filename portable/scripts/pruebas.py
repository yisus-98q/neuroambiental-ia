"""EJECUTAR_PRUEBAS: pruebas del backend (pytest) con el resultado guardado en logs/."""
from __future__ import annotations

import subprocess

from comun import CODIGO, entorno_backend, log_path, python_backend, titulo


def main() -> int:
    titulo("NEUROAMBIENTAL IA · pruebas")
    env = entorno_backend()
    env["PYTHONPATH"] = str(CODIGO / "backend") + ";" + env.get("PYTHONPATH", "")
    p = subprocess.run([python_backend(), "-m", "pytest", "tests/backend", "-q", "-p", "no:cacheprovider"],
                       cwd=CODIGO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lp = log_path("pruebas")
    lp.write_text(p.stdout, encoding="utf-8")
    print(p.stdout[-4000:])
    print(f"\n{'TODAS LAS PRUEBAS PASARON' if p.returncode == 0 else 'HAY PRUEBAS QUE FALLARON'}. Registro: {lp}")
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
