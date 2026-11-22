"""Procesamiento clásico de imágenes con OpenCV (determinista, sin modelos entrenados).

Funciones puras: reciben/devuelven arrays y diccionarios. No tocan base de datos ni disco.
Todas trabajan sobre una imagen de máx. MAX_SIDE px por lado (protege memoria en equipos de 4 GB).
"""
from __future__ import annotations

import struct

import cv2
import numpy as np

MAX_SIDE = 2048
MAX_PIXELS = 25_000_000
MAX_REGIONS = 200
MIN_MATCHES = 10
CHANGE_MIN_DIFF = 25  # diferencia mínima (0-255) para considerar un cambio, aunque Otsu pida menos
OPENCV_VERSION = cv2.__version__

CONFIDENCE_NOTE = ("no aplica: procesamiento determinístico; requiere un modelo entrenado para clasificar")
LIMITATIONS = [
    "La iluminación, las sombras y el contraste de la foto condicionan todos los resultados.",
    "La resolución y la compresión JPG limitan los detalles detectables; se trabaja con máx. 2048 px por lado.",
    "Las regiones son zonas de la imagen con características visuales parecidas, no objetos identificados: "
    "no se clasifica qué son (eso requiere un modelo entrenado).",
    "Las medidas están en píxeles; sin escala ni georreferenciación no equivalen a metros ni a hectáreas.",
]
EXG_LIMITATION = ("El índice de verdor ExG detecta píxeles verdosos (aparente vegetación): no equivale a "
                  "vegetación confirmada; césped artificial, pintura, objetos verdes o reflejos también lo elevan.")
COMPARE_LIMITATIONS = [
    "Solo es válida para fotos comparables de la misma escena (mismo encuadre aproximado y objetos fijos con textura).",
    "No considera georreferenciación ni diferencias de sensor, lente, exposición o época del año.",
    "Un cambio detectado es una diferencia de píxeles; no confirma qué cambió ni su causa. Requiere revisión humana.",
    "Sombras, nubes, vehículos o personas en movimiento también producen diferencias.",
]


class ImageError(ValueError):
    """Imagen inválida, corrupta o demasiado grande (HTTP 422)."""


class ParamError(ValueError):
    """Parámetros de operación inválidos (HTTP 422)."""


class AlignError(ValueError):
    """No se pudo alinear la segunda imagen con la primera (HTTP 422)."""


# --- Catálogo de operaciones y validación de parámetros -------------------------------------------------

def _p(name, typ, default, lo, hi, desc):
    return {"name": name, "type": typ, "default": default, "min": lo, "max": hi, "description": desc}


OPERATIONS: dict[str, dict] = {
    "canny": {
        "label": "Bordes (Canny)",
        "description": "Bordes sobre escala de grises con suavizado gaussiano previo.",
        "params": [
            _p("blur_ksize", "int", 5, 3, 15, "Tamaño (impar) del suavizado gaussiano."),
            _p("low", "float", 50, 0, 254, "Umbral bajo de histéresis."),
            _p("high", "float", 150, 1, 255, "Umbral alto de histéresis (mayor que el bajo)."),
        ],
    },
    "clahe": {
        "label": "Contraste (CLAHE)",
        "description": "Ecualización adaptativa del contraste sobre la luminancia.",
        "params": [
            _p("clip_limit", "float", 2.0, 1.0, 10.0, "Límite de recorte del contraste."),
            _p("tile", "int", 8, 2, 16, "Divisiones de la cuadrícula por lado."),
        ],
    },
    "segmentacion": {
        "label": "Segmentación (Otsu + contornos)",
        "description": "Umbral automático de Otsu y contornos: regiones con área, caja y centroide.",
        "params": [
            _p("blur_ksize", "int", 5, 1, 15, "Suavizado gaussiano previo (1 = sin suavizado)."),
            _p("min_area", "int", 100, 1, 1_000_000, "Área mínima de región en px."),
            _p("invert", "bool", False, None, None, "Detectar regiones oscuras en lugar de claras."),
        ],
    },
    "verdor_exg": {
        "label": "Índice de verdor ExG",
        "description": "ExG = 2G−R−B sobre coordenadas cromáticas; máscara de aparente vegetación (solo RGB).",
        "params": [
            _p("threshold", "float", 0.10, -0.5, 1.0, "Umbral de ExG para la máscara."),
            _p("min_area", "int", 100, 1, 1_000_000, "Área mínima de región en px."),
        ],
    },
    "caracteristicas": {
        "label": "Características de la imagen",
        "description": "Tamaño, media y desviación por canal, densidad de bordes, nitidez y número de regiones.",
        "params": [],
    },
}


