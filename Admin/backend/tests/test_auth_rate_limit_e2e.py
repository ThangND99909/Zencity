"""E2E cơ chế chặn dò passcode, đi qua đúng endpoint /auth/login.

Lỗi cũ: khoá giới hạn lấy từ phần ĐẦU của X-Forwarded-For — chính là phần client tự
khai — nên chỉ cần đổi header mỗi request là thoát hoàn toàn giới hạn.
"""
import pytest
from fastapi.testclient import TestClient

import auth
from app import app


client = TestClient(app)
WRONG = {"passcode": "0000"}


@pytest.fixture(autouse=True)
def clean_state():
    """resolve_client_key/is_rate_limited đọc biến module lúc gọi nên vá trực tiếp được."""
    auth._attempts.clear()
    auth._global_attempts.clear()
    yield
    auth._attempts.clear()
    auth._global_attempts.clear()


def attempt(xff=None):
    headers = {"x-forwarded-for": xff} if xff is not None else {}
    return client.post("/auth/login", json=WRONG, headers=headers).status_code


def test_spoofed_forwarded_for_cannot_bypass_the_limit(monkeypatch):
    """Chạy sau đúng 1 proxy ⇒ chỉ mục CUỐI là đáng tin, phần client khai bị bỏ qua."""
    monkeypatch.setattr(auth, "TRUSTED_PROXY_COUNT", 1)

    # Kẻ tấn công đổi phần tự khai mỗi lần, nhưng proxy luôn nối IP thật vào cuối.
    codes = [attempt(f"10.0.0.{i}, 203.0.113.7") for i in range(10)]

    assert codes[:auth.MAX_ATTEMPTS] == [401] * auth.MAX_ATTEMPTS
    assert all(code == 429 for code in codes[auth.MAX_ATTEMPTS:]), codes


def test_two_real_clients_behind_the_proxy_are_limited_separately(monkeypatch):
    monkeypatch.setattr(auth, "TRUSTED_PROXY_COUNT", 1)

    for _ in range(auth.MAX_ATTEMPTS):
        assert attempt("203.0.113.7") == 401
    assert attempt("203.0.113.7") == 429
    # Người dùng thật khác không bị vạ lây.
    assert attempt("203.0.113.8") == 401


def test_forwarded_for_is_ignored_when_no_proxy_is_declared(monkeypatch):
    """TRUSTED_PROXY_COUNT=0 ⇒ header bị bỏ qua hoàn toàn, dùng IP kết nối trực tiếp."""
    monkeypatch.setattr(auth, "TRUSTED_PROXY_COUNT", 0)

    codes = [attempt(f"10.0.0.{i}") for i in range(10)]

    assert 429 in codes, "Đổi X-Forwarded-For không được phép cấp thêm hạn mức"


def test_header_shorter_than_declared_proxies_falls_back_to_peer_ip(monkeypatch):
    """Header ngắn hơn số proxy đã khai ⇒ không đáng tin, không được tin dùng."""
    monkeypatch.setattr(auth, "TRUSTED_PROXY_COUNT", 2)

    codes = [attempt(f"10.0.0.{i}") for i in range(10)]

    assert 429 in codes, codes


def test_global_safety_net_stops_a_distributed_attack(monkeypatch):
    """Nhiều IP THẬT khác nhau ⇒ giới hạn theo IP không đủ, cần chặn trên tổng."""
    monkeypatch.setattr(auth, "TRUSTED_PROXY_COUNT", 1)
    monkeypatch.setattr(auth, "GLOBAL_MAX_ATTEMPTS", 12)

    codes = [attempt(f"198.51.100.{i}") for i in range(20)]

    assert codes.count(401) == 12
    assert codes[-1] == 429


def test_attempt_table_stays_bounded(monkeypatch):
    """X-Forwarded-For do client gửi nên nếu không chặn trần, dict phình vô hạn."""
    monkeypatch.setattr(auth, "TRUSTED_PROXY_COUNT", 1)
    monkeypatch.setattr(auth, "GLOBAL_MAX_ATTEMPTS", 10_000)
    monkeypatch.setattr(auth, "MAX_TRACKED_CLIENTS", 64)

    for i in range(2000):
        attempt(f"198.51.100.{i // 256}.{i % 256}")

    assert len(auth._attempts) <= 64


def test_probing_an_unknown_client_key_does_not_allocate(monkeypatch):
    """is_rate_limited từng dùng defaultdict nên chỉ cần TRA là đã sinh bản ghi."""
    monkeypatch.setattr(auth, "TRUSTED_PROXY_COUNT", 1)

    for i in range(500):
        auth.is_rate_limited(f"203.0.113.{i}")

    assert auth._attempts == {}


def test_correct_passcode_clears_the_client_bucket(monkeypatch):
    monkeypatch.setattr(auth, "TRUSTED_PROXY_COUNT", 1)

    for _ in range(auth.MAX_ATTEMPTS - 1):
        assert attempt("203.0.113.9") == 401

    ok = client.post("/auth/login", json={"passcode": "1234"},
                     headers={"x-forwarded-for": "203.0.113.9"})
    assert ok.status_code == 200
    assert attempt("203.0.113.9") == 401  # đã được reset, chưa bị chặn


@pytest.mark.parametrize(
    "proxies,forwarded,peer,expected",
    [
        (0, "1.1.1.1, 2.2.2.2", "9.9.9.9", "9.9.9.9"),   # bỏ qua header
        (1, "1.1.1.1, 2.2.2.2", "9.9.9.9", "2.2.2.2"),   # proxy ghi phần cuối
        (2, "1.1.1.1, 2.2.2.2", "9.9.9.9", "1.1.1.1"),   # đếm từ phải sang
        (1, "", "9.9.9.9", "9.9.9.9"),                   # header rỗng
        (2, "1.1.1.1", "9.9.9.9", "9.9.9.9"),            # ngắn hơn khai báo
        (1, "1.1.1.1, 2.2.2.2", "", "2.2.2.2"),
    ],
)
def test_resolve_client_key(monkeypatch, proxies, forwarded, peer, expected):
    monkeypatch.setattr(auth, "TRUSTED_PROXY_COUNT", proxies)
    assert auth.resolve_client_key(forwarded, peer) == expected
