"""
Phase 1: GET /, GET /api/v1/health.
Phase 2: database layer (not exposed through any route directly).
Phase 3: authentication — /api/v1/auth/register, /login, /me, /logout.
Phase 4: profile (/api/v1/profile) and journal (/api/v1/journal) —
         per-user owned resources, protected by get_current_user and
         (for journal) ensure_owner.

The chatbot, the acne model, and the product/report endpoints are
deliberately NOT included yet — those are later phases, built and
tested separately so each piece is verified before the next depends on
it.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.acne import router as acne_router
from app.api.assessment import router as assessment_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.journal import router as journal_router
from app.api.products import router as products_router
from app.api.profile import router as profile_router
from app.api.recommendations import router as recommendations_router
from app.api.reports import router as reports_router
from app.api.routines import router as routines_router
from app.core.config import get_settings

logger = logging.getLogger("skincare_api")
logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Educational skin-care assistant API. This is an informational "
        "and tracking tool, not a diagnostic or prescribing system."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Centralized error handling: never leak a raw stack trace or
    internal exception message to the client. The real detail still goes
    to the server log for debugging."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "Something went wrong on our side. Please try again.",
        },
    )


@app.get("/", tags=["root"])
def read_root() -> dict:
    """Unversioned root endpoint — just enough to confirm the service is
    up and to point people at the versioned API."""
    return {
        "service": settings.app_name,
        "status": "ok",
        "environment": settings.app_env,
        "api_prefix": settings.api_v1_prefix,
        "docs": "/docs",
    }


@app.get(f"{settings.api_v1_prefix}/health", tags=["health"])
def health_check() -> dict:
    """Liveness check for monitoring / uptime tools and for the frontend
    to confirm the backend is reachable before making real requests."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(profile_router, prefix=settings.api_v1_prefix)
app.include_router(assessment_router, prefix=settings.api_v1_prefix)
app.include_router(journal_router, prefix=settings.api_v1_prefix)
app.include_router(chat_router, prefix=settings.api_v1_prefix)
app.include_router(acne_router, prefix=settings.api_v1_prefix)
app.include_router(products_router, prefix=settings.api_v1_prefix)
app.include_router(routines_router, prefix=settings.api_v1_prefix)
app.include_router(recommendations_router, prefix=settings.api_v1_prefix)
app.include_router(reports_router, prefix=settings.api_v1_prefix)
