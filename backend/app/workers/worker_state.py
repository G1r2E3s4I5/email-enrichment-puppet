"""WorkerState telemetry tracker for Background Worker Engine."""

import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class WorkerState:
    """Telemetry state container tracking worker execution metrics."""

    def __init__(self) -> None:
        """Initialize worker state attributes."""
        self._running: bool = False
        self._current_job: Optional[str] = None
        self._processed_jobs: int = 0
        self._start_time: Optional[float] = None
        self._last_activity: Optional[datetime] = None

    @property
    def running(self) -> bool:
        """Return True if worker loop is currently running."""
        return self._running

    @running.setter
    def running(self, value: bool) -> None:
        """Set running flag and track start time."""
        self._running = value
        if value:
            if self._start_time is None:
                self._start_time = time.perf_counter()
            self.record_activity()
        else:
            self._start_time = None
            self._current_job = None

    @property
    def current_job(self) -> Optional[str]:
        """Return active job UUID string or None."""
        return self._current_job

    @current_job.setter
    def current_job(self, job_id: Optional[str]) -> None:
        """Set current job ID and record activity timestamp."""
        self._current_job = job_id
        self.record_activity()

    @property
    def processed_jobs(self) -> int:
        """Return total completed jobs count."""
        return self._processed_jobs

    @property
    def last_activity(self) -> Optional[str]:
        """Return ISO timestamp of last worker activity."""
        if self._last_activity:
            return self._last_activity.isoformat()
        return None

    def record_activity(self) -> None:
        """Update last activity timestamp to current UTC time."""
        self._last_activity = datetime.now(timezone.utc)

    def increment_processed_jobs(self) -> None:
        """Increment processed jobs counter."""
        self._processed_jobs += 1
        self.record_activity()

    def get_uptime_formatted(self) -> str:
        """Return formatted human-readable uptime string (e.g. '0h 15m 30s')."""
        if not self._running or self._start_time is None:
            return "0s"

        elapsed_sec = int(time.perf_counter() - self._start_time)
        hours = elapsed_sec // 3600
        minutes = (elapsed_sec % 3600) // 60
        seconds = elapsed_sec % 60

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def to_dict(self, queue_size: int = 0) -> Dict[str, Any]:
        """Format state attributes into status response payload dictionary."""
        return {
            "running": self._running,
            "current_job": self._current_job,
            "processed_jobs": self._processed_jobs,
            "queue_size": queue_size,
            "uptime": self.get_uptime_formatted(),
            "last_activity": self.last_activity,
        }
