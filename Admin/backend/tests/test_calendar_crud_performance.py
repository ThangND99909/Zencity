import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError


def _load_calendar_crud():
    """Import calendar_crud without credentials or real Google network calls."""
    fake_google = ModuleType("google_calendar")
    fake_google.calendar_service = MagicMock(name="calendar_service")
    fake_google.CALENDARS = {"odd": "calendar-odd", "even": "calendar-even"}
    fake_google.create_calendar_http = MagicMock(return_value=object())
    module_path = Path(__file__).resolve().parents[1] / "calendar_crud.py"
    spec = importlib.util.spec_from_file_location("calendar_crud_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    original_google = sys.modules.get("google_calendar")
    sys.modules["google_calendar"] = fake_google
    try:
        spec.loader.exec_module(module)
    finally:
        if original_google is None:
            sys.modules.pop("google_calendar", None)
        else:
            sys.modules["google_calendar"] = original_google
    return module


CRUD = _load_calendar_crud()


class CalendarLookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crud = CRUD

    def setUp(self):
        self.service = self.crud.calendar_service
        self.service.reset_mock()
        events = self.service.events.return_value
        for method_name in ("get", "update", "patch", "insert", "delete", "instances"):
            method = getattr(events, method_name)
            method.side_effect = None
            method.return_value = MagicMock()
        self.service.new_batch_http_request.side_effect = None
        self.service.new_batch_http_request.return_value = MagicMock()

    def test_saved_calendar_hint_uses_one_google_get(self):
        request = MagicMock()
        request.execute.return_value = {"id": "event-1"}
        self.service.events.return_value.get.return_value = request

        with patch.object(self.crud, "_saved_calendar_hint", return_value="calendar-even"), \
             patch.object(
                 self.crud,
                 "_resolve_calendar_order",
                 return_value=["calendar-even", "calendar-odd"],
             ):
            order, results = self.crud._probe_event_on_calendars("event-1")

        self.assertEqual(order, ["calendar-even", "calendar-odd"])
        self.assertEqual(results["calendar-even"]["id"], "event-1")
        self.assertEqual(self.service.events.return_value.get.call_count, 1)

    def test_stale_hint_falls_back_after_404(self):
        not_found = HttpError(
            resp=SimpleNamespace(status=404, reason="Not Found"),
            content=b"not found",
        )
        request = MagicMock()
        request.execute.side_effect = [not_found, {"id": "event-1"}]
        self.service.events.return_value.get.return_value = request

        with patch.object(self.crud, "_saved_calendar_hint", return_value="calendar-even"), \
             patch.object(
                 self.crud,
                 "_resolve_calendar_order",
                 return_value=["calendar-even", "calendar-odd"],
             ):
            _, results = self.crud._probe_event_on_calendars("event-1")

        self.assertIsInstance(results["calendar-even"], HttpError)
        self.assertEqual(results["calendar-odd"]["id"], "event-1")
        self.assertEqual(self.service.events.return_value.get.call_count, 2)


class CalendarUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crud = CRUD

    def setUp(self):
        self.service = self.crud.calendar_service
        self.service.reset_mock()
        events = self.service.events.return_value
        for method_name in ("get", "update", "patch", "insert", "delete", "instances"):
            method = getattr(events, method_name)
            method.side_effect = None
            method.return_value = MagicMock()
        self.service.new_batch_http_request.side_effect = None
        self.service.new_batch_http_request.return_value = MagicMock()

    def test_single_update_reuses_event_loaded_during_lookup(self):
        current_event = {
            "id": "event-1",
            "summary": "Old name",
            "start": {"dateTime": "2026-08-13T01:00:00Z", "timeZone": "Asia/Ho_Chi_Minh"},
            "end": {"dateTime": "2026-08-13T02:00:00Z", "timeZone": "Asia/Ho_Chi_Minh"},
        }
        update_request = MagicMock()
        update_request.execute.return_value = {"id": "event-1", "summary": "New name"}
        self.service.events.return_value.update.return_value = update_request
        class_info = {
            "name": "New name",
            "classname": "Class A",
            "teacher": "Teacher A",
            "program": "Program A",
            "zoom_link": "https://zoom.example/test",
            "meeting_id": "123",
            "passcode": "secret",
            "start": "2026-08-13T01:00:00Z",
            "end": "2026-08-13T02:00:00Z",
            "timezone": "Asia/Ho_Chi_Minh",
            "edit_mode": "this",
        }

        with patch.object(
            self.crud,
            "_probe_event_on_calendars",
            return_value=(["calendar-odd", "calendar-even"], {"calendar-odd": current_event}),
        ), patch.object(
            self.crud, "determine_calendar_by_hour", return_value="calendar-odd"
        ), patch.object(self.crud, "update_extra"):
            result = self.crud.update_event("event-1", class_info)

        self.assertEqual(result["summary"], "New name")
        self.service.events.return_value.get.assert_not_called()
        self.service.events.return_value.update.assert_called_once()
        update_kwargs = self.service.events.return_value.update.call_args.kwargs
        self.assertEqual(update_kwargs["sendUpdates"], "all")

    def test_following_update_keeps_naive_local_time_in_selected_timezone(self):
        instance = {
            "id": "master_20260820T080000Z",
            "recurringEventId": "master",
            "start": {"dateTime": "2026-08-20T15:00:00+07:00"},
            "end": {"dateTime": "2026-08-20T16:00:00+07:00"},
        }
        master = {
            "id": "master",
            "summary": "Old series",
            "start": {
                "dateTime": "2026-08-13T15:00:00+07:00",
                "timeZone": "Asia/Ho_Chi_Minh",
            },
            "recurrence": ["RRULE:FREQ=WEEKLY;COUNT=5;BYDAY=TH"],
        }
        master_request = MagicMock()
        master_request.execute.return_value = master
        self.service.events.return_value.get.return_value = master_request
        insert_request = MagicMock()
        insert_request.execute.return_value = {"id": "new-master"}
        self.service.events.return_value.insert.return_value = insert_request
        self.service.events.return_value.update.return_value.execute.return_value = master
        self.service.events.return_value.delete.return_value.execute.return_value = None
        class_info = {
            "name": "Updated series",
            "classname": "Class A",
            "teacher": "Teacher A",
            "program": "Program A",
            "zoom_link": "https://zoom.example/test",
            "meeting_id": "123",
            "passcode": "secret",
            "start": "2026-08-20T15:00:00",
            "end": "2026-08-20T16:00:00",
            "timezone": "Asia/Ho_Chi_Minh",
            "recurrence": "WEEKLY",
            "repeat_count": 3,
            "byday": ["TH"],
        }

        with patch.object(
            self.crud, "determine_calendar_by_hour", return_value="calendar-odd"
        ), patch.object(self.crud, "update_extra"), patch.object(self.crud, "remove_extra"):
            self.crud.update_following_events(
                instance["id"],
                master["id"],
                "calendar-odd",
                class_info,
                current_event=instance,
            )

        inserted_body = self.service.events.return_value.insert.call_args.kwargs["body"]
        self.assertEqual(inserted_body["start"]["dateTime"], "2026-08-20T15:00:00+07:00")
        self.assertEqual(inserted_body["end"]["dateTime"], "2026-08-20T16:00:00+07:00")

    def test_recurring_instance_is_detached_without_redundant_delete(self):
        instance = {
            "id": "master_20260813T010000Z",
            "recurringEventId": "master",
            "start": {"dateTime": "2026-08-13T01:00:00Z"},
        }
        master = {
            "id": "master",
            "summary": "Old",
            "recurrence": ["RRULE:FREQ=DAILY;COUNT=3"],
        }
        get_request = MagicMock()
        get_request.execute.return_value = master
        update_request = MagicMock()
        update_request.execute.return_value = master
        insert_request = MagicMock()
        insert_request.execute.return_value = {"id": "detached-event", "summary": "Changed"}
        self.service.events.return_value.get.return_value = get_request
        self.service.events.return_value.update.return_value = update_request
        self.service.events.return_value.insert.return_value = insert_request
        class_info = {
            "name": "Changed",
            "classname": "Class A",
            "teacher": "Teacher A",
            "program": "Program A",
            "zoom_link": "https://zoom.example/test",
            "meeting_id": "123",
            "passcode": "secret",
            "start": "2026-08-13T01:00:00Z",
            "end": "2026-08-13T02:00:00Z",
            "timezone": "Asia/Ho_Chi_Minh",
        }

        with patch.object(self.crud, "update_extra"):
            result = self.crud.update_this_instance(
                instance["id"],
                "master",
                "calendar-odd",
                class_info,
                current_event=instance,
            )

        self.assertEqual(result["id"], "detached-event")
        self.service.events.return_value.get.assert_called_once()
        self.service.events.return_value.delete.assert_not_called()
        self.service.events.return_value.patch.assert_not_called()
        self.service.events.return_value.update.assert_called_once()
        self.service.events.return_value.insert.assert_called_once()
        self.assertEqual(
            self.service.events.return_value.insert.call_args.kwargs["sendUpdates"],
            "all",
        )

    def test_cancelled_instance_from_old_flow_continues_detached_insert(self):
        instance_id = "master_20260820T080000Z"
        cancelled_instance = {
            "id": instance_id,
            "status": "cancelled",
        }
        master = {
            "id": "master",
            "recurrence": [
                "EXDATE;TZID=Asia/Ho_Chi_Minh:20260820T150000",
                "RRULE:FREQ=DAILY;COUNT=3;INTERVAL=1",
            ],
        }
        get_request = MagicMock()
        get_request.execute.return_value = master
        self.service.events.return_value.get.return_value = get_request
        master_update_request = MagicMock()
        detached_insert_request = MagicMock()
        master_update_request.execute.return_value = master
        detached_insert_request.execute.return_value = {
            "id": "recovered-detached-event",
            "status": "confirmed",
        }
        self.service.events.return_value.update.return_value = master_update_request
        self.service.events.return_value.insert.return_value = detached_insert_request
        class_info = {
            "name": "Recovered",
            "classname": "Class A",
            "teacher": "Teacher A",
            "program": "Program A",
            "zoom_link": "https://zoom.example/test",
            "meeting_id": "123",
            "passcode": "secret",
            "start": "2026-08-20T15:00:00+07:00",
            "end": "2026-08-20T16:00:00+07:00",
            "timezone": "Asia/Ho_Chi_Minh",
        }

        with patch.object(self.crud, "update_extra"):
            result = self.crud.update_this_instance(
                instance_id,
                "master",
                "calendar-odd",
                class_info,
                current_event=cancelled_instance,
            )

        self.assertEqual(result["status"], "confirmed")
        self.service.events.return_value.patch.assert_not_called()
        self.service.events.return_value.update.assert_called_once()
        master_update_body = self.service.events.return_value.update.call_args.kwargs["body"]
        self.assertIn("RRULE:FREQ=DAILY;COUNT=3;INTERVAL=1", master_update_body["recurrence"])
        self.assertIn("EXDATE:20260820T080000Z", master_update_body["recurrence"])
        self.service.events.return_value.insert.assert_called_once()
        self.service.events.return_value.delete.assert_not_called()


class CalendarDeleteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crud = CRUD

    def setUp(self):
        self.service = self.crud.calendar_service
        self.service.reset_mock()
        events = self.service.events.return_value
        for method_name in ("get", "update", "patch", "insert", "delete", "instances"):
            method = getattr(events, method_name)
            method.side_effect = None
            method.return_value = MagicMock()
        self.service.new_batch_http_request.side_effect = None
        self.service.new_batch_http_request.return_value = MagicMock()

    def test_following_instances_are_deleted_in_one_batch(self):
        queued = []
        batch = MagicMock()

        def add(_request, request_id, callback):
            queued.append((request_id, callback))

        def execute(**_kwargs):
            for request_id, callback in queued:
                callback(request_id, None, None)

        batch.add.side_effect = add
        batch.execute.side_effect = execute
        self.service.new_batch_http_request.return_value = batch
        self.service.events.return_value.delete.side_effect = lambda **_kwargs: MagicMock()

        with patch.object(self.crud, "remove_extras") as remove_extras:
            deleted_count = self.crud._delete_events_in_batches(
                "calendar-odd",
                ["instance-1", "instance-2", "instance-3"],
            )

        self.assertEqual(deleted_count, 3)
        self.service.new_batch_http_request.assert_called_once_with()
        self.assertEqual(self.service.events.return_value.delete.call_count, 3)
        batch.execute.assert_called_once()
        remove_extras.assert_called_once_with(
            ["instance-1", "instance-2", "instance-3"]
        )

    def test_batch_transport_failure_falls_back_to_single_deletes(self):
        batch = MagicMock()
        batch.execute.side_effect = ConnectionError("batch transport failed")
        self.service.new_batch_http_request.return_value = batch
        delete_request = MagicMock()
        delete_request.execute.return_value = None
        self.service.events.return_value.delete.return_value = delete_request

        with patch.object(self.crud, "remove_extras") as remove_extras:
            deleted_count = self.crud._delete_events_in_batches(
                "calendar-odd",
                ["instance-1", "instance-2"],
            )

        self.assertEqual(deleted_count, 2)
        self.assertEqual(delete_request.execute.call_count, 2)
        remove_extras.assert_called_once_with(["instance-1", "instance-2"])


if __name__ == "__main__":
    unittest.main()
