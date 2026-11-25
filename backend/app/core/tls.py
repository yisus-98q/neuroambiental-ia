"""HTTPS con verificación ESTRICTA y recuperación de certificados intermedios ausentes (AIA), como un navegador.

Algunos servidores públicos (p. ej. geocatmin.ingemmet.gob.pe) no envían el certificado intermedio de su cadena.
Windows lo completa solo; Python en Linux (GitHub Actions) falla con «unable to get local issuer certificate».
Aquí NO se desactiva la verificación: se descarga el intermedio desde la URL «CA Issuers» del propio certificado
del servidor y se vuelve a verificar la cadena COMPLETA contra las raíces de confianza del sistema. Si la raíz no es
de confianza, falla igual que antes. El contexto recuperado se guarda en memoria por host.
"""
from __future__ import annotations

import ssl
import tempfile
import urllib.request
from pathlib import Path

_CONTEXTS: dict[str, ssl.SSLContext] = {}
_MAX_INTERMEDIATE_BYTES = 64 * 1024


def _missing_issuer(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) and "local issuer" in str(reason)


def _aia_context(host: str, port: int = 443) -> ssl.SSLContext:
    # Solo se LEE el certificado del servidor para conocer su emisor; la verificación real se hace después.
    leaf_pem = ssl.get_server_certificate((host, port), timeout=60)
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False, encoding="ascii") as f:
        f.write(leaf_pem)
        tmp = Path(f.name)
    try:
        info = ssl._ssl._test_decode_cert(str(tmp))  # noqa: SLF001 (decodificador de CPython)
    finally:
        tmp.unlink(missing_ok=True)
    urls = [u for u in info.get("caIssuers", ()) if u.startswith(("http://", "https://"))]
    if not urls:
        raise ssl.SSLError("El certificado del servidor no indica dónde obtener su intermedio (AIA).")
    with urllib.request.urlopen(urls[0], timeout=60) as r:   # certificado público; se verifica abajo
        der = r.read(_MAX_INTERMEDIATE_BYTES + 1)
    if len(der) > _MAX_INTERMEDIATE_BYTES:
        raise ssl.SSLError("Respuesta AIA demasiado grande.")
    pem = der.decode("ascii") if der.lstrip().startswith(b"-----BEGIN") else ssl.DER_cert_to_PEM_cert(der)
    ctx = ssl.create_default_context()      # raíces de confianza del sistema / certifi
    ctx.load_verify_locations(cadata=pem)   # solo se AÑADE el intermedio; la raíz sigue debiendo ser de confianza
    return ctx


def urlopen(req: urllib.request.Request, timeout: float):
    """Como urllib.request.urlopen, con verificación estricta y recuperación AIA si falta el intermedio."""
    host = urllib.request.urlparse(req.full_url).hostname or ""
    ctx = _CONTEXTS.get(host)
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    except Exception as exc:  # noqa: BLE001 - solo se trata el caso de intermedio ausente
        if ctx is not None or not _missing_issuer(exc):
            raise
    _CONTEXTS[host] = _aia_context(host)
    return urllib.request.urlopen(req, timeout=timeout, context=_CONTEXTS[host])
