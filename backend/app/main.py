"""
Integris Clinical Platform — FastAPI application entry point.

Startup sequence
----------------
1. Validate / auto-generate JWT keys.
2. Register SQLAlchemy audit-log event listeners.
3. Create local storage directories.
4. Mount API router.
5. Expose /health endpoint.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import v1_router
from app.config import get_settings
from app.core.audit import register_audit_listeners
from app.core.security import get_private_key_pem  # triggers key generation / validation

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    # 1. Ensure JWT keys are available (auto-generates for dev if missing)
    get_private_key_pem()

    # 2. Register SQLAlchemy audit-trail event listeners
    from app.database import SessionLocal
    register_audit_listeners(SessionLocal)

    # 3. Ensure local storage directories exist
    if settings.STORAGE_BACKEND == "local":
        from pathlib import Path
        Path(settings.STORAGE_LOCAL_PATH).mkdir(parents=True, exist_ok=True)

    yield
    # ── Shutdown ───────────────────────────────────────────────────────────
    # (nothing to clean up for now)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# ── CORS ───────────────────────────────────────────────────────────────────
_origins = list(settings.ALLOWED_ORIGINS)
if settings.LANDING_ORIGIN:
    _origins.append(settings.LANDING_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────────────
app.include_router(v1_router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok", "version": settings.APP_VERSION}
