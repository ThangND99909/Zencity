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
from collections import deque


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

# Khoá cho service khác (ZenGuide AI Dashboard) gọi API qua header X-API-Key.
# Để trống = tắt hẳn đường xác thực này. Khoá CHỈ mở được SERVICE_API_ROUTES:
# đọc/tạo/sửa/xoá lớp như form Smart Calendar và đọc danh sách programs; KHÔNG
# tạo/sửa/xoá được programs hay các route quản trị khác.
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "").strip()
SERVICE_API_KEY_MIN_LENGTH = 32

if SERVICE_API_KEY and len(SERVICE_API_KEY) < SERVICE_API_KEY_MIN_LENGTH:
    raise RuntimeError(
        f"SERVICE_API_KEY must be at least {SERVICE_API_KEY_MIN_LENGTH} characters"
    )

# "{...}" khớp đúng MỘT đoạn path, vd "/classes/{event_id}" khớp "/classes/abc_20261110T000000Z".
SERVICE_API_ROUTES = frozenset({
    ("GET", "/classes"),
    ("GET", "/programs"),
    ("GET", "/timezones"),
    ("POST", "/check-conflict"),
    ("POST", "/classes/preview"),
    ("POST", "/classes"),
    # Chatbot ZenGuide kiểm tra, sửa và xoá lớp (luôn có bước xác nhận của người dùng).
    ("GET", "/classes/{event_id}"),
    ("PUT", "/classes/{event_id}"),
    ("DELETE", "/classes/{event_id}"),
})

# Số lớp proxy tin cậy đứng trước ứng dụng (Render/Cloudflare/nginx...).
# 0 = không có proxy ⇒ BỎ QUA hoàn toàn header X-Forwarded-For.
TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "0"))

_attempts: dict[str, deque[float]] = {}
_attempts_lock = threading.Lock()
MAX_ATTEMPTS = 5
ATTEMPT_WINDOW_SECONDS = 5 * 60

# Chặn trên tổng số lần sai trong cùng cửa sổ, tính trên MỌI client. Đây là lưới an toàn
# cho trường hợp kẻ tấn công có nhiều IP thật (botnet) nên giới hạn theo IP không đủ.
# Ngưỡng để cao vì nó đánh đổi: khi bị tấn công thì quản trị viên cũng bị chặn theo.
GLOBAL_MAX_ATTEMPTS = int(os.getenv("ADMIN_GLOBAL_MAX_ATTEMPTS", "100"))
_global_attempts: deque[float] = deque()

# Trần số client được theo dõi. X-Forwarded-For do client gửi nên nếu không chặn,
# kẻ tấn công chỉ cần đổi header mỗi request là làm dict phình vô hạn.
MAX_TRACKED_CLIENTS = 4096


def resolve_client_key(forwarded_for: str, peer_ip: str) -> str:
    """Xác định IP client dùng làm khoá giới hạn tần suất.

    ⚠️ X-Forwarded-For do CLIENT gửi lên và giả mạo được tuỳ ý. Chỉ những phần do proxy
    của chính mình ghi vào là đáng tin, và chúng luôn nằm ở CUỐI chuỗi — nên phải đếm
    từ phải sang đúng số lớp proxy đã khai báo.

    Code cũ lấy phần tử ĐẦU TIÊN, tức đúng phần kẻ tấn công tự khai, nên chỉ cần đổi
    header mỗi request là vô hiệu hoàn toàn cơ chế chặn dò passcode.
    """
    peer_ip = (peer_ip or "").strip() or "unknown"
    if TRUSTED_PROXY_COUNT <= 0:
        return peer_ip

    parts = [part.strip() for part in (forwarded_for or "").split(",") if part.strip()]
    # Chuỗi ngắn hơn số proxy đã khai ⇒ header không đáng tin, dùng IP kết nối trực tiếp.
    if len(parts) < TRUSTED_PROXY_COUNT:
        return peer_ip
    return parts[-TRUSTED_PROXY_COUNT]


def _prune_attempts_locked(now: float) -> None:
    """Dọn các bản ghi đã hết hạn và chặn trần bộ nhớ. Phải gọi khi ĐANG giữ khoá."""
    cutoff = now - ATTEMPT_WINDOW_SECONDS

    while _global_attempts and _global_attempts[0] < cutoff:
        _global_attempts.popleft()

    for key in [k for k, v in _attempts.items() if not v or v[-1] < cutoff]:
        _attempts.pop(key, None)

    if len(_attempts) > MAX_TRACKED_CLIENTS:
        oldest_first = sorted(_attempts.items(), key=lambda item: item[1][-1])
        for key, _ in oldest_first[:len(_attempts) - MAX_TRACKED_CLIENTS]:
            _attempts.pop(key, None)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def is_rate_limited(client_key: str) -> bool:
    now = time.time()
    with _attempts_lock:
        _prune_attempts_locked(now)

        if len(_global_attempts) >= GLOBAL_MAX_ATTEMPTS:
            return True

        # .get() chứ không phải _attempts[key]: dict thường + get() không tạo bản ghi
        # cho mỗi khoá được tra. Trước đây đây là defaultdict nên chỉ cần dò thử là
        # sinh entry mới, và entry không bao giờ được dọn.
        attempts = _attempts.get(client_key)
        if not attempts:
            return False
        while attempts and attempts[0] < now - ATTEMPT_WINDOW_SECONDS:
            attempts.popleft()
        return len(attempts) >= MAX_ATTEMPTS


def record_failed_attempt(client_key: str) -> None:
    now = time.time()
    with _attempts_lock:
        _attempts.setdefault(client_key, deque()).append(now)
        _global_attempts.append(now)
        # Dọn SAU khi ghi để trần MAX_TRACKED_CLIENTS luôn đúng; dọn trước rồi mới thêm
        # sẽ để số bản ghi vượt trần đúng 1 đơn vị.
        _prune_attempts_locked(now)


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


def verify_service_api_key(api_key: str) -> bool:
    return bool(SERVICE_API_KEY) and hmac.compare_digest(
        (api_key or "").encode(), SERVICE_API_KEY.encode()
    )


def _path_matches(template: str, path: str) -> bool:
    template_parts, path_parts = template.split("/"), path.split("/")
    return len(template_parts) == len(path_parts) and all(
        expected == actual or (expected.startswith("{") and expected.endswith("}") and actual != "")
        for expected, actual in zip(template_parts, path_parts)
    )


def is_service_api_route(method: str, path: str) -> bool:
    method, path = method.upper(), path.rstrip("/") or "/"
    return any(
        route_method == method and _path_matches(route_path, path)
        for route_method, route_path in SERVICE_API_ROUTES
    )
