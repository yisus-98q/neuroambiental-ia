"""Sincroniza NEUROAMBIENTAL IA con GitHub de forma segura (lo llama scripts/sincronizar_github.bat).

1. Muestra los cambios.
2. Bloquea secretos y archivos grandes (> 50 MB; GitHub rechaza > 100 MB).
3. Ejecuta las pruebas y la compilación (scripts/comprobar.py).
4. Pide confirmación y un mensaje de commit.
5. Trae el remoto: si hay trabajo remoto nuevo, se DETIENE (nunca sobrescribe ni hace force push).
6. Publica y verifica que el remoto quedó igual al local.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAX_MB = 50
SECRET = re.compile(r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH|PRIVATE)"
                    r"|password\s*=\s*['\"][^'\"]{6,}['\"]|api[_-]?key\s*=\s*['\"][A-Za-z0-9]{12,})", re.I)
FORBIDDEN = re.compile(r"(^|/)(\.env|.*\.db|.*\.sqlite|.*\.joblib|.*\.tif|.*\.pem|.*\.key)$")


def git(*a: str, check: bool = True) -> str:
    r = subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise SystemExit(f"[ERROR] git {' '.join(a)}: {r.stderr.strip()}")
    return r.stdout.strip()


def main() -> int:
    print("== NEUROAMBIENTAL IA · sincronizar con GitHub ==")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    remote = git("remote", "get-url", "origin", check=False)
    if not remote:
        print("[ERROR] No hay remoto «origin». Vea docs/ESTRATEGIA_GITHUB_Y_VERSIONADO.md.")
        return 1
    status = git("status", "--porcelain")
    print(f"Rama: {branch} · remoto: {remote}")
    print(status or "(sin cambios locales)")
    files = [ln[3:].strip().strip('"') for ln in status.splitlines()]
    problems = []
    for f in files:
        p = REPO / f
        if FORBIDDEN.search(f.replace("\\", "/")):
            problems.append(f"Archivo que no debe subirse: {f}")
        if p.is_file() and p.stat().st_size > MAX_MB * 2**20:
            problems.append(f"Archivo grande ({p.stat().st_size / 2**20:.0f} MB): {f} — use scripts de descarga o Git LFS")
        if p.is_file() and p.stat().st_size < 5 * 2**20:
            try:
                if SECRET.search(p.read_text(encoding="utf-8", errors="ignore")):
                    problems.append(f"Posible secreto en: {f}")
            except OSError:
                pass
    if problems:
        print("\n[BLOQUEADO]\n  - " + "\n  - ".join(problems))
        return 1
    print("\nEjecutando pruebas y compilación…")
    if subprocess.run([sys.executable, str(REPO / "scripts" / "comprobar.py")], cwd=REPO).returncode != 0:
        print("[BLOQUEADO] Las pruebas o la compilación fallaron: no se publica.")
        return 1
    if status:
        msg = input("\nMensaje del commit (vacío = cancelar): ").strip()
        if not msg:
            print("Cancelado.")
            return 0
        git("add", "-A")
        git("commit", "-m", msg)
    git("fetch", "origin")
    behind = int(git("rev-list", "--count", f"HEAD..origin/{branch}", check=False) or 0)
    ahead = int(git("rev-list", "--count", f"origin/{branch}..HEAD", check=False) or 0)
    if behind:
        print(f"[DETENIDO] GitHub tiene {behind} commit(s) que no están aquí. Integre primero "
              f"(git pull --rebase) y revise conflictos. Nunca se hace force push.")
        return 1
    if not ahead:
        print("Nada que publicar: GitHub ya está al día.")
        return 0
    if input(f"¿Publicar {ahead} commit(s) en {remote}? [s/N]: ").strip().lower() not in ("s", "si", "sí"):
        print("Cancelado.")
        return 0
    git("push", "origin", branch)
    ok = git("rev-parse", "HEAD") == git("ls-remote", "origin", f"refs/heads/{branch}").split()[0]
    print("[OK] Sincronizado y verificado." if ok else "[ERROR] El remoto no coincide con el local.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
