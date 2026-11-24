"""Verifica los SHA-256 de todos los archivos del paquete portátil contra checksums/SHA256SUMS.txt."""
from __future__ import annotations

import hashlib
import sys

from comun import RAIZ, titulo


def sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    titulo("NEUROAMBIENTAL IA · verificación de integridad")
    sums = RAIZ / "checksums" / "SHA256SUMS.txt"
    if not sums.is_file():
        print("No existe checksums/SHA256SUMS.txt.")
        return 1
    bad, missing, n = [], [], 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        p = RAIZ / rel
        n += 1
        if not p.is_file():
            missing.append(rel)
        elif sha(p) != digest:
            bad.append(rel)
    print(f"{n} archivos comprobados · {len(bad)} alterados · {len(missing)} ausentes")
    for r in bad[:20]:
        print("  ALTERADO:", r)
    for r in missing[:20]:
        print("  AUSENTE:", r)
    ok = not bad and not missing
    print("INTEGRIDAD CORRECTA" if ok else "INTEGRIDAD CON PROBLEMAS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
