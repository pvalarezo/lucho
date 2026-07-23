"""Lucho — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Configure root logger so all application logs appear in journald/stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from app.config import settings  # noqa: E402
from app.routers import health, webhook, search, whatsapp_webhook, payphone_webhook, deuna_webhook  # noqa: E402
from app.services.scheduler import start_scheduler, stop_scheduler  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Routers
app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(search.router)
app.include_router(whatsapp_webhook.router)
app.include_router(payphone_webhook.router)
app.include_router(deuna_webhook.router)

# Internal test endpoints — only in DEBUG mode
if settings.DEBUG:
    from app.routers import internal_test
    app.include_router(internal_test.router)


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
