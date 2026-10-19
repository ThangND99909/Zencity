"""API cho service khác (ZenGuide AI Dashboard) gọi vào bằng X-API-Key.

Hai phần được khoá lại ở đây:
  - X-API-Key chỉ mở đúng các route trong SERVICE_API_ROUTES — không sửa/xoá được lịch;
  - POST /classes/preview chạy thử đúng quy tắc CHẴN/LẺ như lúc tạo thật và không ghi
    gì lên Google.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app as app_module
import auth
from app import app
from fake_calendar import CALENDAR_EVEN, CALENDAR_ODD, FakeCalendarService, load_calendar_crud
from recurrence_helper import build_recurrence_rule


client = TestClient(app)

SERVICE_KEY = "test-service-key-0123456789abcdefghijklmnop"
CAL_OF = {'even': CALENDAR_EVEN, 'odd': CALENDAR_ODD}

# 18:00 Chicago thứ Năm 15/10/2026 = 06:00 VN 16/10 (CHẴN). Mỹ hết giờ mùa hè CN 01/11:
# từ đó 18:00 Chicago = 07:00 VN (LẺ).
CLASS = {
    "name": "Grammar & Phonics",
    "classname": "Room 4B",
    "teacher": "Teacher A",
    "zoom_link": "https://zoom.us/j/123",
    "program": "ASVN",
    "start": "2026-10-15T18:00:00",
    "end": "2026-10-15T19:00:00",
    "timezone": "America/Chicago",
}
WEEKLY_8_WEEKS = {**CLASS, "recurrence": "WEEKLY", "byday": ["TU", "TH"], "repeat_count": 16}


@pytest.fixture
def service_key(monkeypatch):
    monkeypatch.setattr(auth, "SERVICE_API_KEY", SERVICE_KEY)
    return {"X-API-Key": SERVICE_KEY}


# ==========================================================================
# X-API-Key
# ==========================================================================

def test_service_key_opens_allowed_route(service_key):
    response = client.get("/timezones", headers=service_key)
    assert response.status_code == 200


def test_wrong_service_key_is_rejected(service_key):
    response = client.get("/timezones", headers={"X-API-Key": SERVICE_KEY + "x"})
    assert response.status_code == 401


def test_any_key_is_rejected_when_service_key_is_not_configured(monkeypatch):
    monkeypatch.setattr(auth, "SERVICE_API_KEY", "")
    response = client.get("/timezones", headers={"X-API-Key": ""})
    assert response.status_code == 401


@pytest.mark.parametrize("method, path", [
    ("GET", "/classes"),
    ("GET", "/classes/event-1"),
    ("PUT", "/classes/event-1"),
    ("DELETE", "/classes/event-1"),
    ("POST", "/programs"),
    ("DELETE", "/programs/p1"),
    ("GET", "/ai/suggest"),
])
def test_service_key_cannot_reach_other_routes(service_key, method, path):
    with patch.object(app_module, "delete_event", side_effect=AssertionError("must not run")), \
            patch.object(app_module, "update_event", side_effect=AssertionError("must not run")):
        response = client.request(method, path, headers=service_key, json=CLASS)
    assert response.status_code == 403


def test_bad_service_key_does_not_fall_back_to_bearer_session(service_key):
    login = client.post("/auth/login", json={"passcode": "1234"})
    token = login.json()["access_token"]
    response = client.get(
        "/timezones",
        headers={"X-API-Key": "wrong", "Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_short_service_key_is_rejected_at_startup(monkeypatch):
    import importlib

    monkeypatch.setenv("SERVICE_API_KEY", "too-short")
    with pytest.raises(RuntimeError, match="SERVICE_API_KEY"):
        importlib.reload(auth)
    monkeypatch.delenv("SERVICE_API_KEY")
    importlib.reload(auth)


# ==========================================================================
# POST /classes/preview
# ==========================================================================

def test_preview_single_event_reports_calendar_and_vietnam_time(service_key):
    with patch.object(app_module, "list_events", return_value=[]), \
            patch.object(app_module, "create_event", side_effect=AssertionError("must not write")):
        response = client.post("/classes/preview", json=CLASS, headers=service_key)

    assert response.status_code == 200
    body = response.json()
    assert body["occurrence_count"] == 1
    assert body["timezone"] == "America/Chicago"
    [segment] = body["segments"]
    assert segment["calendar"] == "even"
    assert segment["first_start"]["local"] == "2026-10-15T18:00:00-05:00"
    assert segment["first_start"]["vietnam"] == "2026-10-16T06:00:00+07:00"
    assert body["conflict"]["has_conflict"] is False


def test_preview_splits_series_at_us_dst_change(service_key):
    with patch.object(app_module, "list_events", return_value=[]):
        response = client.post("/classes/preview", json=WEEKLY_8_WEEKS, headers=service_key)

    assert response.status_code == 200
    body = response.json()
    assert body["occurrence_count"] == 16
    assert [(s["calendar"], s["occurrence_count"]) for s in body["segments"]] == [
        ("even", 5),  # 15, 20, 22, 27, 29/10
        ("odd", 11),
    ]
    assert body["segments"][1]["first_start"]["vietnam"] == "2026-11-04T07:00:00+07:00"


def test_preview_reports_teacher_conflict(service_key):
    existing = [{
        "id": "event-1",
        "summary": "Other class - Teacher A - Program A",
        "start": {"dateTime": "2026-10-15T23:30:00Z"},
        "end": {"dateTime": "2026-10-16T00:30:00Z"},
    }]
    with patch.object(app_module, "list_events", return_value=existing):
        response = client.post("/classes/preview", json=CLASS, headers=service_key)

    assert response.status_code == 200
    conflict = response.json()["conflict"]
    assert conflict["has_conflict"] is True
    assert conflict["conflict_count"] == 1


def test_preview_rejects_end_before_start(service_key):
    payload = {**CLASS, "end": "2026-10-15T17:00:00"}
    with patch.object(app_module, "list_events", return_value=[]):
        response = client.post("/classes/preview", json=payload, headers=service_key)
    assert response.status_code == 400


def test_preview_fails_closed_when_calendar_is_unreachable(service_key):
    with patch.object(app_module, "list_events", side_effect=RuntimeError("Google down")):
        response = client.post("/classes/preview", json=CLASS, headers=service_key)
    assert response.status_code == 500
    assert "conflict" not in response.json()


# ==========================================================================
# preview_event phải khớp đúng với create_event
# ==========================================================================

@pytest.mark.parametrize("payload", [CLASS, WEEKLY_8_WEEKS], ids=["single", "weekly-across-dst"])
def test_preview_matches_calendars_used_by_create(tmp_path, payload):
    service = FakeCalendarService()
    crud = load_calendar_crud(service, tmp_path / "classes_extra.json")

    data = dict(payload)
    rule = build_recurrence_rule(data)
    data["rrule"] = [rule] if rule else None

    preview = crud.preview_event(data)
    assert service.total_events() == 0

    crud.create_event(data)
    created = sorted(
        (calendar_id, event["start"]["dateTime"])
        for calendar_id, events in service.store.items()
        for event in events.values()
        if not event.get("recurringEventId")  # bỏ các instance sinh từ chuỗi lặp
    )
    planned = sorted(
        (CAL_OF[segment["calendar"]], segment["first_start"]["local"])
        for segment in preview["segments"]
    )
    assert created == planned
