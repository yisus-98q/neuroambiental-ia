"""Acceso remoto gratuito a Sentinel-2 L2A: catálogo STAC Earth Search + COGs públicos en AWS.

- Sin cuenta, sin claves, sin costo (AWS Open Data / Element 84 Earth Search).
- La lectura usa peticiones HTTP por rangos desde Python (urllib), que valida TLS con el
  almacén de certificados del sistema. No se desactiva nunca la verificación TLS.
- Solo se permiten hosts conocidos (evita que la API se use para pedir URLs arbitrarias).
"""
from __future__ import annotations

import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass, field

from rasterio.abc import FileContainer

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
ALLOWED_HOSTS = {
    "earth-search.aws.element84.com",
    "sentinel-cogs.s3.us-west-2.amazonaws.com",
    # Copernicus DEM GLO-30 (AWS Open Data, gratuito, sin cuenta) para NEURO 3D LAB / NEUROTERRAIN.
    "copernicus-dem-30m.s3.eu-central-1.amazonaws.com",
}
ITEM_ID_RE = re.compile(r"^S2[A-D]_[0-9]{2}[A-Z]{3}_[0-9]{8}_[0-9]+_L2A$")
USER_AGENT = "neuroambiental-ia/0.2 (uso local, investigación ambiental)"
TIMEOUT_S = 60
BLOCK = 256 * 1024          # tamaño de bloque de descarga
MAX_CACHED_BLOCKS = 48      # ~12 MB de caché por archivo como máximo


class RemoteError(Exception):
    """Fallo de red o respuesta inesperada del servicio remoto."""


def _check_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise RemoteError(f"Host no permitido: {parts.hostname}")
    return url


def _request(url: str, *, data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(_check_url(url), data=data,
                                 headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        return urllib.request.urlopen(req, timeout=TIMEOUT_S)  # noqa: S310 - host validado
    except urllib.error.HTTPError as exc:
        raise RemoteError(f"El servicio respondió {exc.code} para {urllib.parse.urlsplit(url).path}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RemoteError(f"No se pudo conectar: {exc}") from exc


# ---------------------------------------------------------------- STAC
@dataclass
class Scene:
    id: str
    datetime: str
    cloud_cover: float
    mgrs_tile: str
    platform: str
    bbox: list[float]
    assets: dict = field(repr=False)

    def public(self) -> dict:
        return {"id": self.id, "datetime": self.datetime, "cloud_cover": round(self.cloud_cover, 2),
                "mgrs_tile": self.mgrs_tile, "platform": self.platform, "bbox": self.bbox}


def _scene(feature: dict) -> Scene:
    p = feature.get("properties", {})
    return Scene(
        id=feature["id"], datetime=p.get("datetime", ""), cloud_cover=float(p.get("eo:cloud_cover", 100)),
        mgrs_tile=str(p.get("grid:code") or p.get("s2:mgrs_tile") or ""), platform=str(p.get("platform", "")),
        bbox=feature.get("bbox", []), assets=feature.get("assets", {}),
    )


def search_scenes(bbox: list[float], date_from: str, date_to: str, max_cloud: float, limit: int = 20) -> list[Scene]:
    body = {
        "collections": [COLLECTION], "bbox": bbox, "datetime": f"{date_from}T00:00:00Z/{date_to}T23:59:59Z",
        "limit": limit, "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }
    with _request(f"{STAC_URL}/search", data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json"}) as r:
        doc = json.load(r)
    return [_scene(f) for f in doc.get("features", [])]


def get_scene(item_id: str) -> Scene:
    if not ITEM_ID_RE.match(item_id):
        raise RemoteError("Identificador de escena con formato inválido.")
    with _request(f"{STAC_URL}/collections/{COLLECTION}/items/{item_id}") as r:
        return _scene(json.load(r))


# ---------------------------------------------------------------- lectura por rangos
def remote_size(url: str) -> int:
    with _request(_check_url(url), headers={"Range": "bytes=0-0"}) as r:
        rng = r.headers.get("Content-Range", "")
    if "/" not in rng:
        raise RemoteError("El servidor no admite lectura por rangos.")
    return int(rng.rsplit("/", 1)[1])


class HttpRangeFile(io.RawIOBase):
    """Archivo remoto de solo lectura. La caché de bloques es compartida por URL (GDAL abre el
    mismo archivo varias veces; así cada bloque se descarga una sola vez)."""

    def __init__(self, url: str, size: int, cache: OrderedDict, stats: dict):
        super().__init__()
        self.url = _check_url(url)
        self.pos = 0
        self.size = size
        self.stats = stats
        self._cache = cache

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = max(0, base + offset)
        return self.pos

    def _block(self, idx: int) -> bytes:
        if idx in self._cache:
            self._cache.move_to_end(idx)
            return self._cache[idx]
        start = idx * BLOCK
        end = min(start + BLOCK, self.size) - 1
        with _request(self.url, headers={"Range": f"bytes={start}-{end}"}) as r:
            data = r.read()
        self.stats["bytes"] = self.stats.get("bytes", 0) + len(data)
        self.stats["requests"] = self.stats.get("requests", 0) + 1
        self._cache[idx] = data
        if len(self._cache) > MAX_CACHED_BLOCKS:
            self._cache.popitem(last=False)
        return data

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, max(self.size - self.pos, 0))
        out = bytearray()
        while n > 0:
            idx, off = divmod(self.pos, BLOCK)
            chunk = self._block(idx)[off:off + n]
            if not chunk:
                break
            out += chunk
            self.pos += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def readinto(self, b) -> int:
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


class HttpsOpener(FileContainer):
    """Adaptador para rasterio.open(url, opener=...): GDAL lee a través de Python."""

    def __init__(self) -> None:
        self.stats: dict = {"bytes": 0, "requests": 0}
        self._sizes: dict[str, int] = {}
        self._caches: dict[str, OrderedDict] = {}

    @staticmethod
    def _is_cog(path: str) -> bool:
        # GDAL también busca archivos auxiliares (.aux.xml, .msk, .xml) que los COG públicos no tienen:
        # se responde "no existe" sin hacer peticiones.
        return path.startswith("https://") and path.lower().endswith((".tif", ".tiff"))

    def open(self, path: str, mode: str = "rb", **kwds):
        if "w" in mode or "a" in mode:
            raise PermissionError("Solo lectura.")
        if not self._is_cog(path):
            raise FileNotFoundError(path)
        return HttpRangeFile(path, self.size(path), self._caches.setdefault(path, OrderedDict()), self.stats)

    def isfile(self, path: str) -> bool:
        return self._is_cog(path)

    def isdir(self, path: str) -> bool:
        return False

    def ls(self, path: str) -> list[str]:
        return []

    def mtime(self, path: str) -> int:
        return 0

    def rm(self, path: str) -> None:
        raise PermissionError("Solo lectura.")

    def size(self, path: str) -> int:
        if not self._is_cog(path):
            return 0  # rutas ficticias (sondeo de rasterio) y archivos auxiliares inexistentes
        if path not in self._sizes:
            self._sizes[path] = remote_size(path)
        return self._sizes[path]
