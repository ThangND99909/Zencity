# backend/recurrence_helper.py
from datetime import datetime, timezone as dt_timezone

import pytz
from dateutil.rrule import rrulestr

from log_config import make_print

print = make_print(__name__)

# Trần số buổi được bung ra để kiểm tra trùng lịch. Chặn trường hợp người dùng gõ
# nhầm repeat_count rất lớn làm treo request.
MAX_OCCURRENCES = 366


def build_recurrence_rule(class_info):
    
    freq = class_info.get("recurrence", "").upper().strip()
    print(f"   Extracted freq: '{freq}'")
    
    if not freq:
        print("🔁 No recurrence specified, returning None")
        return None

    rrule_parts = [f"FREQ={freq}"]
    print(f"   Initial rules: {rrule_parts}")

    # COUNT - số lần lặp 
    repeat_count = class_info.get("repeat_count", 1)
    print(f"   repeat_count (after fix): {repeat_count}")
    
    if repeat_count > 0:
        rrule_parts.append(f"COUNT={repeat_count}")
        print(f"   Added COUNT: {rrule_parts}")

    # BYDAY cho WEEKLY
    if freq == "WEEKLY" and class_info.get("byday"):
        byday_str = ','.join(class_info['byday'])
        rrule_parts.append(f"BYDAY={byday_str}")
        print(f"   Added BYDAY: {rrule_parts}")

    # BYMONTHDAY cho MONTHLY
    if freq == "MONTHLY" and class_info.get("bymonthday"):
        bymonthday_str = ','.join(map(str, class_info['bymonthday']))
        rrule_parts.append(f"BYMONTHDAY={bymonthday_str}")
        print(f"   Added BYMONTHDAY: {rrule_parts}")

    # BYMONTH và BYMONTHDAY cho YEARLY
    if freq == "YEARLY":
        if class_info.get("bymonth"):
            bymonth_str = ','.join(map(str, class_info['bymonth']))
            rrule_parts.append(f"BYMONTH={bymonth_str}")
            print(f"   Added BYMONTH: {rrule_parts}")
        if class_info.get("bymonthday"):
            bymonthday_str = ','.join(map(str, class_info['bymonthday']))
            rrule_parts.append(f"BYMONTHDAY={bymonthday_str}")
            print(f"   Added BYMONTHDAY: {rrule_parts}")

    # INTERVAL mặc định là 1
    rrule_parts.append("INTERVAL=1")
    print(f"   Added INTERVAL: {rrule_parts}")

    rrule = "RRULE:" + ";".join(rrule_parts)
    print(f"📆 Generated RRULE: {rrule}")
    
    # ✅ CHỈ TRẢ VỀ RRULE STRING, KHÔNG PHẢI OBJECT
    return rrule

def _to_aware_utc(value, tz):
    """Đưa một chuỗi ISO về datetime aware ở UTC.

    Chuỗi naive (không offset) được hiểu là giờ treo tường trong `tz` — đúng với
    giá trị datetime-local mà form gửi lên.
    """
    if isinstance(value, datetime):
        parsed = value
    else:
        if not value or not str(value).strip():
            raise ValueError("Datetime string must not be empty")
        parsed = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = tz.localize(parsed)
    return parsed.astimezone(dt_timezone.utc)


def wall_clock_utc_range(naive, tz):
    """Một giờ treo tường trong ``tz`` ứng với mốc UTC nào — trả ``(sớm nhất, muộn nhất)``.

    Ngày thường hai giá trị BẰNG NHAU. Chỉ đúng hai mốc DST mới khác:
      - Fall-back (Mỹ: CN đầu tháng 11): 01:30 xảy ra HAI lần, cách nhau 1 tiếng.
      - Spring-forward (Mỹ: CN thứ 2 tháng 3): 02:30 KHÔNG tồn tại.

    Khi đó trả về khoảng bao trùm mọi khả năng để việc dò trùng lịch fail-closed —
    thà kiểm tra dư một tiếng còn hơn bỏ sót một xung đột thật.
    """
    candidates = {
        tz.normalize(tz.localize(naive, is_dst=is_dst)).astimezone(dt_timezone.utc)
        for is_dst in (True, False)
    }
    return min(candidates), max(candidates)


