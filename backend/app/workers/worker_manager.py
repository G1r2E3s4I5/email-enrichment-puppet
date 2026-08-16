"""WorkerManager orchestrating EnrichmentWorker lifecycle, starting, stopping, and status telemetry."""

import asyncio
from typing import Optional

from app.config.logging import logger
from app.schemas.worker import (
    WorkerStartResponse,
    WorkerStatusResponse,
    WorkerStopResponse,
)
from app.services.redis_queue_service import RedisQueueService
from app.workers.enrichment_worker import EnrichmentWorker


class WorkerManager:
    """Manager singleton controlling background enrichment worker task creation and lifecycle management."""

    _instance: Optional["WorkerManager"] = None

    def __init__(
        self,
        worker: Optional[EnrichmentWorker] = None,
        redis_queue_service: Optional[RedisQueueService] = None,
    ) -> None:
        """Initialize WorkerManager with background worker and Redis queue service."""
        self._worker = worker or EnrichmentWorker()
        self._redis_queue_service = redis_queue_service or RedisQueueService()
        self._task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(
        cls,
        worker: Optional[EnrichmentWorker] = None,
        redis_queue_service: Optional[RedisQueueService] = None,
    ) -> "WorkerManager":
        """Get or initialize singleton WorkerManager instance."""
        if cls._instance is None:
            cls._instance = cls(worker=worker, redis_queue_service=redis_queue_service)
        return cls._instance

    @property
    def worker(self) -> EnrichmentWorker:
        """Access underlying EnrichmentWorker instance."""
        return self._worker

    def get_queue_size(self) -> int:
        """Retrieve current pending Redis queue size."""
        try:
            return self._redis_queue_service.get_queue_size()
        except Exception:
            return 0

    def get_status(self) -> WorkerStatusResponse:
        """Return real-time worker status snapshot formatted per schema requirements."""
        q_size = self.get_queue_size()
        state_dict = self._worker.state.to_dict(queue_size=q_size)

        return WorkerStatusResponse(
            running=state_dict["running"],
            current_job=state_dict["current_job"],
            processed_jobs=state_dict["processed_jobs"],
            queue_size=q_size,
            uptime=state_dict["uptime"],
            last_activity=state_dict["last_activity"],
        )

    def start_worker(self) -> WorkerStartResponse:
        """Launch background worker execution loop in an asyncio task."""
        if self._worker.state.running or (self._task and not self._task.done()):
            logger.info("Worker start requested, but worker is already running.")
            return WorkerStartResponse(
                success=True,
                message="Background worker is already running",
                status=self.get_status(),
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

        # Reset worker state for fresh execution
        self._worker.reset()

        self._task = loop.create_task(self._worker.run_loop())

        def _handle_task_completion(task: asyncio.Task) -> None:
            try:
                task.result()
            except asyncio.CancelledError:
                logger.info("EnrichmentWorker asyncio task cancelled.")
            except Exception as exc:
                logger.critical(
                    f"CRITICAL: EnrichmentWorker task crashed with unhandled exception: {str(exc)}",
                    exc_info=True,
                )

        self._task.add_done_callback(_handle_task_completion)
        logger.info("EnrichmentWorker asyncio task launched on active event loop.")

        return WorkerStartResponse(
            success=True,
            message="Background worker started successfully",
            status=self.get_status(),
        )

    def stop_worker(self) -> WorkerStopResponse:
        """Signal background worker to gracefully stop."""
        if not self._worker.state.running:
            logger.info("Worker stop requested, but worker is not running.")
            return WorkerStopResponse(
                success=True,
                message="Background worker is not running",
                status=self.get_status(),
            )

        self._worker.stop()
        if self._task and not self._task.done():
            self._task.cancel()

        logger.info("EnrichmentWorker stop signal sent successfully.")
        return WorkerStopResponse(
            success=True,
            message="Background worker stop signal sent successfully",
            status=self.get_status(),
        )
