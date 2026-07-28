import asyncio
import logging
import os
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from config.app_config import settings
from routers.admin_auth import router as admin_auth_router
from routers.crm_api import router as crm_api_router
from routers.instagram_auth import router as auth_router
from routers.instagram_static import static_router
from routers.instagram_webhook import router as webhook_router
from routers.telegram_webhook import router as telegram_webhook_router
from routers.zernio_webhook import router as zernio_webhook_router
from services.automation import autopost_worker, reminder_worker
from services.security import (
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    ALLOWED_ORIGINS,
)
from services.telegram_bot import start_bot, stop_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


MIGRATIONS_DIR = os.getenv(
    "PYWAY_DATABASE_MIGRATION_DIR",
    str(Path(__file__).resolve().parents[1] / "infra" / "flyway" / "sql"),
)


def run_pyway_migrations() -> None:
    env = os.environ.copy()

    env["PYWAY_TYPE"] = "postgres"
    env["PYWAY_DATABASE_HOST"] = settings.pyway_database_host
    env["PYWAY_DATABASE_PORT"] = settings.pyway_database_port
    env["PYWAY_DATABASE_NAME"] = settings.pyway_database_name
    env["PYWAY_DATABASE_USERNAME"] = settings.pyway_database_username
    env["PYWAY_DATABASE_PASSWORD"] = settings.pyway_database_password
    env["PYWAY_DATABASE_MIGRATION_DIR"] = str(MIGRATIONS_DIR)
    env["PYWAY_TABLE"] = "pyway_schema_history"

    result = subprocess.run(
        ["pyway", "migrate"],
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error("Pyway stdout:\n%s", result.stdout)
        logger.error("Pyway stderr:\n%s", result.stderr)
        raise RuntimeError("Pyway migration failed")

    logger.info("Pyway migrations completed:\n%s", result.stdout)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup started")

    # subprocess.run блокирующий, поэтому выносим в отдельный thread.
    await asyncio.to_thread(run_pyway_migrations)

    telegram_application = await start_bot()
    app.state.telegram_application = telegram_application
    reminder_stop_event = asyncio.Event()
    reminder_task = asyncio.create_task(reminder_worker(stop_event=reminder_stop_event))
    app.state.client_reminder_task = reminder_task
    autopost_stop_event = asyncio.Event()
    autopost_task = asyncio.create_task(autopost_worker(stop_event=autopost_stop_event))
    app.state.autopost_task = autopost_task

    try:
        yield

    finally:
        reminder_stop_event.set()
        autopost_stop_event.set()
        await reminder_task
        await autopost_task
        await stop_bot(telegram_application)
        logger.info("Application shutdown completed")


app = FastAPI(
    title="ChatSI — AI CRM",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ─── Security Middleware ─────────────────────────────────────────────

# 1. Request size limit (must be first)
app.add_middleware(RequestSizeLimitMiddleware)

# 2. Rate limiting
app.add_middleware(RateLimitMiddleware, max_requests=100, window=60)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


app.include_router(admin_auth_router)
app.include_router(crm_api_router)
app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(telegram_webhook_router)
app.include_router(zernio_webhook_router)
app.include_router(static_router)

# ─── CORS ────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "ai-crm-bot" / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

if FRONTEND_ASSETS.exists():
    app.mount("/crm/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="crm-assets")


@app.get("/crm", response_class=HTMLResponse)

@app.get("/crm/{path:path}", response_class=HTMLResponse)
async def crm_frontend(path: str = ""):
    if not FRONTEND_INDEX.exists():
        return HTMLResponse(
            "<h1>CRM frontend is not built</h1><p>Run <code>npm run build</code> in ai-crm-bot/frontend.</p>",
            status_code=503,
        )
    return FileResponse(FRONTEND_INDEX)
