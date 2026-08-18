"""E2E luồng XÓA — chạy qua calendar_crud thật với Google Calendar giả lập.

Trọng tâm: một lệnh "xóa buổi này" KHÔNG được đụng tới bất cứ sự kiện nào khác.
Cơ chế cũ dò theo chuỗi con của id và theo từ cuối trong tiêu đề nên có thể quét trúng
cả chuỗi lặp, thậm chí các lớp khác chỉ vì trùng tên chương trình.
"""
import pytest

from fake_calendar import CALENDAR_EVEN, CALENDAR_ODD, FakeCalendarService, load_calendar_crud


PROGRAM = "ESL KIDS and JUNIOR"


@pytest.fixture
def calendar(tmp_path):
    service = FakeCalendarService()
    crud = load_calendar_crud(service, tmp_path / "classes_extra.json")
    return service, crud


def seed_world(service):
    """Một chuỗi lặp 3 buổi + hai sự kiện KHÔNG liên quan nhưng dễ bị khớp nhầm."""
    service.seed_series(
        CALENDAR_ODD, "master1", f"Lớp A - Cô Lan - {PROGRAM}",
        "2026-08-20T09:00:00+07:00", count=3,
    )
    # Cùng chương trình (trùng từ cuối trong tiêu đề) và cách chưa tới 2 giờ —
    # đây chính là thứ mà cách dò cũ sẽ xóa nhầm.
    service.seed_single(
        CALENDAR_ODD, "neighbour1", f"Lớp B - Thầy Nam - {PROGRAM}",
        "2026-08-20T10:00:00+07:00",
    )
    service.seed_single(
        CALENDAR_EVEN, "neighbour2", f"Lớp C - Cô Mai - {PROGRAM}",
        "2026-08-20T10:00:00+07:00",
    )


def test_delete_this_removes_only_the_targeted_occurrence(calendar):
    service, crud = calendar
    seed_world(service)
    instances = service.instance_ids(CALENDAR_ODD, "master1")
    target = instances[1]
    before = service.total_events()

    result = crud.delete_event(target, delete_mode="this")

    assert result["status"] == "deleted"
    assert service.total_events() == before - 1
    # Chuỗi còn nguyên 2 buổi kia, master còn nguyên.
    assert service.instance_ids(CALENDAR_ODD, "master1") == [instances[0], instances[2]]
    assert service.find("master1")[0] == CALENDAR_ODD
    # Hai sự kiện không liên quan phải còn nguyên vẹn.
    assert service.find("neighbour1")[0] == CALENDAR_ODD
    assert service.find("neighbour2")[0] == CALENDAR_EVEN


def test_deleting_the_same_occurrence_twice_is_idempotent_and_harmless(calendar):
    """Kịch bản kích hoạt lỗi cũ: UI cache cũ / bấm hai lần → Google trả 410 Gone."""
    service, crud = calendar
    seed_world(service)
    target = service.instance_ids(CALENDAR_ODD, "master1")[1]

    crud.delete_event(target, delete_mode="this")
    snapshot = service.all_event_ids()

    result = crud.delete_event(target, delete_mode="this")

    assert result["status"] == "already_deleted"
    # Lần xóa thứ hai KHÔNG được đụng vào bất cứ thứ gì.
    assert service.all_event_ids() == snapshot


def test_gone_delete_never_touches_a_same_program_neighbour(calendar):
    """Sự kiện lạc hoàn toàn: không có chuỗi cha, chỉ trùng chương trình và giờ giấc."""
    service, crud = calendar
    seed_world(service)
    service.seed_single(
        CALENDAR_ODD, "orphan1", f"Lớp D - Cô Hoa - {PROGRAM}",
        "2026-08-20T09:30:00+07:00",
    )
    crud.delete_event("orphan1", delete_mode="this")
    snapshot = service.all_event_ids()

    result = crud.delete_event("orphan1", delete_mode="this")

    assert result["status"] == "already_deleted"
    assert service.all_event_ids() == snapshot
    assert service.find("neighbour1")[0] == CALENDAR_ODD


def test_stale_instance_id_is_relocated_through_the_master_series(calendar):
    """Chuỗi bị sửa nên Google cấp id mới cho cùng một buổi.

    Đây là tình huống duy nhất đáng khôi phục, và phải khôi phục bằng cách hỏi chính
    chuỗi cha — không phải bằng cách đoán.
    """
    service, crud = calendar
    seed_world(service)
    instances = service.instance_ids(CALENDAR_ODD, "master1")
    stale_id = instances[1]

    # Cùng thời điểm bắt đầu nhưng mang id khác.
    occurrence = service.store[CALENDAR_ODD].pop(stale_id)
    service.gone.add(stale_id)
    renamed = dict(occurrence, id="master1_renewed")
    service.store[CALENDAR_ODD]["master1_renewed"] = renamed

    result = crud.delete_event(stale_id, delete_mode="this")

    assert result["status"] == "deleted"
    assert result["recovered_event_id"] == "master1_renewed"
    assert "master1_renewed" not in service.store[CALENDAR_ODD]
    # Các buổi khác và sự kiện lân cận vẫn nguyên.
    assert service.instance_ids(CALENDAR_ODD, "master1") == [instances[0], instances[2]]
    assert service.find("neighbour1")[0] == CALENDAR_ODD


def test_delete_all_removes_the_series_but_nothing_else(calendar):
    service, crud = calendar
    seed_world(service)
    target = service.instance_ids(CALENDAR_ODD, "master1")[0]

    result = crud.delete_event(target, delete_mode="all")

    assert result["status"] == "deleted"
    assert service.find("master1")[0] is None
    assert service.instance_ids(CALENDAR_ODD, "master1") == []
    assert service.find("neighbour1")[0] == CALENDAR_ODD
    assert service.find("neighbour2")[0] == CALENDAR_EVEN


def test_delete_all_twice_is_idempotent(calendar):
    service, crud = calendar
    seed_world(service)
    target = service.instance_ids(CALENDAR_ODD, "master1")[0]

    crud.delete_event(target, delete_mode="all")
    snapshot = service.all_event_ids()
    result = crud.delete_event(target, delete_mode="all")

    assert result["status"] == "already_deleted"
    assert service.all_event_ids() == snapshot


def test_delete_following_removes_only_this_and_later_occurrences(calendar):
    service, crud = calendar
    seed_world(service)
    instances = service.instance_ids(CALENDAR_ODD, "master1")

    result = crud.delete_event(instances[1], delete_mode="following")

    assert result["status"] == "deleted"
    assert result["deleted_count"] == 2
    assert service.instance_ids(CALENDAR_ODD, "master1") == [instances[0]]
    assert service.find("neighbour1")[0] == CALENDAR_ODD
    assert service.find("neighbour2")[0] == CALENDAR_EVEN
