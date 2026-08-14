"""Security and authentication primitives placeholder."""

from typing import Optional
from fastapi import Header


async def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> Optional[str]:
    """Verify optional API Key header for restricted endpoints."""
    return x_api_key
