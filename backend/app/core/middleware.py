"""Production HTTP Middlewares providing Request Correlation IDs and Response Latency Tracking."""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config.logging import logger


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware attaching X-Correlation-ID header and measuring HTTP request duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process incoming request, attach correlation ID, and record process latency."""
        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start_time = time.perf_counter()

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"[{correlation_id}] Request failed {request.method} {request.url.path} in {duration_ms}ms: {str(exc)}",
                exc_info=True,
            )
            raise exc

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time-MS"] = str(duration_ms)

        return response


def setup_middlewares(app) -> None:
    """Register application HTTP middlewares including CORS and Correlation ID headers."""
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)

