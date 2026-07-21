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

from app.config import settings
from app.routers import health, webhook, search, whatsapp_webhook, internal_test
from app.services.scheduler import start_scheduler, stop_scheduler


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
app.include_router(internal_test.router)


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
