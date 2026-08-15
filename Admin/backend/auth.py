"""Small stateless authentication layer for the admin calendar API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque


IS_PRODUCTION = (
    os.getenv("ENVIRONMENT", "").lower() == "production"
    or os.getenv("RENDER", "").lower() == "true"
)

ADMIN_PASSCODE = os.getenv("ADMIN_PASSCODE", "" if IS_PRODUCTION else "1234")
AUTH_SECRET = os.getenv("ADMIN_AUTH_SECRET", "")
TOKEN_TTL_SECONDS = int(os.getenv("ADMIN_SESSION_TTL_SECONDS", "28800"))

if IS_PRODUCTION and (not ADMIN_PASSCODE or len(AUTH_SECRET) < 32):
    raise RuntimeError(
        "ADMIN_PASSCODE and ADMIN_AUTH_SECRET (at least 32 characters) are required in production"
    )

if not AUTH_SECRET:
    # Development-only secret. It deliberately changes when the process restarts.
    AUTH_SECRET = secrets.token_urlsafe(48)

_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempts_lock = threading.Lock()
MAX_ATTEMPTS = 5
ATTEMPT_WINDOW_SECONDS = 5 * 60


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def is_rate_limited(client_key: str) -> bool:
    now = time.time()
    with _attempts_lock:
        attempts = _attempts[client_key]
        while attempts and attempts[0] < now - ATTEMPT_WINDOW_SECONDS:
            attempts.popleft()
        return len(attempts) >= MAX_ATTEMPTS


def record_failed_attempt(client_key: str) -> None:
    with _attempts_lock:
        _attempts[client_key].append(time.time())


def clear_attempts(client_key: str) -> None:
    with _attempts_lock:
        _attempts.pop(client_key, None)


def verify_passcode(passcode: str) -> bool:
    return bool(ADMIN_PASSCODE) and hmac.compare_digest(passcode, ADMIN_PASSCODE)


def create_access_token() -> tuple[str, int]:
    expires_at = int(time.time()) + TOKEN_TTL_SECONDS
    payload = _b64encode(json.dumps({"exp": expires_at}, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}", expires_at


def validate_access_token(token: str) -> bool:
    try:
        payload, signature = token.split(".", 1)
        expected = _b64encode(
            hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return False
        data = json.loads(_b64decode(payload))
        return int(data.get("exp", 0)) > int(time.time())
    except (ValueError, TypeError, json.JSONDecodeError):
        return False
