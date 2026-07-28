"""
Security middleware and validation for ChatSI CRM.

Features:
- Rate limiting per IP
- Text message length validation
- Voice message duration validation
- CORS configuration
- Request size limits
"""

import time
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

from fastapi import Request, HTTPException, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────

ALLOWED_ORIGINS = [
    "https://assistants.jo3.org",
    "https://assistants.jo3.org/crm",
    "http://localhost:5173",  # Dev
    "http://localhost:3000",  # Dev
]

# Rate limiting: {ip: [timestamps]}
_rate_limit_store: dict[str, list[float]] = defaultdict(list)

# Rate limit settings
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 100  # per window
RATE_LIMIT_WEBHOOK_MAX = 30  # per window for webhooks

# Message limits
MAX_TEXT_LENGTH = 200
MAX_VOICE_DURATION_SECONDS = 40
MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


# ─── Rate Limiter ────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per IP."""

    def __init__(self, app, max_requests: int = RATE_LIMIT_MAX_REQUESTS, window: int = RATE_LIMIT_WINDOW):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = self._get_client_ip(request)
        now = time.time()

        # Clean old timestamps
        _rate_limit_store[client_ip] = [
            ts for ts in _rate_limit_store[client_ip]
            if now - ts < self.window
        ]

        # Check limit
        if len(_rate_limit_store[client_ip]) >= self.max_requests:
            logger.warning("Rate limit exceeded for IP=%s path=%s", client_ip, request.url.path)
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
            )

        # Record request
        _rate_limit_store[client_ip].append(now)

        response = await call_next(request)

        # Add rate limit headers
        remaining = self.max_requests - len(_rate_limit_store[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(now + self.window))

        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        # Check for forwarded headers (behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"


# ─── Message Validators ──────────────────────────────────────────────

def validate_text_message(text: str) -> str:
    """Validate and truncate text messages to MAX_TEXT_LENGTH."""
    if not text or not text.strip():
        return ""

    text = text.strip()

    if len(text) > MAX_TEXT_LENGTH:
        logger.warning(
            "Text message truncated: length=%d max=%d",
            len(text), MAX_TEXT_LENGTH,
        )
        return text[:MAX_TEXT_LENGTH] + "..."

    return text


def validate_voice_duration(duration_seconds: float | None) -> bool:
    """Check if voice message duration is within limit."""
    if duration_seconds is None:
        return True  # Can't validate without duration

    if duration_seconds > MAX_VOICE_DURATION_SECONDS:
        logger.warning(
            "Voice message rejected: duration=%.1fs max=%ds",
            duration_seconds, MAX_VOICE_DURATION_SECONDS,
        )
        return False

    return True


def validate_audio_size(size_bytes: int) -> bool:
    """Check if audio file size is within limit."""
    if size_bytes > MAX_AUDIO_SIZE_BYTES:
        logger.warning(
            "Audio file rejected: size=%d max=%d",
            size_bytes, MAX_AUDIO_SIZE_BYTES,
        )
        return False
    return True


# ─── Webhook Security ────────────────────────────────────────────────

def verify_webhook_signature(
    payload: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    """Verify webhook signature (HMAC-SHA256)."""
    if not signature or not secret:
        return False

    import hmac
    import hashlib

    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ─── Request Size Limiter ────────────────────────────────────────────

MAX_REQUEST_BODY_SIZE = 5 * 1024 * 1024  # 5MB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")

        if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Request body too large",
            )

        return await call_next(request)
