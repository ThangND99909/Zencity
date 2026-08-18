"""Google Calendar giả lập, đủ thật để chạy E2E cho luồng thêm/sửa/xóa.

Mô phỏng đúng những hành vi mà code phụ thuộc vào:
  - hai calendar (chẵn / lẻ);
  - chuỗi lặp sinh ra instance với id '<master>_<YYYYMMDDTHHMMSSZ>' như Google;
  - EXDATE loại bỏ occurrence khỏi chuỗi;
  - xóa lần hai trả về 410 Gone (chứ không phải 404);
  - events().move() giữ nguyên id.
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

from dateutil.rrule import rrulestr
from googleapiclient.errors import HttpError

CALENDAR_ODD = "calendar-odd"
CALENDAR_EVEN = "calendar-even"


def http_error(status, reason="Error"):
    return HttpError(resp=SimpleNamespace(status=status, reason=reason), content=reason.encode())


def parse_dt(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class _Request:
    def __init__(self, run):
        self._run = run

    def execute(self, **_kwargs):
        return self._run()


class _Batch:
    def __init__(self, service):
        self._service = service
        self._queued = []

    def add(self, request, request_id, callback):
        self._queued.append((request_id, request, callback))

    def execute(self, **_kwargs):
        for request_id, request, callback in self._queued:
            try:
                callback(request_id, request.execute(), None)
            except Exception as error:  # noqa: BLE001 - batch báo lỗi qua callback
                callback(request_id, None, error)


class _Events:
    def __init__(self, service):
        self._service = service

    def get(self, calendarId, eventId, **_kwargs):
        return _Request(lambda: self._service.read(calendarId, eventId))

    def insert(self, calendarId, body, **_kwargs):
        return _Request(lambda: self._service.insert(calendarId, body))

    def update(self, calendarId, eventId, body, **_kwargs):
        return _Request(lambda: self._service.update(calendarId, eventId, body))

    def delete(self, calendarId, eventId, **_kwargs):
        return _Request(lambda: self._service.delete(calendarId, eventId))

    def move(self, calendarId, eventId, destination, **_kwargs):
        return _Request(lambda: self._service.move(calendarId, eventId, destination))

    def instances(self, calendarId, eventId, **_kwargs):
        return _Request(lambda: self._service.instances(calendarId, eventId))

    def list(self, calendarId, **kwargs):
        return _Request(lambda: self._service.list(calendarId, **kwargs))


class FakeCalendarService:
    def __init__(self):
        self.store = {CALENDAR_ODD: {}, CALENDAR_EVEN: {}}
        self.gone = set()          # id đã từng bị xóa → lần sau trả 410 như Google
        self.fail_insert = False   # bật để mô phỏng Google lỗi lúc tạo
        self.fail_move = False
        self._seq = 0

    # ---------------- helpers ----------------
    def _next_id(self):
        self._seq += 1
        return f"generated{self._seq:04d}"

    def all_event_ids(self):
        return {
            calendar_id: sorted(events)
            for calendar_id, events in self.store.items()
        }

    def total_events(self):
        return sum(len(events) for events in self.store.values())

    def find(self, event_id):
        for calendar_id, events in self.store.items():
            if event_id in events:
                return calendar_id, events[event_id]
        return None, None

    # ---------------- API ----------------
    def events(self):
        return _Events(self)

    def new_batch_http_request(self):
        return _Batch(self)

    def calendarList(self):  # noqa: N802 - khớp tên của googleapiclient
        return SimpleNamespace(list=lambda **_k: _Request(lambda: {"items": []}))

    def read(self, calendar_id, event_id):
        events = self.store.get(calendar_id, {})
        if event_id not in events:
            raise http_error(410 if event_id in self.gone else 404, "Not Found")
        return dict(events[event_id])

    def insert(self, calendar_id, body):
        if self.fail_insert:
            raise http_error(500, "Backend Error")
        event_id = body.get("id") or self._next_id()
        event = dict(body)
        event["id"] = event_id
        event.setdefault("status", "confirmed")
        self.store[calendar_id][event_id] = event
        if event.get("recurrence"):
            self._materialize(calendar_id, event)
        return dict(event)

    def update(self, calendar_id, event_id, body):
        events = self.store.get(calendar_id, {})
        if event_id not in events:
            raise http_error(410 if event_id in self.gone else 404, "Not Found")
        event = dict(body)
        event["id"] = event_id
        event.setdefault("status", "confirmed")
        events[event_id] = event
        if event.get("recurrence"):
            self._materialize(calendar_id, event)
        return dict(event)

    def delete(self, calendar_id, event_id):
        events = self.store.get(calendar_id, {})
        if event_id not in events:
            raise http_error(410 if event_id in self.gone else 404, "Not Found")
        removed = events.pop(event_id)
        self.gone.add(event_id)
        # Xóa master ⇒ toàn bộ chuỗi biến mất, giống Google.
        if removed.get("recurrence"):
            for child_id in [
                child for child, value in events.items()
                if value.get("recurringEventId") == event_id
            ]:
                events.pop(child_id, None)
                self.gone.add(child_id)
        return ""

    def move(self, calendar_id, event_id, destination):
        if self.fail_move:
            raise http_error(500, "Backend Error")
        events = self.store.get(calendar_id, {})
        if event_id not in events:
            raise http_error(410 if event_id in self.gone else 404, "Not Found")
        event = events.pop(event_id)
        self.store[destination][event_id] = event
        return dict(event)

    def instances(self, calendar_id, event_id):
        events = self.store.get(calendar_id, {})
        if event_id not in events:
            raise http_error(410 if event_id in self.gone else 404, "Not Found")
        items = [
            dict(value) for value in events.values()
            if value.get("recurringEventId") == event_id
        ]
        items.sort(key=lambda item: item["start"]["dateTime"])
        return {"items": items}

    def list(self, calendar_id, **kwargs):
        events = self.store.get(calendar_id, {})
        single = kwargs.get("singleEvents", False)
        items = []
        for value in events.values():
            if single and value.get("recurrence"):
                continue  # singleEvents=True ⇒ Google trả instance thay cho master
            items.append(dict(value))
        return {"items": items, "nextSyncToken": "sync-token"}

    # ---------------- recurrence ----------------
    def _materialize(self, calendar_id, master):
        """Sinh instance từ RRULE và gỡ những occurrence nằm trong EXDATE."""
        rules = master.get("recurrence") or []
        rrule_line = next((rule for rule in rules if rule.startswith("RRULE:")), None)
        exdates = set()
        for rule in rules:
            if rule.startswith("EXDATE"):
                _, _, value = rule.rpartition(":")
                exdates.update(token.strip() for token in value.split(","))
        if not rrule_line:
            return

        events = self.store[calendar_id]
        start = parse_dt(master["start"]["dateTime"])
        duration = parse_dt(master["end"]["dateTime"]) - start

        for occurrence in rrulestr(rrule_line[len("RRULE:"):], dtstart=start):
            token = stamp(occurrence)
            instance_id = f"{master['id']}_{token}"
            if token in exdates:
                if events.pop(instance_id, None) is not None:
                    self.gone.add(instance_id)
                continue
            if instance_id in events:
                continue
            events[instance_id] = {
                "id": instance_id,
                "status": "confirmed",
                "summary": master.get("summary", ""),
                "description": master.get("description", ""),
                "location": master.get("location", ""),
                "recurringEventId": master["id"],
                "originalStartTime": {"dateTime": occurrence.isoformat()},
                "start": {"dateTime": occurrence.isoformat()},
                "end": {"dateTime": (occurrence + duration).isoformat()},
            }

    # ---------------- dựng dữ liệu cho test ----------------
    def seed_single(self, calendar_id, event_id, summary, start, hours=1, description=""):
        begin = parse_dt(start)
        self.store[calendar_id][event_id] = {
            "id": event_id,
            "status": "confirmed",
            "summary": summary,
            "description": description,
            "start": {"dateTime": begin.isoformat(), "timeZone": "Asia/Ho_Chi_Minh"},
            "end": {"dateTime": (begin + timedelta(hours=hours)).isoformat(),
                    "timeZone": "Asia/Ho_Chi_Minh"},
        }
        return self.store[calendar_id][event_id]

    def seed_series(self, calendar_id, master_id, summary, start, count, description=""):
        begin = parse_dt(start)
        master = {
            "id": master_id,
            "status": "confirmed",
            "summary": summary,
            "description": description,
            "start": {"dateTime": begin.isoformat(), "timeZone": "Asia/Ho_Chi_Minh"},
            "end": {"dateTime": (begin + timedelta(hours=1)).isoformat(),
                    "timeZone": "Asia/Ho_Chi_Minh"},
            "recurrence": [f"RRULE:FREQ=DAILY;COUNT={count};INTERVAL=1"],
        }
        self.store[calendar_id][master_id] = master
        self._materialize(calendar_id, master)
        return master

    def instance_ids(self, calendar_id, master_id):
        return sorted(
            event_id for event_id, value in self.store[calendar_id].items()
            if value.get("recurringEventId") == master_id
        )


def load_calendar_crud(service, extra_file):
    """Nạp calendar_crud gắn với service giả và file metadata riêng của test."""
    fake_module = ModuleType("google_calendar")
    fake_module.calendar_service = service
    fake_module.CALENDARS = {"odd": CALENDAR_ODD, "even": CALENDAR_EVEN}
    fake_module.create_calendar_http = lambda **_kwargs: object()

    module_path = Path(__file__).resolve().parents[1] / "calendar_crud.py"
    spec = importlib.util.spec_from_file_location("calendar_crud_e2e", module_path)
    module = importlib.util.module_from_spec(spec)

    previous = sys.modules.get("google_calendar")
    sys.modules["google_calendar"] = fake_module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop("google_calendar", None)
        else:
            sys.modules["google_calendar"] = previous

    module.EXTRA_FILE = Path(extra_file)
    return module
