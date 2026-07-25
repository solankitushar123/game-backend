"""
ArenaForge backend — FastAPI application entrypoint.
"""
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api import auth, wallet, games, tournaments, admin
from app.db_init import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ArenaForge API",
    version="0.1.0",
    description="Skill-based e-sports tournament platform — backend API",
)


@app.on_event("startup")
def on_startup():
    # Creates tables + seeds the game catalog if they don't already exist.
    # Runs every boot; safe/idempotent since init_db() checks for existing rows first.
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log the full traceback server-side (visible in Render logs) but never leak
    # internals to the client.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


app.include_router(auth.router)
app.include_router(wallet.router)
app.include_router(games.router)
app.include_router(tournaments.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}
