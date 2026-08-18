"""Kiểm tra trùng lịch trên TOÀN BỘ chuỗi lặp và nhận diện giáo viên tin cậy.

Hai giới hạn cũ được khoá lại ở đây:
  1. Chỉ buổi ĐẦU TIÊN của chuỗi lặp được kiểm tra → các buổi sau trùng mà không ai biết.
  2. Tên giáo viên chỉ tách từ summary theo ' - ' → tên lớp có chứa ' - ' làm tách sai
     và xung đột bị bỏ sót.
"""
from datetime import datetime, timedelta, timezone

import pytz

from check_conflict import (
    extract_teacher_from_event,
    find_conflicts,
    group_occurrences_into_windows,
    master_id_of,
    window_bounds,
)
from recurrence_helper import expand_occurrences


def utc(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00')).astimezone(timezone.utc)


def event(summary, start, end, description=None, event_id="existing-1", recurring_event_id=None):
    payload = {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    if description is not None:
        payload["description"] = description
    if recurring_event_id:
        payload["recurringEventId"] = recurring_event_id
    return payload


# --------------------------------------------------------------------------
# 1) Bung chuỗi lặp
# --------------------------------------------------------------------------

def test_single_event_expands_to_one_occurrence():
    occurrences, truncated = expand_occurrences(
        "2026-08-20T08:00:00Z", "2026-08-20T09:00:00Z", {"recurrence": ""}
    )
    assert len(occurrences) == 1
    assert truncated is False


def test_daily_series_expands_to_every_occurrence():
    occurrences, truncated = expand_occurrences(
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
        {"recurrence": "DAILY", "repeat_count": 5, "timezone": "Asia/Ho_Chi_Minh"},
    )
    assert len(occurrences) == 5
    assert truncated is False
    # Mỗi buổi cách nhau đúng 1 ngày và giữ nguyên độ dài.
    assert occurrences[1][0] - occurrences[0][0] == timedelta(days=1)
    assert all(end - start == timedelta(hours=1) for start, end in occurrences)


def test_weekly_series_respects_byday_in_event_timezone():
    """BYDAY phải tính theo giờ địa phương của sự kiện, không phải theo UTC.

    17:00 giờ VN thứ Hai = 10:00 UTC cùng ngày, nhưng 00:30 giờ VN thứ Hai lại là
    17:30 UTC Chủ nhật hôm trước. Nếu bung chuỗi ở UTC thì BYDAY lệch mất một ngày.
    """
    vn = pytz.timezone("Asia/Ho_Chi_Minh")
    occurrences, _ = expand_occurrences(
        "2026-08-16T17:30:00Z",  # 00:30 thứ Hai 17/08/2026 giờ VN
        "2026-08-16T18:30:00Z",
        {
            "recurrence": "WEEKLY",
            "repeat_count": 3,
            "byday": ["MO"],
            "timezone": "Asia/Ho_Chi_Minh",
        },
    )

    local_days = [start.astimezone(vn) for start, _ in occurrences]
    # Mọi buổi đều rơi vào thứ Hai theo giờ VN (weekday() == 0).
    assert [day.weekday() for day in local_days] == [0, 0, 0]
    assert [day.hour for day in local_days] == [0, 0, 0]
    assert len(occurrences) == 3


def test_dtstart_is_kept_even_when_it_does_not_match_byday():
    """Thà kiểm tra dư buổi gốc còn hơn bỏ sót một xung đột thật."""
    occurrences, _ = expand_occurrences(
        "2026-08-18T08:00:00Z",  # thứ Ba
        "2026-08-18T09:00:00Z",
        {
            "recurrence": "WEEKLY",
            "repeat_count": 2,
            "byday": ["MO", "WE"],
            "timezone": "Asia/Ho_Chi_Minh",
        },
    )
    assert occurrences[0][0] == utc("2026-08-18T08:00:00Z")


def test_runaway_repeat_count_is_capped():
    occurrences, truncated = expand_occurrences(
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
        {"recurrence": "DAILY", "repeat_count": 100000},
        max_occurrences=50,
    )
    assert len(occurrences) == 50
    assert truncated is True


# --------------------------------------------------------------------------
# 2) Xung đột trên buổi thứ N của chuỗi
# --------------------------------------------------------------------------

def test_conflict_on_a_later_occurrence_is_detected():
    occurrences, _ = expand_occurrences(
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
        {"recurrence": "DAILY", "repeat_count": 5},
    )
    # Lịch đã có một lớp vào buổi thứ 4 của chuỗi (23/08).
    existing = [event(
        "Other Class - Teacher A - Program X",
        "2026-08-23T08:30:00Z",
        "2026-08-23T09:30:00Z",
    )]

    result = find_conflicts(existing, "Teacher A", occurrences)

    assert result["has_conflict"] is True
    assert result["checked_occurrences"] == 5
    assert result["conflicts"][0]["occurrence_start"].startswith("2026-08-23")


def test_first_occurrence_free_but_series_conflicts():
    """Chính xác kịch bản mà lỗi cũ bỏ lọt: buổi đầu trống, buổi sau trùng."""
    occurrences, _ = expand_occurrences(
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
        {"recurrence": "DAILY", "repeat_count": 3},
    )
    existing = [event(
        "Other Class - Teacher A - Program X",
        "2026-08-22T08:00:00Z",
        "2026-08-22T09:00:00Z",
    )]

    # Chỉ kiểm tra buổi đầu → không thấy gì (đây là hành vi cũ).
    assert find_conflicts(existing, "Teacher A", occurrences[:1])["has_conflict"] is False
    # Kiểm tra cả chuỗi → phát hiện.
    assert find_conflicts(existing, "Teacher A", occurrences)["has_conflict"] is True


# --------------------------------------------------------------------------
# 3) Nhận diện giáo viên
# --------------------------------------------------------------------------

def test_teacher_is_read_from_description_first():
    cls = event(
        "Toán - Nâng cao - Cô Lan - ESL",  # tên lớp có chứa ' - '
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
        description="Classname: Toán - Nâng cao\nTeacher: Cô Lan\nProgram: ESL",
    )
    assert extract_teacher_from_event(cls) == "Cô Lan"


def test_teacher_falls_back_to_summary_counting_from_the_end():
    cls = event(
        "Toán - Nâng cao - Cô Lan - ESL",
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
    )
    # Không có description: giáo viên là phần áp chót (chương trình luôn ở cuối).
    assert extract_teacher_from_event(cls) == "Cô Lan"


def test_teacher_from_html_description():
    cls = event(
        "X - Y - Z",
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
        description="Classname: A<br>Teacher: Nguyễn Văn B<br>Program: C",
    )
    assert extract_teacher_from_event(cls) == "Nguyễn Văn B"


def test_class_name_with_dash_no_longer_hides_a_conflict():
    occurrences = [(utc("2026-08-20T08:00:00Z"), utc("2026-08-20T09:00:00Z"))]
    existing = [event(
        "Toán - Nâng cao - Cô Lan - ESL",
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
        description="Classname: Toán - Nâng cao\nTeacher: Cô Lan\nProgram: ESL",
    )]
    assert find_conflicts(existing, "Cô Lan", occurrences)["has_conflict"] is True
    # So khớp không phân biệt hoa thường / khoảng trắng thừa.
    assert find_conflicts(existing, "  cô   lan ", occurrences)["has_conflict"] is True


# --------------------------------------------------------------------------
# 4) Loại trừ chuỗi đang được sửa
# --------------------------------------------------------------------------

def test_master_id_of():
    assert master_id_of("abc123_20260820T080000Z") == "abc123"
    assert master_id_of("abc123") is None
    assert master_id_of("has_underscore_but_not_instance") is None


def test_editing_whole_series_excludes_its_own_occurrences():
    occurrences, _ = expand_occurrences(
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
        {"recurrence": "DAILY", "repeat_count": 3},
    )
    existing = [
        event("C - Teacher A - P", "2026-08-20T08:00:00Z", "2026-08-20T09:00:00Z",
              event_id="master-1_20260820T080000Z", recurring_event_id="master-1"),
        event("C - Teacher A - P", "2026-08-21T08:00:00Z", "2026-08-21T09:00:00Z",
              event_id="master-1_20260821T080000Z", recurring_event_id="master-1"),
    ]

    # Không loại trừ → mọi buổi tự trùng với chính nó.
    assert find_conflicts(existing, "Teacher A", occurrences)["has_conflict"] is True
    # Loại trừ chuỗi đang sửa → sạch.
    assert find_conflicts(
        existing, "Teacher A", occurrences, exclude_master_event_id="master-1"
    )["has_conflict"] is False


def test_this_mode_still_sees_siblings_of_the_same_series():
    """Mode 'this' chỉ loại đúng buổi đang sửa, nên dời trùng lên buổi khác vẫn bị chặn."""
    occurrences = [(utc("2026-08-21T08:00:00Z"), utc("2026-08-21T09:00:00Z"))]
    existing = [
        event("C - Teacher A - P", "2026-08-20T08:00:00Z", "2026-08-20T09:00:00Z",
              event_id="master-1_20260820T080000Z", recurring_event_id="master-1"),
        event("C - Teacher A - P", "2026-08-21T08:00:00Z", "2026-08-21T09:00:00Z",
              event_id="master-1_20260821T080000Z", recurring_event_id="master-1"),
    ]

    result = find_conflicts(
        existing, "Teacher A", occurrences,
        exclude_event_id="master-1_20260820T080000Z"
    )
    assert result["has_conflict"] is True


# --------------------------------------------------------------------------
# 5) Chia cửa sổ nạp lịch
# --------------------------------------------------------------------------

def test_long_series_is_split_into_loadable_windows():
    occurrences, _ = expand_occurrences(
        "2026-01-05T08:00:00Z",
        "2026-01-05T09:00:00Z",
        {"recurrence": "WEEKLY", "repeat_count": 40, "byday": ["MO"]},
    )
    windows = group_occurrences_into_windows(occurrences)

    # ~40 tuần ≈ 280 ngày, vượt xa trần 120 ngày của một lần nạp lịch.
    assert len(windows) > 1
    assert sum(len(window) for window in windows) == len(occurrences)
    for window in windows:
        start, end = window_bounds(window)
        assert end - start < timedelta(days=120)


def test_short_series_needs_only_one_window():
    occurrences, _ = expand_occurrences(
        "2026-08-20T08:00:00Z",
        "2026-08-20T09:00:00Z",
        {"recurrence": "WEEKLY", "repeat_count": 4, "byday": ["TH"]},
    )
    assert len(group_occurrences_into_windows(occurrences)) == 1
