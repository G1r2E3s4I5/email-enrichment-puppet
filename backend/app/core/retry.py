"""Retry and fault tolerance utility supporting exponential backoff, jitter, and transient error handling."""

import asyncio
import random
import time
from typing import Any, Callable, TypeVar

from app.config.logging import logger

T = TypeVar("T")


def execute_with_retry(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    backoff_base: float = 0.5,
    jitter: bool = True,
    transient_exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> T:
    """Synchronous execution wrapper with exponential backoff and jitter."""
    attempt = 0
    while True:
        attempt += 1
        try:
            return func(*args, **kwargs)
        except transient_exceptions as exc:
            if attempt >= max_attempts:
                logger.error(f"Execution failed after {attempt} attempts: {str(exc)}")
                raise
            delay = backoff_base * (2 ** (attempt - 1))
            if jitter:
                delay += random.uniform(0, delay * 0.5)
            logger.warning(f"Attempt {attempt}/{max_attempts} failed ({str(exc)}). Retrying in {round(delay, 2)}s...")
            time.sleep(delay)


async def execute_with_retry_async(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    backoff_base: float = 0.5,
    jitter: bool = True,
    transient_exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> Any:
    """Asynchronous execution wrapper with exponential backoff and jitter."""
    attempt = 0
    while True:
        attempt += 1
        try:
            return await func(*args, **kwargs)
        except transient_exceptions as exc:
            if attempt >= max_attempts:
                logger.error(f"Async execution failed after {attempt} attempts: {str(exc)}")
                raise
            delay = backoff_base * (2 ** (attempt - 1))
            if jitter:
                delay += random.uniform(0, delay * 0.5)
            logger.warning(f"Async attempt {attempt}/{max_attempts} failed ({str(exc)}). Retrying in {round(delay, 2)}s...")
            await asyncio.sleep(delay)
