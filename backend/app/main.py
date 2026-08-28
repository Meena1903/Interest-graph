"""
main.py
=======
FastAPI application entry point.

Initializes routes, configures CORS, handles DB tables creation on startup,
and loads seed data in debug mode.
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import feed, graph, interactions, metrics, posts, recommendations, users
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.db.database import init_db
from app.db.seed import seed_database
from app.services.interest_engine import build_graph
from app.db.database import get_db_context

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events manager (app startup/shutdown)."""
    logger.info("[Lifespan] Starting application initialization sequence")
    
    # 1. Initialize SQLite Database Schema
    await init_db()
    
    # 2. Seed database with POC dataset
    if settings.DEBUG:
        logger.info("[Lifespan] DEBUG mode is ON — running seed_database()")
        await seed_database()
        
    # 3. Build initial in-memory Interest Graph
    async with get_db_context() as session:
        await build_graph(session)
        
    logger.info("[Lifespan] Startup initialization complete. Ready to serve requests.")
    yield
    logger.info("[Lifespan] Application shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
    debug=settings.DEBUG
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("[CORS] Middleware added | allowed_origins=%s", settings.cors_origins_list)

# Include API Routers
app.include_router(users.router, prefix="/api")
app.include_router(posts.router, prefix="/api")
app.include_router(interactions.router, prefix="/api")
app.include_router(feed.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")

logger.info("[API] All routes successfully mounted.")


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple status check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "debug_mode": settings.DEBUG
    }


if __name__ == "__main__":
    logger.info("[Main] Launching server via uvicorn")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
