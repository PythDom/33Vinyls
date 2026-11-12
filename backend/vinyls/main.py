"""FastAPI application: API under /api, the installable web app (PWA) everywhere else."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, api, auth, db, sync
from .config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.migrate()
    yield


app = FastAPI(title="33Vinyls", version=__version__, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(auth.router)
app.include_router(sync.router)
app.include_router(api.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": __version__, "demo": settings.demo}


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def api_not_found(path: str):
    return JSONResponse({"detail": "Not found"}, status_code=404)


# The service worker and manifest must never be cached by the browser's HTTP cache,
# otherwise app updates would not arrive on the phones.
NO_CACHE = {"Cache-Control": "no-cache"}


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(settings.static_dir / "sw.js", media_type="text/javascript", headers=NO_CACHE)


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(settings.static_dir / "manifest.webmanifest", media_type="application/manifest+json", headers=NO_CACHE)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(settings.static_dir / "index.html", headers=NO_CACHE)


if settings.static_dir.exists():
    app.mount("/", StaticFiles(directory=settings.static_dir), name="static")
