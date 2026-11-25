"""Recuperación AIA: solo ante «intermedio ausente», sin desactivar la verificación."""
from __future__ import annotations

import ssl
import urllib.error
import urllib.request

import pytest

from app.core import tls


def _req():
    return urllib.request.Request("https://geocatmin.ingemmet.gob.pe/x")


def test_missing_intermediate_triggers_aia_once_and_is_cached(monkeypatch):
    tls._CONTEXTS.clear()
    calls = []
    sentinel = ssl.create_default_context()

    def fake_urlopen(req, timeout, context=None):
        calls.append(context)
        if context is None:
            raise urllib.error.URLError(ssl.SSLCertVerificationError(
                "certificate verify failed: unable to get local issuer certificate"))
        return "ok"

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(tls, "_aia_context", lambda host, port=443: sentinel)
    assert tls.urlopen(_req(), 5) == "ok" and calls == [None, sentinel]
    assert tls.urlopen(_req(), 5) == "ok" and calls[-1] is sentinel          # contexto reutilizado
    tls._CONTEXTS.clear()


def test_other_tls_errors_are_not_bypassed(monkeypatch):
    tls._CONTEXTS.clear()

    def fake_urlopen(req, timeout, context=None):
        raise urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed: self-signed certificate"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(tls, "_aia_context", lambda *a, **k: pytest.fail("no debe intentar AIA"))
    with pytest.raises(urllib.error.URLError):
        tls.urlopen(_req(), 5)
    # La verificación nunca se desactiva: los contextos creados exigen certificado y nombre de host.
    ctx = ssl.create_default_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
