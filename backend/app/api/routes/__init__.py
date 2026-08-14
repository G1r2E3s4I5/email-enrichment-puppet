"""API Router Package."""

from app.api.routes.health import router as health_router
from app.api.routes.domain import router as domain_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.queue import router as queue_router
from app.api.routes.workers import router as worker_router
from app.api.routes.email_pattern_routes import router as email_pattern_router

__all__ = [
    "health_router",
    "domain_router",
    "jobs_router",
    "queue_router",
    "worker_router",
    "email_pattern_router",
]
