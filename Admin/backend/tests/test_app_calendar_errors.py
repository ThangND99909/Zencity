import httplib2
import pytest
from fastapi import HTTPException
from googleapiclient.errors import HttpError

import app


def test_get_classes_hides_google_calendar_details(monkeypatch):
    response = httplib2.Response({"status": "404", "reason": "Not Found"})
    upstream_error = HttpError(
        response,
        b'{"error":{"message":"Not Found"}}',
        uri="https://www.googleapis.com/calendar/v3/calendars/private-calendar-id",
    )

    def raise_upstream_error(*_args, **_kwargs):
        raise upstream_error

    monkeypatch.setattr(app, "list_events", raise_upstream_error)

    with pytest.raises(HTTPException) as captured:
        app.get_classes()

    error = captured.value
    rendered_detail = str(error.detail)
    assert error.status_code == 503
    assert error.detail["code"] == "CALENDAR_NOT_ACCESSIBLE"
    assert "googleapis.com" not in rendered_detail
    assert "private-calendar-id" not in rendered_detail


def test_conflict_check_hides_google_calendar_details(monkeypatch):
    response = httplib2.Response({"status": "404", "reason": "Not Found"})
    upstream_error = HttpError(
        response,
        b'{"error":{"message":"Not Found"}}',
        uri="https://www.googleapis.com/calendar/v3/calendars/private-calendar-id/events",
    )

    def raise_upstream_error(*_args, **_kwargs):
        raise upstream_error

    monkeypatch.setattr(app, "list_events", raise_upstream_error)
    request = app.ConflictCheckRequest(
        teacher="Teacher A",
        start="2026-08-17T09:00:00+07:00",
        end="2026-08-17T10:00:00+07:00",
    )

    with pytest.raises(HTTPException) as captured:
        app.api_check_conflict(request)

    error = captured.value
    rendered_detail = str(error.detail)
    assert error.status_code == 503
    assert error.detail["code"] == "CALENDAR_NOT_ACCESSIBLE"
    assert "googleapis.com" not in rendered_detail
    assert "private-calendar-id" not in rendered_detail
