"""Kiểm tra endpoint /check-conflict phải FAIL-CLOSED.

Trước đây endpoint nuốt mọi exception và trả HTTP 200 kèm has_conflict=False.
Client không phân biệt được "đã kiểm tra, không trùng" với "chưa kiểm tra được"
nên vẫn tạo ra sự kiện trùng. Các test dưới đây khoá lại hành vi đúng.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app as app_module
from app import app
from check_conflict import traditional_conflict_check


client = TestClient(app)


def auth_headers():
    login = client.post("/auth/login", json={"passcode": "1234"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


PAYLOAD = {
    "teacher": "Teacher A",
    "start": "2026-08-20T08:00:00Z",
    "end": "2026-08-20T09:00:00Z",
}


def test_upstream_failure_returns_error_status_not_no_conflict():
    with patch.object(app_module, "list_events", side_effect=RuntimeError("Google down")):
        response = client.post("/check-conflict", json=PAYLOAD, headers=auth_headers())

    assert response.status_code == 502
    assert "has_conflict" not in response.json()


def test_invalid_datetime_is_rejected_instead_of_reported_as_free():
    with patch.object(app_module, "list_events", return_value=[]):
        response = client.post(
            "/check-conflict",
            json={**PAYLOAD, "start": "not-a-datetime"},
            headers=auth_headers(),
        )

    assert response.status_code == 400
    assert "has_conflict" not in response.json()


def test_overlapping_event_for_same_teacher_is_reported():
    existing = [{
        "id": "event-1",
        "summary": "Class A - Teacher A - Program A",
        "start": {"dateTime": "2026-08-20T08:30:00Z"},
        "end": {"dateTime": "2026-08-20T09:30:00Z"},
    }]
    with patch.object(app_module, "list_events", return_value=existing):
        response = client.post("/check-conflict", json=PAYLOAD, headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["has_conflict"] is True
    assert body["conflict_count"] == 1


def test_event_being_edited_is_excluded_from_its_own_conflicts():
    existing = [{
        "id": "event-1",
        "summary": "Class A - Teacher A - Program A",
        "start": {"dateTime": "2026-08-20T08:00:00Z"},
        "end": {"dateTime": "2026-08-20T09:00:00Z"},
    }]
    with patch.object(app_module, "list_events", return_value=existing):
        response = client.post(
            "/check-conflict",
            json={**PAYLOAD, "exclude_event_id": "event-1"},
            headers=auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["has_conflict"] is False


def test_recurring_series_reports_a_conflict_on_a_later_occurrence():
    """Buổi đầu trống nhưng buổi thứ 3 trùng — lỗi cũ sẽ bỏ lọt hoàn toàn."""
    existing = [{
        "id": "other-1",
        "summary": "Other - Teacher A - Program X",
        "description": "Teacher: Teacher A",
        "start": {"dateTime": "2026-08-22T08:30:00Z"},
        "end": {"dateTime": "2026-08-22T09:30:00Z"},
    }]
    payload = {**PAYLOAD, "recurrence": "DAILY", "repeat_count": 3}

    with patch.object(app_module, "list_events", return_value=existing):
        response = client.post("/check-conflict", json=payload, headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["checked_occurrences"] == 3
    assert body["has_conflict"] is True
    assert body["conflicts"][0]["occurrence_start"].startswith("2026-08-22")


def test_long_series_loads_more_than_one_calendar_window():
    payload = {**PAYLOAD, "recurrence": "WEEKLY", "repeat_count": 40, "byday": ["MO"]}

    with patch.object(app_module, "list_events", return_value=[]) as list_events:
        response = client.post("/check-conflict", json=payload, headers=auth_headers())

    assert response.status_code == 200
    # ~40 tuần vượt trần cửa sổ 120 ngày → phải nạp lịch nhiều lần, nếu không các buổi
    # cuối chuỗi sẽ không có dữ liệu để đối chiếu.
    assert list_events.call_count > 1
    # 40 buổi thứ Hai + buổi gốc (PAYLOAD bắt đầu vào thứ Năm, không khớp BYDAY nhưng
    # vẫn luôn được kiểm tra để không bỏ sót xung đột).
    assert response.json()["checked_occurrences"] == 41


def test_repeat_count_zero_is_rejected_instead_of_looping_forever():
    """repeat_count=0 làm build_recurrence_rule bỏ COUNT → luật lặp vô hạn."""
    payload = {**PAYLOAD, "recurrence": "DAILY", "repeat_count": 0}

    with patch.object(app_module, "list_events", return_value=[]):
        response = client.post("/check-conflict", json=payload, headers=auth_headers())

    assert response.status_code == 422


def test_null_recurrence_is_rejected():
    payload = {**PAYLOAD, "recurrence": None}

    with patch.object(app_module, "list_events", return_value=[]):
        response = client.post("/check-conflict", json=payload, headers=auth_headers())

    assert response.status_code == 422


def test_traditional_check_raises_on_bad_datetime():
    with pytest.raises(ValueError):
        traditional_conflict_check(
            existing_classes=[],
            teacher="Teacher A",
            new_start="not-a-datetime",
            new_end="2026-08-20T09:00:00Z",
        )
