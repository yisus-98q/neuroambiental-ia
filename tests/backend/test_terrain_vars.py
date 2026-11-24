"""P3.1 / P1.2: variables derivadas del DEM (curvatura, TPI, cauces) y variograma para el tamaño de bloque."""
from __future__ import annotations

import numpy as np

from app.modules.disasters import protocol, terrain_vars as tv
from app.modules.disasters.validation import _conclusion


def test_fill_removes_pits_and_keeps_drainage():
    z = np.full((7, 7), 10.0)
    z[3, 3] = 1.0                      # pozo cerrado en el centro
    f = tv.fill_depressions(z)
    assert f[3, 3] >= 10.0             # el pozo queda rellenado
    recv = tv.d8_receivers(f, 30.0, 30.0)
    # Ninguna celda interior queda sin salida tras el relleno (épsilon impone pendiente mínima).
    inner = np.zeros((7, 7), bool)
    inner[1:-1, 1:-1] = True
    assert (recv.reshape(7, 7)[inner] >= 0).all()


def test_accumulation_and_channel_follow_the_valley_axis():
    n = 120
    x = np.linspace(-1, 1, n)
    y = np.linspace(0, 1, n)
    z = 3000 + 800 * np.abs(x)[None, :] + 400 * y[:, None]      # valle en V que baja hacia la fila 0
    bbox = [-77.5, -9.5, -77.5 + n * 0.0003, -9.5 + n * 0.0003]  # celdas de ≈33 m
    filled = tv.fill_depressions(z)
    acc = tv.flow_accumulation(filled, tv.d8_receivers(filled, 33.0, 33.0))
    assert np.argmax(acc[1]) in (n // 2 - 1, n // 2)             # máxima acumulación en el eje del valle
    st = tv.compute(z.astype("float32"), bbox)
    assert set(st) == {"pendiente_deg", "elevacion_m", "curvatura", "tpi_m", "dist_cauce_m"}
    d = st["dist_cauce_m"]
    assert d[n // 3, n // 2] < d[n // 3, 5]                      # el eje está más cerca del cauce que el borde
    assert st["tpi_m"][n // 2, n // 2] < 0 < st["tpi_m"][n // 2, 20]   # fondo de valle bajo la media local


def test_variogram_range_is_short_for_noise_and_long_for_trends():
    rng = np.random.default_rng(0)
    n = 200
    noise = rng.normal(size=(n, n)).astype("float32")
    trend = np.add.outer(np.arange(n), np.arange(n)).astype("float32")
    v = protocol.variogram_range({"ruido": noise, "tendencia": trend}, (30.0, 30.0), seed=1, n=600)
    assert v["ruido"]["alcance_m"] < v["tendencia"]["alcance_m"]


def test_generic_single_variable_conclusion():
    def var(h, e, m, base, pv):
        return {"auc_heuristico_pendiente": h, "auc_solo_elevacion_baja": e, "por_variable": pv,
                "regresion_logistica": {"espacial": {"auc_mean": m, "auc_ic95_bloques": None}},
                "regresion_logistica_base": {"espacial": {"auc_mean": base}}}
    pv = {"dist_cauce_m": {"auc": 0.28, "auc_discriminante": 0.72, "direccion": "menor en eventos",
                           "mediana_eventos": 90.0, "mediana_ausencias": 260.0}}
    out = _conclusion(var(0.40, 0.80, 0.75, 0.78, pv), var(0.42, 0.66, 0.70, 0.67, pv))
    assert any("«dist_cauce_m» sola SÍ discrimina" in c and "menor en eventos" in c for c in out)
    assert any("no mejoran" in c and "0,72" in c for c in out)
