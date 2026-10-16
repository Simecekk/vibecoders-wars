"""Vibecoders Wars FastAPI app (maintainer-owned; players never edit this file).

Areas are discovered automatically: every `app/areas/<id>/router.py` exporting
`router: APIRouter` is mounted under the `/<id>` prefix. The root `/` serves the area map (app/map_page.py).
"""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi import APIRouter, FastAPI

from app.map_page import router as map_router

AREAS_DIR = Path(__file__).parent / "areas"


def discover_areas() -> list[tuple[str, APIRouter]]:
    found: list[tuple[str, APIRouter]] = []
    for router_file in sorted(AREAS_DIR.glob("*/router.py")):
        area_id = router_file.parent.name
        module = importlib.import_module(f"app.areas.{area_id}.router")
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            raise TypeError(f"app/areas/{area_id}/router.py must export `router = APIRouter()`")
        found.append((area_id, router))
    return found


def create_app() -> FastAPI:
    application = FastAPI(title="Vibecoders Wars")
    application.include_router(map_router)
    for area_id, router in discover_areas():
        application.include_router(router, prefix=f"/{area_id}", tags=[area_id])

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
