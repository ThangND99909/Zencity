import re
from datetime import datetime, timedelta, timezone
from log_config import make_print

print = make_print(__name__)

# Cửa sổ thời gian tối đa cho một lần nạp lịch. list_events chặn ở 120 ngày nên để
# 110 cho có biên an toàn (còn phải cộng thêm phần đệm hai đầu).
WINDOW_MAX_DAYS = 110
WINDOW_PADDING = timedelta(hours=1)

# Google sinh id instance dạng '<masterId>_<YYYYMMDD>T<HHMMSS>Z'.
_INSTANCE_SUFFIX_RE = re.compile(r'^\d{8}T\d{6}Z$')

# Description do backend dựng có dòng 'Teacher: ...'; 'GV:' để tương thích dữ liệu cũ.
_TEACHER_LINE_RE = re.compile(r'^[ \t]*(?:Teacher|GV)[ \t]*[:：][ \t]*(.+?)[ \t]*$',
                              re.IGNORECASE | re.MULTILINE)


def normalize_teacher_name(teacher_name):
    """Chuẩn hóa tên giáo viên để so sánh"""
    if not teacher_name:
        return ""
    return ' '.join(teacher_name.strip().lower().split())


def _plain_text(raw):
    """Gỡ HTML tối thiểu — Google trả description có thể chứa <br>, <a>, <p>."""
    text = re.sub(r'<br\s*/?>', '\n', raw, flags=re.IGNORECASE)
    text = re.sub(r'</\s*p\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]*>', '', text)
    return text


def extract_teacher_from_event(cls):
    """Trích tên giáo viên từ một event Google Calendar.

    Thứ tự ưu tiên:
      1. Field ``teacher`` (nếu caller đã gắn sẵn).
      2. Dòng ``Teacher:`` trong description — đây là nguồn ĐÁNG TIN CẬY nhất vì
         build_event_description luôn ghi ra dòng này.
      3. Cuối cùng mới tách từ summary dạng ``<lớp> - <giáo viên> - <chương trình>``.

    Trước đây hàm bỏ qua hoàn toàn description và luôn rơi vào bước 3 (list_events
    không gắn field ``teacher``). Tên lớp có chứa ' - ' sẽ khiến tách sai và xung đột
    bị bỏ sót.
    """
    cls_teacher = (cls.get('teacher') or '').strip()
    if cls_teacher:
        return cls_teacher

    description = cls.get('description') or ''
    if description:
        match = _TEACHER_LINE_RE.search(_plain_text(description))
        if match:
            teacher = match.group(1).strip()
            if teacher:
                return teacher

    summary = cls.get('summary') or ''
    if ' - ' in summary:
        parts = [part.strip() for part in summary.split(' - ')]
        # Chương trình luôn là phần cuối, nên giáo viên là phần áp chót. Đếm từ cuối
        # lên giúp chịu được tên lớp có chứa ' - '.
        if len(parts) >= 3:
            return parts[-2]
        if len(parts) == 2:
            return parts[1]

    return ""


def parse_iso_datetime_flexible(dt_str):
    """Parse datetime linh hoạt, xử lý cả với và không có timezone"""
    if not dt_str:
        return None

    try:
        # Xử lý string có Z
        if dt_str.endswith('Z'):
            dt_str = dt_str.replace('Z', '+00:00')

        # Nếu không có timezone, thêm timezone mặc định (Vietnam)
        if 'T' in dt_str and '+' not in dt_str and '-' not in dt_str.split('T')[1]:
            dt_str = dt_str + '+07:00'

        return datetime.fromisoformat(dt_str)
    except ValueError as e:
        print(f"❌ Error parsing datetime {dt_str}: {e}")
        return None


def master_id_of(event_id):
    """'MASTER_20260820T080000Z' → 'MASTER'. Trả None nếu không phải id instance."""
    if not event_id or '_' not in event_id:
        return None
    head, _, tail = event_id.rpartition('_')
    if head and _INSTANCE_SUFFIX_RE.match(tail):
        return head
    return None


def build_exclusion(exclude_event_id=None, exclude_master_event_id=None):
    """Tập id/chuỗi cần bỏ qua khi so trùng.

    ``exclude_master_event_id`` chỉ nên được truyền khi thao tác lưu thay thế CẢ chuỗi
    (edit mode 'following'/'all'). Ở mode 'this' chỉ loại đúng một buổi, để nếu người
    dùng dời buổi này trùng lên một buổi khác cùng chuỗi thì vẫn được cảnh báo.
    """
    excluded_ids = set()
    excluded_series = set()
    if exclude_event_id:
        excluded_ids.add(exclude_event_id)
    if exclude_master_event_id:
        excluded_series.add(exclude_master_event_id)
        excluded_ids.add(exclude_master_event_id)
    return excluded_ids, excluded_series


def _is_excluded(cls, excluded_ids, excluded_series):
    event_id = cls.get('id')
    if event_id and event_id in excluded_ids:
        return True
    if not excluded_series:
        return False
    if cls.get('recurringEventId') in excluded_series:
        return True
    if event_id and event_id in excluded_series:
        return True
    master = master_id_of(event_id)
    return bool(master and master in excluded_series)