def public_operations() -> list[dict]:
    return [{"key": k, **{kk: vv for kk, vv in v.items()}} for k, v in OPERATIONS.items()]


def validate_params(operation: str, params: dict | None) -> dict:
    if operation not in OPERATIONS:
        raise ParamError(f"Operación desconocida: {operation}. Disponibles: {', '.join(OPERATIONS)}.")
    params = dict(params or {})
    specs = {p["name"]: p for p in OPERATIONS[operation]["params"]}
    unknown = set(params) - set(specs)
    if unknown:
        raise ParamError(f"Parámetros no admitidos para {operation}: {sorted(unknown)}.")
    out = {}
    for name, spec in specs.items():
        val = params.get(name, spec["default"])
        try:
            if spec["type"] == "bool":
                if not isinstance(val, bool):
                    raise ValueError
            elif spec["type"] == "int":
                if isinstance(val, bool) or (isinstance(val, float) and not val.is_integer()):
                    raise ValueError
                val = int(val)
            else:
                if isinstance(val, bool):
                    raise ValueError
                val = float(val)
                if not np.isfinite(val):
                    raise ValueError
        except (TypeError, ValueError):
            raise ParamError(f"El parámetro '{name}' debe ser de tipo {spec['type']}.") from None
        if spec["type"] != "bool" and not (spec["min"] <= val <= spec["max"]):
            raise ParamError(f"El parámetro '{name}' debe estar entre {spec['min']} y {spec['max']}.")
        out[name] = val
    if "blur_ksize" in out and out["blur_ksize"] % 2 == 0:
        raise ParamError("blur_ksize debe ser impar.")
    if operation == "canny" and out["low"] >= out["high"]:
        raise ParamError("El umbral bajo debe ser menor que el alto.")
    return out


# --- Lectura y preparación ------------------------------------------------------------------------------

def header_size(raw: bytes) -> tuple[int, int] | None:
    """Ancho y alto leídos de la cabecera PNG/JPG sin decodificar (None si no se puede)."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
        return struct.unpack(">II", raw[16:24])
    if raw.startswith(b"\xff\xd8"):
        i = 2
        while i + 9 < len(raw):
            if raw[i] != 0xFF:
                i += 1
                continue
            marker = raw[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", raw[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", raw[i + 2:i + 4])[0]
    return None


def decode_image(raw: bytes) -> np.ndarray:
    """Decodifica a BGR de 3 canales. Rechaza corruptas y > 25 MP (antes de decodificar si es posible)."""
    size = header_size(raw)
    if size and size[0] * size[1] > MAX_PIXELS:
        raise ImageError(f"La imagen ({size[0]}x{size[1]}) supera el máximo de {MAX_PIXELS // 1_000_000} MP.")
    try:
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:
        img = None
    if img is None or img.size == 0:
        raise ImageError("La imagen está corrupta o no se pudo decodificar.")
    h, w = img.shape[:2]
    if h * w > MAX_PIXELS:
        raise ImageError(f"La imagen ({w}x{h}) supera el máximo de {MAX_PIXELS // 1_000_000} MP.")
    return img


def to_work_size(img: np.ndarray) -> tuple[np.ndarray, dict]:
    h, w = img.shape[:2]
    info = {"original_width": w, "original_height": h, "resized": False, "scale": 1.0}
    if max(h, w) > MAX_SIDE:
        s = MAX_SIDE / max(h, w)
        img = cv2.resize(img, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
        info.update(resized=True, scale=round(s, 6),
                    method="INTER_AREA")
    info["work_width"], info["work_height"] = img.shape[1], img.shape[0]
    return img, info


def _odd_blur(gray: np.ndarray, k: int) -> np.ndarray:
    return cv2.GaussianBlur(gray, (k, k), 0) if k > 1 else gray


def _regions(mask: np.ndarray, min_area: int, shape: tuple[int, int]) -> tuple[list[dict], int]:
    """Contornos externos → regiones (área del contorno en px, caja [x,y,w,h], centroide). Máx. 200."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total_px = shape[0] * shape[1]
    found = []
    for c in contours:
        area = float(cv2.contourArea(c))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        m = cv2.moments(c)
        cx, cy = (m["m10"] / m["m00"], m["m01"] / m["m00"]) if m["m00"] else (x + w / 2, y + h / 2)
        found.append({"area_px": round(area, 1), "area_pct": round(100 * area / total_px, 3),
                      "bbox": [x, y, w, h], "centroid": [round(cx, 1), round(cy, 1)]})
    found.sort(key=lambda r: r["area_px"], reverse=True)
    total = len(found)
    out = found[:MAX_REGIONS]
    for i, r in enumerate(out, 1):
        r["id"] = i
    return out, total


