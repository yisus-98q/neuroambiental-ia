"""Punto de entrada de la API central de NEUROAMBIENTAL IA."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    alerts,
    auth,
    biodiversity,
    construction,
    environmental,
    neuro3d,
    neurocore,
    neurodata,
    neuroprediction,
    neurotraining,
    neurovision,
    neurovoice,
    simulation,
    system,
    terrain,
    territories,
)
from app.core.config import settings

log = logging.getLogger("neuroambiental")


def create_app() -> FastAPI:
    app = FastAPI(title=f"{settings.app_name} API", version=settings.version,
                  description="API central. Las alertas son experimentales y no son emergencias oficiales.")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        # strict-origin-when-cross-origin: OpenStreetMap exige un Referer válido para servir teselas;
        # con esta política solo se envía el origen (nunca la ruta ni parámetros).
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):  # pragma: no cover - red de seguridad
        log.exception("Error no controlado en %s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Error interno. Revise los registros del servidor."})

    for module in (system, auth, neurocore, neurodata, alerts, biodiversity, environmental, neurotraining, neuroprediction, neurovision,
                   neuro3d, simulation, terrain, construction,
                   neurovoice, territories):
        app.include_router(module.router)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Si existe frontend/dist, se sirve desde el mismo proceso (un solo servicio = menos RAM)."""
    dist = settings.frontend_dist
    index = dist / "index.html"
    if not index.is_file():
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json"):
            return JSONResponse(status_code=404, content={"detail": "No encontrado."})
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
