"""Lucho — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import health, webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup
    yield
    # Shutdown
    # (close DB connections, etc.)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Routers
app.include_router(health.router)
app.include_router(webhook.router)


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
