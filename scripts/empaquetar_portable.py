"""Construye NEUROAMBIENTAL_IA_PORTABLE (Fase 9 de NEUROAMBIENTAL IA 2.0).

Uso:  python scripts/empaquetar_portable.py [--destino D:\\NEUROAMBIENTAL_IA_PORTABLE] [--capacidad-gb 20]
                                            [--con-datos] [--wheelhouse]
- Código: `git archive HEAD` (solo archivos versionados: sin cachés, secretos ni .venv) + frontend compilado.
- Dependencias: lista fijada (pip freeze de backend/.deps). --wheelhouse descarga además los paquetes para
  instalar sin internet (descarga GRANDE: se informa el tamaño al terminar).
- Datos: por defecto solo manifiestos. --con-datos copia la base y los archivos locales (uso interno: el
  inventario y la geología de INGEMMET NO se pueden redistribuir).
- Antes de terminar: mide el tamaño, comprueba el espacio, genera MANIFESTO_ARCHIVOS.md y SHA-256, y verifica.
- Nunca borra ni sobrescribe: si el destino existe, crea una carpeta nueva con fecha.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GB = 1024 ** 3

BAT = {
    "VERIFICAR_EQUIPO.bat": ("Verificar el equipo", "verificar_equipo.py", ""),
    "INSTALAR_DEPENDENCIAS.bat": ("Instalar dependencias (entorno local)", "instalar.py", ""),
    "INICIAR_NEUROAMBIENTAL.bat": ("Iniciar NEUROAMBIENTAL IA", "servidor.py", "iniciar"),
    "DETENER_SISTEMA.bat": ("Detener NEUROAMBIENTAL IA", "servidor.py", "detener"),
    "EJECUTAR_PRUEBAS.bat": ("Ejecutar pruebas", "pruebas.py", ""),
    "ENTRENAR_MODELOS.bat": ("Entrenar y validar modelos", "datasets.py", "entrenar"),
    "DESCARGAR_DATASETS.bat": ("Descargar datasets por recorte", "datasets.py", "descargar"),
    "VERIFICAR_INTEGRIDAD.bat": ("Verificar integridad del paquete", "verificar_integridad.py", ""),
}

BAT_TEMPLATE = r"""@echo off
setlocal
chcp 65001 >nul
title NEUROAMBIENTAL IA - {titulo}
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo [ERROR] No se encontro Python. Instale Python 3.14 de python.org ^(gratuito^) marcando "Add to PATH".
  pause
  exit /b 1
)
%PY% "scripts\{script}" {arg}
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERROR] El proceso termino con codigo %RC%. Revise la carpeta logs\ .
) else (
  echo [OK] Proceso terminado.
)
pause
exit /b %RC%
"""

PROFILES = {
    "perfil_ligero.env": "# Equipo secundario (4 GB): consulta, visualización e inferencia.\nNEURO_PROFILE=ligero\n",
    "perfil_estandar.env": "# Equipo intermedio (8–24 GB).\nNEURO_PROFILE=estandar\n",
    "perfil_potente.env": ("# Equipo principal (32 GB): entrenamiento y validación.\nNEURO_PROFILE=potente\n"
                           "NEURO_RAM_TARGET_GB=16\nNEURO_RAM_MAX_GB=20\n"),
    "activo.env": "# Perfil en uso. «auto» lo detecta por la RAM. Copie aquí el contenido de otro perfil para forzarlo.\n"
                  "NEURO_PROFILE=auto\n",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def size_of(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default=r"D:\NEUROAMBIENTAL_IA_PORTABLE")
    ap.add_argument("--capacidad-gb", type=float, default=20.0)
    ap.add_argument("--con-datos", action="store_true")
    ap.add_argument("--wheelhouse", action="store_true")
    a = ap.parse_args()

    dest = Path(a.destino)
    if dest.exists():
        dest = dest.with_name(f"{dest.name}_{dt.datetime.now():%Y%m%d-%H%M%S}")
        print(f"El destino ya existe: se crea {dest} (no se sobrescribe nada).")
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    if dirty:
        print("AVISO: hay cambios sin confirmar; el paquete usa la versión confirmada", head)

    # Estimación previa (código + frontend + dependencias + datos opcionales) frente a la capacidad.
    est = size_of(REPO / "frontend" / "dist") + 5 * 2**20 + (size_of(REPO / "data") if a.con_datos else 0)
    if a.wheelhouse:
        est += size_of(REPO / "backend" / ".deps") // 2   # aproximación: ruedas comprimidas ≈ mitad de lo instalado
    free = shutil.disk_usage(dest.anchor or ".").free
    print(f"Tamaño estimado: {human(est)} · libre en destino: {human(free)} · capacidad del USB: {a.capacidad_gb} GB")
    if est > a.capacidad_gb * GB or est > free:
        print("ERROR: el paquete no cabe. Divida en paquete principal + datos/modelos opcionales.")
        return 1

    codigo = dest / "codigo"
    codigo.mkdir(parents=True)
    tar = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=REPO, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(codigo, filter="data")
    shutil.copytree(REPO / "frontend" / "dist", codigo / "frontend" / "dist")

    dep = dest / "dependencias"
    dep.mkdir()
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze", "--path", str(REPO / "backend" / ".deps")],
                            capture_output=True, text=True).stdout
    lock = "\n".join(sorted(line for line in freeze.splitlines() if line and not line.startswith("-e"))) + "\n"
    (dep / "requirements-lock.txt").write_text(
        f"# Versiones fijadas (pip freeze de backend/.deps, commit {head}). Python 3.14, Windows x64.\n" + lock,
        encoding="utf-8")
    if a.wheelhouse:
        wh = dep / "wheelhouse"
        wh.mkdir()
        subprocess.run([sys.executable, "-m", "pip", "download", "--only-binary=:all:", "-d", str(wh), "-r",
                        str(dep / "requirements-lock.txt")], check=False)
        print("Wheelhouse:", human(size_of(wh)))

    cfg = dest / "config"
    cfg.mkdir()
    for name, text in PROFILES.items():
        (cfg / name).write_text(text, encoding="utf-8")
    shutil.copytree(codigo / "docs", dest / "docs")
    shutil.copytree(REPO / "portable" / "scripts", dest / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (dest / "modelos").mkdir()
    (dest / "modelos" / "LEEME.md").write_text(
        "# Modelos exportados\n\nNo hay modelos entrenados ni validados todavía (ver docs/INFORME_RESULTADOS_"
        "ENTRENAMIENTO.md). Los modelos se exportan desde NEURAL TRAINING (botón «Exportar modelo + ficha») y "
        "se copian aquí con su model_card.json y su SHA-256.\n", encoding="utf-8")
    ds = dest / "datasets"
    shutil.copytree(REPO / "datasets" / "manifiestos", ds / "manifiestos")
    if a.con_datos:
        shutil.copytree(REPO / "data", ds / "datos_locales", ignore=shutil.ignore_patterns("backups"))
        (ds / "datos_locales" / "LICENCIAS.txt").write_text(
            "Uso interno. Inventario, litología y geomorfología de INGEMMET: sin licencia abierta, NO redistribuir.\n"
            "Copernicus DEM y Sentinel-2: libres con atribución.\n", encoding="utf-8")
    (ds / "LEEME.md").write_text(
        "# Datasets\n\nPor defecto solo se incluyen los MANIFIESTOS (metadatos, procedencia, licencia, SHA-256). "
        "Los datos se descargan por recorte con DESCARGAR_DATASETS.bat. Los datasets completos permanecen en el "
        "equipo principal; el equipo de 4 GB usa recortes.\n", encoding="utf-8")
    (dest / "logs").mkdir()

    for name, (titulo, script, arg) in BAT.items():
        (dest / name).write_bytes(BAT_TEMPLATE.format(titulo=titulo, script=script, arg=arg)
                                  .replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
    shutil.copy2(REPO / "portable" / "README_USB.md", dest / "README_USB.md")

    # Manifiesto, checksums y verificación.
    files = sorted(p for p in dest.rglob("*") if p.is_file() and "checksums" not in p.parts
                   and p.name != "MANIFESTO_ARCHIVOS.md")
    total = sum(p.stat().st_size for p in files)
    (dest / "checksums").mkdir()
    lines = [f"{sha256(p)}  {p.relative_to(dest).as_posix()}" for p in files]
    (dest / "checksums" / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    parts = {}
    for p in files:
        top = p.relative_to(dest).parts[0] if len(p.relative_to(dest).parts) > 1 else "(raíz)"
        n, s = parts.get(top, (0, 0))
        parts[top] = (n + 1, s + p.stat().st_size)
    man = ["# Manifiesto de archivos", "", f"- Versión: commit `{head}` · generado {dt.datetime.now():%Y-%m-%d %H:%M}",
           f"- Total: **{len(files)} archivos, {human(total)}** (capacidad declarada del USB: {a.capacidad_gb} GB)",
           f"- Datos locales incluidos: {'sí (uso interno)' if a.con_datos else 'no (solo manifiestos)'}",
           f"- Wheelhouse sin internet: {'sí' if a.wheelhouse else 'no (INSTALAR_DEPENDENCIAS usa PyPI)'}", "",
           "| Carpeta | Archivos | Tamaño |", "|---|---|---|"]
    man += [f"| {k} | {n} | {human(s)} |" for k, (n, s) in sorted(parts.items())]
    man += ["", "Integridad: `VERIFICAR_INTEGRIDAD.bat` compara cada archivo con `checksums/SHA256SUMS.txt`."]
    (dest / "MANIFESTO_ARCHIVOS.md").write_text("\n".join(man) + "\n", encoding="utf-8")
    bad = [ln for ln in lines if sha256(dest / ln.split("  ", 1)[1]) != ln.split("  ", 1)[0]]
    print(f"\nPaquete creado en {dest}: {len(files)} archivos, {human(total)}; integridad: "
          f"{'correcta' if not bad else f'{len(bad)} errores'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