def _draw_regions(base: np.ndarray, regions: list[dict], mask: np.ndarray | None = None) -> np.ndarray:
    over = base.copy()
    if mask is not None:
        tint = over.copy()
        tint[mask > 0] = (0, 200, 0)
        over = cv2.addWeighted(over, 0.6, tint, 0.4, 0)
    for r in regions:
        x, y, w, h = r["bbox"]
        cv2.rectangle(over, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.putText(over, str(r["id"]), (x + 2, max(12, y + 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 255), 1, cv2.LINE_AA)
    return over


def _base_features(img: np.ndarray) -> dict:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    mean, std = cv2.meanStdDev(img)
    return {
        "ancho_px": img.shape[1], "alto_px": img.shape[0],
        "media_rgb": [round(float(v), 2) for v in mean.ravel()[::-1]],
        "desv_rgb": [round(float(v), 2) for v in std.ravel()[::-1]],
        "densidad_bordes_pct": round(100 * float(np.count_nonzero(edges)) / edges.size, 3),
        "nitidez_laplaciano": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2),
    }, gray


def _result(processed, overlay, regions, total, features, limitations, extra=None) -> dict:
    return {"processed": processed, "overlay": overlay, "regions": regions, "regions_total": total,
            "regions_truncated": total > len(regions), "features": features, "limitations": limitations,
            **(extra or {})}


def run_operation(img: np.ndarray, operation: str, params: dict) -> dict:
    """Ejecuta una operación con parámetros ya validados. `img` es BGR en tamaño de trabajo."""
    lims = list(LIMITATIONS)
    base, gray = _base_features(img)
    if operation == "canny":
        edges = cv2.Canny(_odd_blur(gray, params["blur_ksize"]), params["low"], params["high"])
        feats = {**base, "densidad_bordes_pct": round(100 * float(np.count_nonzero(edges)) / edges.size, 3),
                 "umbral_bajo": params["low"], "umbral_alto": params["high"]}
        return _result(edges, None, [], 0, feats, lims)
    if operation == "clahe":
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=params["clip_limit"], tileGridSize=(params["tile"], params["tile"]))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        out_gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        feats = {**base, "desv_luminancia_antes": round(float(gray.std()), 2),
                 "desv_luminancia_despues": round(float(out_gray.std()), 2)}
        lims.append("CLAHE amplifica también el ruido de la imagen; mejora la visualización, no añade información.")
        return _result(out, None, [], 0, feats, lims)
    if operation == "segmentacion":
        _, mask = cv2.threshold(_odd_blur(gray, params["blur_ksize"]), 0, 255,
                                (cv2.THRESH_BINARY_INV if params["invert"] else cv2.THRESH_BINARY) + cv2.THRESH_OTSU)
        regs, total = _regions(mask, params["min_area"], gray.shape)
        otsu = float(cv2.threshold(_odd_blur(gray, params["blur_ksize"]), 0, 255,
                                   cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0])
        feats = {**base, "umbral_otsu": round(otsu, 1), "regiones_total": total,
                 "area_segmentada_pct": round(100 * float(np.count_nonzero(mask)) / mask.size, 3)}
        lims.append("Otsu separa claro/oscuro; en escenas sin dos grupos de brillo claros las regiones pueden no ser significativas.")
        return _result(mask, _draw_regions(img, regs), regs, total, feats, lims)
    if operation == "verdor_exg":
        if np.array_equal(img[:, :, 0], img[:, :, 1]) and np.array_equal(img[:, :, 1], img[:, :, 2]):
            raise ImageError("La imagen no tiene color (escala de grises): el índice ExG requiere RGB.")
        f = img.astype(np.float32)
        total_c = f.sum(axis=2)
        total_c[total_c == 0] = 1.0
        b, g, r = (f[:, :, i] / total_c for i in range(3))
        exg = 2 * g - r - b  # rango teórico [-1, 1]
        mask = (exg > params["threshold"]).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        regs, total = _regions(mask, params["min_area"], gray.shape)
        vis = cv2.applyColorMap(np.clip((exg + 1) * 127.5, 0, 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
        feats = {**base, "exg_medio": round(float(exg.mean()), 4), "exg_max": round(float(exg.max()), 4),
                 "umbral_exg": params["threshold"], "regiones_total": total,
                 "verdor_aparente_pct": round(100 * float(np.count_nonzero(mask)) / mask.size, 3)}
        lims.append(EXG_LIMITATION)
        return _result(vis, _draw_regions(img, regs, mask), regs, total, feats, lims)
    # caracteristicas
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    _, mask = cv2.threshold(cv2.GaussianBlur(gray, (5, 5), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    regs, total = _regions(mask, 100, gray.shape)
    feats = {**base, "regiones_total": total, "regiones_criterio": "Otsu (claro), área ≥ 100 px"}
    return _result(edges, _draw_regions(img, regs), regs, total, feats, lims)


# --- Comparación de dos imágenes ------------------------------------------------------------------------

def align(a_gray: np.ndarray, b_img: np.ndarray, b_gray: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """Alinea B sobre A con ORB + homografía RANSAC. Devuelve (B alineada, máscara válida, métricas)."""
    orb = cv2.ORB_create(nfeatures=2000)
    ka, da = orb.detectAndCompute(a_gray, None)
    kb, db_ = orb.detectAndCompute(b_gray, None)
    if da is None or db_ is None or len(ka) < MIN_MATCHES or len(kb) < MIN_MATCHES:
        raise AlignError("No se pudieron alinear las imágenes: hay muy pocos puntos de referencia en común.")
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(db_, da, k=2)
    good = [m for p in pairs if len(p) == 2 for m, n in [p] if m.distance < 0.75 * n.distance]
    if len(good) < MIN_MATCHES:
        raise AlignError(f"No se pudieron alinear las imágenes: solo {len(good)} correspondencias buenas "
                         f"(mínimo {MIN_MATCHES}). ¿Son la misma escena?")
    src = np.float32([kb[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([ka[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, inl = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    n_inl = int(inl.sum()) if inl is not None else 0
    if H is None or n_inl < MIN_MATCHES:
        raise AlignError(f"No se pudieron alinear las imágenes: solo {n_inl} correspondencias consistentes "
                         f"tras RANSAC (mínimo {MIN_MATCHES}).")
    h, w = a_gray.shape
    warped = cv2.warpPerspective(b_img, H, (w, h), flags=cv2.INTER_LINEAR)
    valid = cv2.warpPerspective(np.full(b_gray.shape, 255, np.uint8), H, (w, h), flags=cv2.INTER_NEAREST)
    valid = cv2.erode(valid, np.ones((5, 5), np.uint8))
    return warped, valid, {"good_matches": len(good), "inliers": n_inl, "homography": [round(float(v), 5) for v in H.ravel()]}


def compare_images(a: np.ndarray, b: np.ndarray, min_area: int = 100) -> dict:
    """Detección de cambios: alinea B a A, iguala histogramas, diferencia, Otsu y limpieza morfológica."""
    a_gray = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    b_gray = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    warped, valid, align_info = align(a_gray, b, b_gray)
    w_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(cv2.equalizeHist(a_gray), cv2.equalizeHist(w_gray))
    diff = cv2.GaussianBlur(diff, (5, 5), 0)
    diff[valid == 0] = 0
    otsu = float(cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0])
    thr = max(otsu, CHANGE_MIN_DIFF)
    mask = (diff > thr).astype(np.uint8) * 255
    k = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, k), cv2.MORPH_CLOSE, k)
    mask[valid == 0] = 0
    valid_px = int(np.count_nonzero(valid))
    changed = int(np.count_nonzero(mask))
    regs, total = _regions(mask, min_area, a_gray.shape)
    overlay = _draw_regions(a, regs, None)
    red = overlay.copy()
    red[mask > 0] = (0, 0, 255)
    overlay = cv2.addWeighted(overlay, 0.55, red, 0.45, 0)
    metrics = {"cambio_pct": round(100 * changed / valid_px, 3) if valid_px else 0.0,
               "pixeles_cambiados": changed, "pixeles_comparables": valid_px,
               "umbral_otsu": round(otsu, 1), "umbral_aplicado": round(thr, 1),
               "regiones_total": total, **{f"alineacion_{k_}": v for k_, v in align_info.items()}}
    return _result(overlay, None, regs, total, metrics, list(LIMITATIONS) + COMPARE_LIMITATIONS,
                   {"align": align_info, "mask": mask})


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ImageError("No se pudo codificar la imagen resultante.")
    return buf.tobytes()
