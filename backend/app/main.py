"""Main application entrypoint for Email Enrichment Tool Backend API."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI

from app.config.constants import APP_NAME, APP_VERSION, APP_DESCRIPTION
from app.config.settings import settings
from app.config.logging import setup_logging, logger
from app.core.middleware import setup_middlewares
from app.api.routes.health import router as health_router
from app.api.routes.domain import router as domain_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.queue import router as queue_router
from app.api.routes.workers import router as worker_router
from app.api.routes.email_pattern_routes import router as email_pattern_router
from app.api.routes.domain_analytics import router as domain_analytics_router
from app.api.routes.email_verification import router as email_verification_router
from app.api.routes.analytics import router as analytics_router, dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager handling application startup and shutdown events."""
    setup_logging(settings.LOG_LEVEL)
    logger.info(f"Starting {APP_NAME} v{APP_VERSION} in [{settings.ENVIRONMENT}] mode.")
    logger.info("Initializing system architecture and registering provider interfaces.")

    from app.workers.worker_manager import WorkerManager
    try:
        wm = WorkerManager.get_instance()
        wm.start_worker()
        logger.info("Auto-started background EnrichmentWorker loop on app startup.")
    except Exception as exc:
        logger.warning(f"Could not auto-start background worker on startup: {str(exc)}")

    yield

    try:
        WorkerManager.get_instance().stop_worker()
    except Exception:
        pass

    logger.info(f"Shutting down {APP_NAME} gracefully.")


def create_application() -> FastAPI:
    """Factory function to build and configure the FastAPI application instance."""
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    setup_middlewares(app)
    app.include_router(health_router)
    app.include_router(domain_router)
    app.include_router(jobs_router)
    app.include_router(queue_router)
    app.include_router(worker_router)
    app.include_router(email_pattern_router)
    app.include_router(domain_analytics_router)
    app.include_router(email_verification_router)
    app.include_router(analytics_router)
    app.include_router(dashboard_router)

    return app


app = create_application()

if __name__ == "__main__":
    import uvicorn
    from app.config.constants import DEFAULT_HOST, DEFAULT_PORT

    uvicorn.run("app.main:app", host=DEFAULT_HOST, port=DEFAULT_PORT, http="h11", reload=True)