def group_occurrences_into_windows(occurrences, max_days=WINDOW_MAX_DAYS):
    """Chia các buổi thành cụm sao cho mỗi cụm nạp được trong một cửa sổ lịch.

    Chuỗi lặp dài (vd một học kỳ) vượt quá cửa sổ mặc định của list_events; nếu chỉ nạp
    một cửa sổ thì các buổi cuối chuỗi không có dữ liệu để đối chiếu và sẽ lọt xung đột.
    """
    groups = []
    current = []
    anchor = None
    for start, end in sorted(occurrences):
        if anchor is None:
            anchor = start
        elif end - anchor > timedelta(days=max_days):
            groups.append(current)
            current = []
            anchor = start
        current.append((start, end))
    if current:
        groups.append(current)
    return groups


def window_bounds(occurrences):
    """Khoảng thời gian cần nạp lịch cho một cụm buổi (đã cộng phần đệm)."""
    start = min(item[0] for item in occurrences) - WINDOW_PADDING
    end = max(item[1] for item in occurrences) + WINDOW_PADDING
    return start, end


def find_conflicts(
    existing_classes,
    teacher,
    occurrences,
    exclude_event_id=None,
    exclude_master_event_id=None
):
    """So mọi buổi trong ``occurrences`` với lịch hiện có của cùng giáo viên.

    ``occurrences``: list ``(start_utc, end_utc)`` đều là datetime aware.

    ⚠️ FAIL-CLOSED: mọi lỗi đều raise lên caller. Trả về "không trùng" khi thực chất
    chưa kiểm tra được là cách chắc chắn nhất để sinh ra sự kiện trùng.
    """
    if not occurrences:
        raise ValueError("No occurrence to check")

    normalized_teacher = normalize_teacher_name(teacher)
    if not normalized_teacher:
        raise ValueError("Teacher name is required for conflict checking")

    excluded_ids, excluded_series = build_exclusion(exclude_event_id, exclude_master_event_id)

    # Lọc trước danh sách event của đúng giáo viên này, rồi mới đối chiếu từng buổi —
    # tránh parse lại description/summary cho mỗi cặp (buổi × event).
    candidates = []
    for cls in existing_classes:
        if _is_excluded(cls, excluded_ids, excluded_series):
            continue

        cls_teacher = extract_teacher_from_event(cls)
        if not cls_teacher or normalize_teacher_name(cls_teacher) != normalized_teacher:
            continue

        cls_start = parse_iso_datetime_flexible(cls.get('start', {}).get('dateTime', ''))
        cls_end = parse_iso_datetime_flexible(cls.get('end', {}).get('dateTime', ''))
        if not cls_start or not cls_end:
            continue

        candidates.append({
            'summary': cls.get('summary', 'No title'),
            'teacher': cls_teacher,
            'start_raw': cls.get('start', {}).get('dateTime', ''),
            'end_raw': cls.get('end', {}).get('dateTime', ''),
            'start_utc': cls_start.astimezone(timezone.utc),
            'end_utc': cls_end.astimezone(timezone.utc),
        })

    print(f"🔍 {len(candidates)} event(s) of '{teacher}' vs {len(occurrences)} occurrence(s)")

    conflicts = []
    for occurrence_start, occurrence_end in occurrences:
        for candidate in candidates:
            overlaps = (occurrence_start < candidate['end_utc']
                        and occurrence_end > candidate['start_utc'])
            if overlaps:
                conflicts.append({
                    'occurrence_start': occurrence_start.isoformat().replace('+00:00', 'Z'),
                    'occurrence_end': occurrence_end.isoformat().replace('+00:00', 'Z'),
                    'event_summary': candidate['summary'],
                    'event_teacher': candidate['teacher'],
                    'event_start': candidate['start_raw'],
                    'event_end': candidate['end_raw'],
                    'conflict_type': 'teacher_schedule_conflict',
                })

    print(f"📊 Found {len(conflicts)} conflict(s) across {len(occurrences)} occurrence(s)")

    return {
        'has_conflict': len(conflicts) > 0,
        'conflicts': conflicts,
        'conflict_count': len(conflicts),
        'checked_occurrences': len(occurrences),
    }


def traditional_conflict_check(
    existing_classes,
    teacher,
    new_start,
    new_end,
    exclude_event_id=None,
    exclude_master_event_id=None
):
    """Kiểm tra trùng lịch cho MỘT buổi. Giữ chữ ký cũ cho các caller đơn lẻ."""
    start_dt = parse_iso_datetime_flexible(new_start)
    end_dt = parse_iso_datetime_flexible(new_end)
    if not start_dt or not end_dt:
        raise ValueError(f"Invalid datetime format: start={new_start}, end={new_end}")

    return find_conflicts(
        existing_classes,
        teacher,
        [(start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc))],
        exclude_event_id=exclude_event_id,
        exclude_master_event_id=exclude_master_event_id,
    )