def expand_occurrences(start, end, class_info, max_occurrences=MAX_OCCURRENCES):
    """Bung một sự kiện (kèm luật lặp) thành danh sách buổi thực tế theo UTC.

    Trả về ``(occurrences, truncated)`` với occurrences là list ``(start_utc, end_utc)``
    đã sắp xếp tăng dần, và truncated=True khi chuỗi bị cắt vì vượt max_occurrences.

    Vì sao cần: kiểm tra trùng lịch trước đây chỉ so buổi ĐẦU TIÊN, nên một chuỗi lặp
    10 tuần chỉ được kiểm tra 1/10 số buổi — 9 buổi còn lại có thể trùng mà không ai biết.

    Buổi gốc (DTSTART) LUÔN được đưa vào kết quả kể cả khi không khớp BYDAY. Thà kiểm
    tra dư một buổi còn hơn bỏ sót một xung đột thật.

    FIX DST: luật lặp được bung theo GIỜ TREO TƯỜNG (naive) trong múi giờ của sự kiện,
    rồi mới localize từng buổi về UTC — đúng ngữ nghĩa Google Calendar (RRULE + timeZone:
    lớp 9h sáng vẫn là 9h sáng quanh năm, offset tự đổi -06:00 ↔ -05:00).

    Trước đây dtstart được gán tzinfo có offset CỐ ĐỊNH tại ngày bắt đầu
    (``start_utc.astimezone(tz)``); dateutil giữ nguyên tzinfo đó cho mọi buổi sau nên
    toàn bộ chuỗi vắt qua mốc DST bị lệch đúng 1 tiếng so với sự kiện Google thật sự
    tạo ra — vừa bỏ sót xung đột thật, vừa báo trùng giả.
    """
    tz = pytz.timezone(validate_recurrence_timezone(class_info.get('timezone')))

    start_utc = _to_aware_utc(start, tz)
    end_utc = _to_aware_utc(end, tz)
    if end_utc <= start_utc:
        raise ValueError("Event end time must be later than its start time")

    rule = build_recurrence_rule(class_info)
    if not rule:
        return [(start_utc, end_utc)], False

    # Giờ treo tường của buổi gốc trong múi giờ sự kiện — đây mới là thứ RRULE lặp lại.
    start_wall = start_utc.astimezone(tz).replace(tzinfo=None)
    end_wall = end_utc.astimezone(tz).replace(tzinfo=None)

    # Độ dài tính theo giờ treo tường (lớp 9:00–10:00 vẫn là 9:00–10:00 sau khi đổi giờ).
    # Buổi gốc nằm vắt qua đúng mốc fall-back có thể cho hiệu âm/0 — khi đó lùi về độ
    # dài thật theo UTC để không bao giờ sinh ra buổi có end <= start.
    wall_duration = end_wall - start_wall
    if wall_duration.total_seconds() <= 0:
        wall_duration = end_utc - start_utc

    try:
        rule_set = rrulestr(rule[len("RRULE:"):], dtstart=start_wall)
    except Exception as error:
        raise ValueError(f"Invalid recurrence rule '{rule}': {error}") from error

    # Buổi gốc luôn có mặt, và giữ đúng mốc UTC người dùng đã gửi lên.
    spans = {start_utc: end_utc}
    truncated = False
    for index, occurrence in enumerate(rule_set):
        if index >= max_occurrences:
            truncated = True
            break
        occurrence_start, _ = wall_clock_utc_range(occurrence, tz)
        _, occurrence_end = wall_clock_utc_range(occurrence + wall_duration, tz)
        # Trùng mốc bắt đầu thì giữ khoảng RỘNG hơn (fail-closed).
        previous_end = spans.get(occurrence_start)
        spans[occurrence_start] = (
            max(previous_end, occurrence_end) if previous_end else occurrence_end
        )

    print(f"📆 Expanded {len(spans)} occurrence(s) from {rule} (truncated={truncated})")
    return [(moment, spans[moment]) for moment in sorted(spans)], truncated


