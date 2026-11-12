"""FastAPI application: API under /api, the installable web app (PWA) everywhere else."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, api, auth, backup, db, importer, jobs, sharing, sync
from .config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.migrate()
    task = asyncio.create_task(jobs.loop()) if settings.background_jobs else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="33Vinyls", version=__version__, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.middleware("http")
async def no_store_api(request, call_next):
    """API answers change (prices, sharing, ownership): never let the browser reuse an old one."""
    response = await call_next(request)
    if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(auth.router)
app.include_router(sync.router)
app.include_router(api.router)
app.include_router(importer.router)
app.include_router(sharing.router)
app.include_router(backup.router)


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
