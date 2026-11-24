"""Perfiles de ejecución según el hardware (Fase 8 de NEUROAMBIENTAL IA 2.0).

Dos equipos con la MISMA arquitectura y el mismo código:
- «ligero» (< 8 GB de RAM, p. ej. el equipo secundario de 4 GB): consulta, visualización e inferencia;
  trabajos pesados limitados a ≈600 MB.
- «estandar» (8–24 GB): procesamiento moderado.
- «potente» (≥ 24 GB, p. ej. el equipo principal de 32 GB): preparación de datos, entrenamiento y validación.
  Objetivo de RAM 10–16 GB y límite máximo configurable de 20 GB.

El perfil se detecta solo, pero se puede forzar SIN tocar el código con variables de entorno:
NEURO_PROFILE=ligero|estandar|potente, NEURO_RAM_TARGET_GB, NEURO_RAM_MAX_GB, NEURO_N_JOBS.
Sin dependencias nuevas: la memoria se lee con ctypes (Windows) o /proc (Linux).
"""
from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import asdict, dataclass

GB = 1024 ** 3


def memory_bytes() -> tuple[int, int]:
    """(total, disponible) en bytes; (0, 0) si no se puede leer."""
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullTotalPhys), int(st.ullAvailPhys)
        return 0, 0
    try:
        info = {}
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) * 1024
        return info.get("MemTotal", 0), info.get("MemAvailable", info.get("MemFree", 0))
    except OSError:
        return 0, 0


def process_peak_bytes() -> int:
    """Pico de memoria del proceso (working set en Windows, ru_maxrss en POSIX); 0 si no se puede leer."""
    if sys.platform == "win32":
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        try:
            h = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                return int(pmc.PeakWorkingSetSize)
        except (AttributeError, OSError):
            return 0
        return 0
    try:
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    except (ImportError, OSError):
        return 0


def process_current_bytes() -> int:
    if sys.platform == "win32":
        return 0 if not hasattr(ctypes, "windll") else _win_current()
    try:
        with open("/proc/self/statm", encoding="ascii") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError):
        return 0


def _win_current() -> int:
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t), ("d", ctypes.c_size_t),
                    ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    try:
        if ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc),
                                                    pmc.cb):
            return int(pmc.WorkingSetSize)
    except (AttributeError, OSError):
        pass
    return 0


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    ram_total_gb: float
    ram_target_gb: float        # memoria que puede usar un trabajo pesado en condiciones normales
    ram_max_gb: float           # tope duro: no se inicia un trabajo que lo supere
    n_jobs: int                 # hilos para scikit-learn
    max_dem_px: int             # lado máximo de un DEM de análisis
    rf_trees: int
    validation_seeds_max: int
    training_allowed: bool      # entrenamiento de modelos medianos (ligero: solo modelos pequeños)
    voice_local_engine: bool    # motores de voz locales (Piper/Vosk) recomendables

    def as_dict(self) -> dict:
        return asdict(self)


def _env_float(name: str) -> float | None:
    v = os.environ.get(name, "").strip()
    try:
        return float(v) if v else None
    except ValueError:
        return None


def detect_profile() -> Profile:
    total, _ = memory_bytes()
    total_gb = round(total / GB, 2) if total else 0.0
    cores = os.cpu_count() or 1
    forced = os.environ.get("NEURO_PROFILE", "auto").strip().lower()
    name = forced if forced in ("ligero", "estandar", "potente") else (
        "potente" if total_gb >= 24 else "estandar" if total_gb >= 8 else "ligero")
    if name == "ligero":
        base = dict(ram_target_gb=0.6, ram_max_gb=1.0, n_jobs=1, max_dem_px=1600, rf_trees=100,
                    validation_seeds_max=5, training_allowed=False, voice_local_engine=False,
                    description="Equipo de pocos recursos: consulta, visualización e inferencia; trabajos pesados "
                                "pequeños y de uno en uno.")
    elif name == "estandar":
        base = dict(ram_target_gb=3.0, ram_max_gb=min(6.0, max(total_gb * 0.6, 3.0)), n_jobs=max(1, min(cores - 1, 4)),
                    max_dem_px=3000, rf_trees=200, validation_seeds_max=10, training_allowed=True,
                    voice_local_engine=True,
                    description="Equipo intermedio: procesamiento y entrenamiento moderados.")
    else:
        base = dict(ram_target_gb=16.0, ram_max_gb=20.0, n_jobs=max(1, min(cores - 1, 8)), max_dem_px=5000,
                    rf_trees=300, validation_seeds_max=20, training_allowed=True, voice_local_engine=True,
                    description="Equipo principal: preparación de datos, entrenamiento y validación (objetivo "
                                "10–16 GB, tope 20 GB).")
    target, mx = _env_float("NEURO_RAM_TARGET_GB"), _env_float("NEURO_RAM_MAX_GB")
    if target:
        base["ram_target_gb"] = target
    if mx:
        base["ram_max_gb"] = mx
    if total_gb:
        base["ram_max_gb"] = min(base["ram_max_gb"], round(total_gb * 0.75, 2))  # nunca más del 75 % físico
        base["ram_target_gb"] = min(base["ram_target_gb"], base["ram_max_gb"])
    nj = os.environ.get("NEURO_N_JOBS", "").strip()
    if nj.isdigit() and int(nj) > 0:
        base["n_jobs"] = int(nj)
    return Profile(name=name, ram_total_gb=total_gb, **base)


def snapshot() -> dict:
    total, avail = memory_bytes()
    p = detect_profile()
    return {"perfil": p.as_dict(), "ram_total_gb": round(total / GB, 2), "ram_disponible_gb": round(avail / GB, 2),
            "proceso_actual_mb": round(process_current_bytes() / 2**20, 1),
            "proceso_pico_mb": round(process_peak_bytes() / 2**20, 1), "cpu_hilos": os.cpu_count(),
            "plataforma": sys.platform}