def validate_recurrence_timezone(tz_str):
    """Giống validate_timezone của calendar_crud nhưng không kéo theo phụ thuộc Google."""
    aliases = {
        "Asia/Saigon": "Asia/Ho_Chi_Minh",
        "Asia/HoChiMinh": "Asia/Ho_Chi_Minh",
    }
    tz_str = aliases.get(tz_str, tz_str) or "Asia/Ho_Chi_Minh"
    try:
        pytz.timezone(tz_str)
        return tz_str
    except pytz.UnknownTimeZoneError:
        print(f"⚠️ Unknown timezone '{tz_str}', fallback to 'Asia/Ho_Chi_Minh'")
        return "Asia/Ho_Chi_Minh"


# ✅ THÊM HÀM RIÊNG ĐỂ TẠO RECURRENCE DESCRIPTION
def build_recurrence_description(class_info):
    """
    Xây dựng mô tả recurrence có timezone cho hiển thị
    """
    freq = class_info.get("recurrence", "").upper().strip()
    timezone = class_info.get('timezone', 'Asia/Ho_Chi_Minh')
    
    # Map timezone sang tên hiển thị
    timezone_display_map = {
        'Asia/Ho_Chi_Minh': 'Giờ Việt Nam',
        'America/Chicago': 'Giờ Miền Trung - Chicago', 
        'America/New_York': 'Giờ Miền Đông - New York',
        'America/Los_Angeles': 'Giờ Miền Tây - Los Angeles',
        'America/Denver': 'Giờ Miền Núi - Denver',
        'Europe/London': 'Giờ London',
        'Europe/Paris': 'Giờ Paris',
        'Asia/Tokyo': 'Giờ Nhật Bản - Tokyo',
        'Asia/Seoul': 'Giờ Hàn Quốc - Seoul',
        'Asia/Singapore': 'Giờ Singapore',
        'Australia/Sydney': 'Giờ Sydney',
        'Pacific/Auckland': 'Giờ New Zealand - Auckland',
        'UTC': 'Giờ UTC'
    }
    
    timezone_display = timezone_display_map.get(timezone, timezone)
    
    if freq == "WEEKLY":
        days_map = {
            'MO': 'thứ hai', 'TU': 'thứ ba', 'WE': 'thứ tư',
            'TH': 'thứ năm', 'FR': 'thứ sáu', 'SA': 'thứ bảy', 'SU': 'chủ nhật'
        }
        days = [days_map.get(day, day) for day in class_info.get('byday', [])]
        days_str = ', '.join(days)
        return f"Hàng tuần vào {days_str} ({timezone_display})"
    
    elif freq == "DAILY":
        return f"Hàng ngày ({timezone_display})"
    
    elif freq == "MONTHLY":
        days = class_info.get('bymonthday', [])
        days_str = ', '.join(map(str, days))
        return f"Hàng tháng vào ngày {days_str} ({timezone_display})"
    
    elif freq == "YEARLY":
        months_map = {
            1: 'tháng 1', 2: 'tháng 2', 3: 'tháng 3', 4: 'tháng 4',
            5: 'tháng 5', 6: 'tháng 6', 7: 'tháng 7', 8: 'tháng 8', 
            9: 'tháng 9', 10: 'tháng 10', 11: 'tháng 11', 12: 'tháng 12'
        }
        months = [months_map.get(month, f"tháng {month}") for month in class_info.get('bymonth', [])]
        months_str = ', '.join(months)
        days = class_info.get('bymonthday', [])
        days_str = ', '.join(map(str, days))
        return f"Hàng năm vào ngày {days_str} {months_str} ({timezone_display})"
    
    else:
        return f"Lặp lại ({timezone_display})"