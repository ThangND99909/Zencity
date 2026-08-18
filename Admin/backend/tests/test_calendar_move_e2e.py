"""E2E chuyển sự kiện giữa calendar chẵn/lẻ khi đổi giờ bắt đầu.

Bất biến quan trọng nhất: nếu bước tạo/chuyển ở calendar mới THẤT BẠI thì sự kiện cũ
phải còn nguyên. Code cũ xóa trước rồi mới tạo, nên mọi lỗi ở bước tạo đều làm mất hẳn
sự kiện và không thể khôi phục.
"""
import pytest

from fake_calendar import CALENDAR_EVEN, CALENDAR_ODD, FakeCalendarService, load_calendar_crud


@pytest.fixture
def calendar(tmp_path):
    service = FakeCalendarService()
    crud = load_calendar_crud(service, tmp_path / "classes_extra.json")
    return service, crud


def class_info(start_hour, edit_mode="this"):
    return {
        "name": "Lớp A - Cô Lan - ESL",
        "classname": "Lớp A",
        "teacher": "Cô Lan",
        "program": "ESL",
        "zoom_link": "https://zoom.example/a",
        "meeting_id": "111",
        "passcode": "222",
        "start": f"2026-08-20T{start_hour:02d}:00:00+07:00",
        "end": f"2026-08-20T{start_hour + 1:02d}:00:00+07:00",
        "timezone": "Asia/Ho_Chi_Minh",
        "edit_mode": edit_mode,
    }


# ---------------------------------------------------------------- sự kiện đơn

def test_single_event_moves_between_calendars_keeping_its_id(calendar):
    service, crud = calendar
    service.seed_single(CALENDAR_ODD, "event1", "Lớp A - Cô Lan - ESL",
                        "2026-08-20T09:00:00+07:00")

    crud.update_event("event1", class_info(10))  # 9h lẻ → 10h chẵn

    assert service.find("event1")[0] == CALENDAR_EVEN
    assert service.total_events() == 1  # không nhân bản
    moved = service.store[CALENDAR_EVEN]["event1"]
    assert "10:00" in moved["start"]["dateTime"]


def test_failed_move_leaves_the_event_untouched(calendar):
    """Không được mất dữ liệu khi Google lỗi lúc chuyển."""
    service, crud = calendar
    original = service.seed_single(CALENDAR_ODD, "event1", "Lớp A - Cô Lan - ESL",
                                   "2026-08-20T09:00:00+07:00")
    snapshot = dict(original)
    service.fail_move = True

    with pytest.raises(Exception):
        crud.update_event("event1", class_info(10))

    assert service.find("event1")[0] == CALENDAR_ODD
    assert service.store[CALENDAR_ODD]["event1"] == snapshot
    assert service.total_events() == 1


# ---------------------------------------------------------------- chuỗi lặp

def test_moving_one_occurrence_detaches_it_and_keeps_the_series(calendar):
    """Giống Google Calendar ở chế độ 'chỉ sự kiện này'."""
    service, crud = calendar
    service.seed_series(CALENDAR_ODD, "master1", "Lớp A - Cô Lan - ESL",
                        "2026-08-20T09:00:00+07:00", count=3)
    instances = service.instance_ids(CALENDAR_ODD, "master1")

    crud.update_event(instances[1], class_info(10))

    # Chuỗi cũ còn master và 2 buổi còn lại.
    assert service.find("master1")[0] == CALENDAR_ODD
    assert service.instance_ids(CALENDAR_ODD, "master1") == [instances[0], instances[2]]
    # Buổi được chuyển giờ là sự kiện đơn ở calendar chẵn.
    detached = [
        event for event in service.store[CALENDAR_EVEN].values()
        if not event.get("recurringEventId")
    ]
    assert len(detached) == 1
    assert "Single event - moved from recurring series" in detached[0]["description"]


def test_failed_insert_never_loses_the_original_occurrence(calendar):
    """Đây chính là ca mất dữ liệu của code cũ: xóa xong rồi tạo mới thất bại."""
    service, crud = calendar
    service.seed_series(CALENDAR_ODD, "master1", "Lớp A - Cô Lan - ESL",
                        "2026-08-20T09:00:00+07:00", count=3)
    instances = service.instance_ids(CALENDAR_ODD, "master1")
    before = service.all_event_ids()
    service.fail_insert = True

    with pytest.raises(Exception):
        crud.update_event(instances[1], class_info(10))

    # Không mất gì: master, cả 3 buổi vẫn còn, calendar chẵn vẫn trống.
    assert service.all_event_ids() == before
    assert service.instance_ids(CALENDAR_ODD, "master1") == instances
    assert service.store[CALENDAR_EVEN] == {}


def test_same_parity_update_does_not_move_calendars(calendar):
    """Đổi giờ nhưng vẫn cùng tính chẵn/lẻ ⇒ ở nguyên calendar cũ."""
    service, crud = calendar
    service.seed_single(CALENDAR_ODD, "event1", "Lớp A - Cô Lan - ESL",
                        "2026-08-20T09:00:00+07:00")

    crud.update_event("event1", class_info(11))  # 9h lẻ → 11h lẻ

    assert service.find("event1")[0] == CALENDAR_ODD
    assert service.total_events() == 1
