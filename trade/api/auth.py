"""API authentication middleware — Bearer token validation."""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests without valid Bearer token (when api_key is configured)."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth if no api_key configured (dev mode)
        if not settings.api_key:
            return await call_next(request)

        # Always allow health check without auth
        if request.url.path.endswith("/health"):
            return await call_next(request)

        # Validate Authorization header
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")

        token = auth[7:]
        if token != settings.api_key:
            raise HTTPException(status_code=403, detail="Invalid API key")

        return await call_next(request)
