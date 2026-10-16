# backend/calendar_parity.py
"""Quy tắc chọn calendar CHẴN/LẺ và tách chuỗi lặp tại mốc đổi giờ.

Quy tắc của khách hàng: calendar được chọn theo GIỜ VIỆT NAM của thời điểm bắt đầu
buổi học — giờ VN chẵn → calendar EVEN, giờ VN lẻ → calendar ODD.

Với lớp theo giờ Mỹ, giờ VN của cùng một lớp đổi 1 tiếng mỗi lần Mỹ đổi giờ:

    20:00 Chicago = 08:00 VN trước 01/11/2026 (CHẴN → EVEN)
                  = 09:00 VN từ  01/11/2026 (LẺ   → ODD)

Google lưu cả một chuỗi lặp trong MỘT calendar, nên chuỗi vắt qua mốc đổi giờ phải
được tách thành nhiều đoạn, mỗi đoạn là một chuỗi riêng nằm đúng calendar của nó.
Module này không phụ thuộc Google để có thể test độc lập.
"""
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone

import pytz
from dateutil.rrule import rrulestr

from recurrence_helper import validate_recurrence_timezone, wall_clock_utc_range

PARITY_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

# Trần số buổi khi bung một chuỗi để tách đoạn (~10 năm học hằng ngày). Vượt trần thì
# từ chối thay vì tách sai.
MAX_SERIES_OCCURRENCES = 3660


def parity_of(moment):
    """'even' hoặc 'odd' theo giờ Việt Nam của một thời điểm có múi giờ."""
    if moment.tzinfo is None:
        raise ValueError("parity_of() needs a timezone-aware datetime")
    return 'even' if moment.astimezone(PARITY_TIMEZONE).hour % 2 == 0 else 'odd'


def to_utc(value, tz_name):
    """Đưa chuỗi ISO / datetime về UTC; giá trị naive là giờ treo tường trong ``tz_name``."""
    tz = pytz.timezone(validate_recurrence_timezone(tz_name))
    if isinstance(value, datetime):
        parsed = value
    else:
        if not value or not str(value).strip():
            raise ValueError("Datetime string must not be empty")
        parsed = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = wall_clock_utc_range(parsed, tz)[0]
    return parsed.astimezone(dt_timezone.utc)


def utc_stamp(moment):
    """Định dạng RFC 5545 cho UNTIL: YYYYMMDDTHHMMSSZ."""
    return moment.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')


@dataclass(frozen=True)
class SeriesSegment:
    """Một đoạn liên tiếp của chuỗi lặp mà mọi buổi cùng một calendar."""
    parity: str
    starts: tuple  # thời điểm bắt đầu (UTC) của từng buổi, tăng dần

    @property
    def first(self):
        return self.starts[0]

    @property
    def last(self):
        return self.starts[-1]


def _split_rrule(recurrence_lines):
    """Tách (dòng RRULE, các dòng khác) — Google cho phép kèm EXDATE/RDATE."""
    rrule_lines = [line for line in recurrence_lines or [] if line.startswith('RRULE:')]
    if len(rrule_lines) != 1:
        raise ValueError("A recurring event must have exactly one RRULE line")
    others = [line for line in recurrence_lines if not line.startswith('RRULE:')]
    return rrule_lines[0], others


def series_occurrence_starts(start, tz_name, recurrence_lines):
    """Bung chuỗi lặp thành các thời điểm bắt đầu (UTC) đúng như Google sinh ra.

    Đã kiểm chứng trên Google Calendar thật:
      - luật lặp chạy theo GIỜ TREO TƯỜNG trong ``timeZone`` của sự kiện (20:00 Chicago
        vẫn là 20:00 sau khi đổi giờ, chỉ có giờ UTC đổi);
      - UNTIL bao gồm chính buổi trùng mốc UNTIL;
      - DTSTART luôn là một buổi, kể cả khi không khớp BYDAY — khi đó COUNT chỉ đếm
        các buổi khớp luật, DTSTART là buổi thêm.
    """
    tz = pytz.timezone(validate_recurrence_timezone(tz_name))
    start_utc = to_utc(start, tz_name)
    rrule_line, _ = _split_rrule(recurrence_lines)

    parts = [part for part in rrule_line[len('RRULE:'):].split(';') if part]
    until_utc = None
    kept = []
    for part in parts:
        key, _, value = part.partition('=')
        if key.upper() == 'UNTIL':
            until_utc = _parse_until(value, tz)
        else:
            kept.append(part)
    if until_utc is None and not any(part.upper().startswith('COUNT=') for part in kept):
        raise ValueError("Recurring classes must have an end (COUNT or UNTIL)")

    start_wall = start_utc.astimezone(tz).replace(tzinfo=None)
    try:
        rule = rrulestr(';'.join(kept), dtstart=start_wall)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid recurrence rule '{rrule_line}': {error}") from error

    starts = {start_utc}
    for wall in rule:
        moment = wall_clock_utc_range(wall, tz)[0]
        if until_utc is not None and moment > until_utc:
            break
        starts.add(moment)
        if len(starts) > MAX_SERIES_OCCURRENCES:
            raise ValueError(
                f"Recurring series is longer than {MAX_SERIES_OCCURRENCES} occurrences"
            )
    return sorted(starts)


def _parse_until(value, tz):
    value = value.strip()
    if value.endswith('Z'):
        return datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt_timezone.utc)
    if 'T' in value:
        return wall_clock_utc_range(datetime.strptime(value, '%Y%m%dT%H%M%S'), tz)[1]
    # UNTIL chỉ có ngày: bao gồm cả ngày đó theo giờ treo tường.
    day_end = datetime.strptime(value, '%Y%m%d').replace(hour=23, minute=59, second=59)
    return wall_clock_utc_range(day_end, tz)[1]


def plan_series_segments(start, tz_name, recurrence_lines):
    """Chia chuỗi lặp thành các đoạn liên tiếp cùng calendar (theo giờ VN)."""
    segments = []
    for moment in series_occurrence_starts(start, tz_name, recurrence_lines):
        parity = parity_of(moment)
        if segments and segments[-1][0] == parity:
            segments[-1][1].append(moment)
        else:
            segments.append((parity, [moment]))
    return [SeriesSegment(parity, tuple(starts)) for parity, starts in segments]


def segment_recurrence(recurrence_lines, segment):
    """Luật lặp cho một đoạn: giữ nguyên luật gốc nhưng kết thúc đúng ở buổi cuối của đoạn.

    Dùng UNTIL thay vì COUNT để ranh giới không phụ thuộc cách đếm DTSTART.
    """
    rrule_line, others = _split_rrule(recurrence_lines)
    parts = [
        part for part in rrule_line[len('RRULE:'):].split(';')
        if part and part.partition('=')[0].upper() not in ('COUNT', 'UNTIL')
    ]
    parts.append(f'UNTIL={utc_stamp(segment.last)}')
    return ['RRULE:' + ';'.join(parts)] + others


def has_rrule(recurrence_lines):
    return any(str(line).startswith('RRULE:') for line in recurrence_lines or [])
