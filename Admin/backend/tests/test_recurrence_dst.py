"""Chuỗi lặp vắt qua mốc đổi giờ (DST) phải giữ nguyên GIỜ TREO TƯỜNG.

Vì sao khoá lại ở đây: sự kiện được gửi lên Google dưới dạng RRULE + `timeZone`, nên
Google bung chuỗi theo giờ treo tường — lớp 9h sáng giờ Chicago vẫn là 9h sáng quanh
năm, chỉ offset đổi -06:00 (CST, mùa đông) <-> -05:00 (CDT, mùa hè).

`expand_occurrences` phải bung ra ĐÚNG các mốc đó thì việc dò trùng lịch mới soi đúng
sự kiện thật. Bản cũ gán cho dtstart một tzinfo offset CỐ ĐỊNH tại ngày bắt đầu, dateutil
giữ nguyên tzinfo ấy cho mọi buổi sau → toàn bộ chuỗi sau mốc DST lệch đúng 1 tiếng:
vừa bỏ sót xung đột thật, vừa báo trùng giả.

Mốc DST Mỹ dùng trong file này (2026):
  - Spring-forward: CN 08/03/2026, 02:00 → 03:00 (mất 1 tiếng)
  - Fall-back:      CN 01/11/2026, 02:00 → 01:00 (lặp 1 tiếng)
"""
from datetime import datetime, timedelta, timezone

import pytest
import pytz

from check_conflict import find_conflicts
from recurrence_helper import expand_occurrences

CHICAGO = pytz.timezone('America/Chicago')
SAIGON = pytz.timezone('Asia/Ho_Chi_Minh')


def series(start, end, timezone_name='America/Chicago', **rule):
    """Bung một chuỗi lặp; mặc định là lớp hàng tuần."""
    class_info = {
        'timezone': timezone_name,
        'recurrence': rule.pop('recurrence', 'WEEKLY'),
        'repeat_count': rule.pop('repeat_count', 4),
    }
    class_info.update(rule)
    return expand_occurrences(start, end, class_info)


def wall_clock(moment, tz=CHICAGO):
    """Mốc UTC → chuỗi 'YYYY-MM-DD HH:MM' theo giờ treo tường của `tz`."""
    return moment.astimezone(tz).strftime('%Y-%m-%d %H:%M')


def offsets(occurrences, tz=CHICAGO):
    return [occ[0].astimezone(tz).strftime('%z') for occ in occurrences]


def utc_iso(moment):
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')


# --------------------------------------------------------------------------
# 1. Hồi quy chính: giờ treo tường phải bất biến qua cả hai mốc DST
# --------------------------------------------------------------------------

def test_weekly_giu_nguyen_9h_sang_qua_spring_forward():
    """Lớp 9:00 thứ Hai bắt đầu 02/03/2026, DST rơi vào 08/03 → vẫn 9:00 mọi buổi."""
    occurrences, truncated = series(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00', byday=['MO'], repeat_count=4
    )

    assert not truncated
    assert [wall_clock(start) for start, _ in occurrences] == [
        '2026-03-02 09:00',
        '2026-03-09 09:00',
        '2026-03-16 09:00',
        '2026-03-23 09:00',
    ]
    # Đây mới là mốc UTC thật sự Google tạo ra — buổi đầu CST, ba buổi sau CDT.
    assert [utc_iso(start) for start, _ in occurrences] == [
        '2026-03-02T15:00Z',   # -06:00
        '2026-03-09T14:00Z',   # -05:00  <- bản cũ trả 15:00Z (sai 1 tiếng)
        '2026-03-16T14:00Z',
        '2026-03-23T14:00Z',
    ]
    assert offsets(occurrences) == ['-0600', '-0500', '-0500', '-0500']


def test_weekly_giu_nguyen_9h_sang_qua_fall_back():
    """Chiều ngược lại: bắt đầu 19/10/2026, DST kết thúc 01/11 → offset về -06:00."""
    occurrences, _ = series(
        '2026-10-19T09:00:00', '2026-10-19T10:00:00', byday=['MO'], repeat_count=4
    )

    assert [wall_clock(start) for start, _ in occurrences] == [
        '2026-10-19 09:00',
        '2026-10-26 09:00',
        '2026-11-02 09:00',
        '2026-11-09 09:00',
    ]
    assert [utc_iso(start) for start, _ in occurrences] == [
        '2026-10-19T14:00Z',   # -05:00
        '2026-10-26T14:00Z',
        '2026-11-02T15:00Z',   # -06:00  <- bản cũ trả 14:00Z (sai 1 tiếng)
        '2026-11-09T15:00Z',
    ]
    assert offsets(occurrences) == ['-0500', '-0500', '-0600', '-0600']


def test_daily_qua_dung_ngay_doi_gio():
    """DAILY đi xuyên qua chính ngày 08/03 — kể cả buổi NGAY TRƯỚC và NGAY SAU."""
    occurrences, _ = series(
        '2026-03-06T09:00:00', '2026-03-06T10:00:00',
        recurrence='DAILY', repeat_count=4
    )

    assert [wall_clock(start) for start, _ in occurrences] == [
        '2026-03-06 09:00',
        '2026-03-07 09:00',
        '2026-03-08 09:00',   # đúng ngày đổi giờ
        '2026-03-09 09:00',
    ]
    assert [utc_iso(start) for start, _ in occurrences] == [
        '2026-03-06T15:00Z',
        '2026-03-07T15:00Z',
        '2026-03-08T14:00Z',
        '2026-03-09T14:00Z',
    ]


def test_monthly_va_yearly_cung_giu_gio_treo_tuong():
    monthly, _ = series(
        '2026-01-15T09:00:00', '2026-01-15T10:00:00',
        recurrence='MONTHLY', bymonthday=[15], repeat_count=5
    )
    assert [wall_clock(start) for start, _ in monthly] == [
        '2026-01-15 09:00', '2026-02-15 09:00', '2026-03-15 09:00',
        '2026-04-15 09:00', '2026-05-15 09:00',
    ]

    yearly, _ = series(
        '2026-07-04T09:00:00', '2026-07-04T10:00:00',
        recurrence='YEARLY', bymonth=[7], bymonthday=[4], repeat_count=3
    )
    assert [wall_clock(start) for start, _ in yearly] == [
        '2026-07-04 09:00', '2027-07-04 09:00', '2028-07-04 09:00',
    ]


# --------------------------------------------------------------------------
# 2. Độ dài buổi học
# --------------------------------------------------------------------------

def test_do_dai_buoi_hoc_giu_nguyen_theo_gio_treo_tuong():
    """Lớp 90 phút vẫn là 09:00-10:30 sau khi đổi giờ, không bị co/giãn."""
    occurrences, _ = series(
        '2026-03-02T09:00:00', '2026-03-02T10:30:00', byday=['MO'], repeat_count=3
    )

    for start, end in occurrences:
        assert wall_clock(start).endswith('09:00')
        assert wall_clock(end).endswith('10:30')
        assert end - start == timedelta(minutes=90)


def test_buoi_vat_qua_dung_moc_fall_back_duoc_noi_rong():
    """Lớp 01:00-02:00 ngày 01/11/2026 thật sự kéo dài 2 tiếng đồng hồ.

    Giờ 01:00-02:00 xảy ra hai lần hôm đó. Khoảng trả về phải bao trùm cả hai lần thì
    mới không bỏ sót xung đột — fail-closed.
    """
    occurrences, _ = series(
        '2026-10-25T01:00:00', '2026-10-25T02:00:00',
        recurrence='WEEKLY', byday=['SU'], repeat_count=2
    )

    binh_thuong, vat_qua_dst = occurrences
    assert binh_thuong[1] - binh_thuong[0] == timedelta(hours=1)

    assert wall_clock(vat_qua_dst[0]).startswith('2026-11-01')
    # 01:00 CDT (06:00Z) -> 02:00 CST (08:00Z): hai tiếng thật.
    assert utc_iso(vat_qua_dst[0]) == '2026-11-01T06:00Z'
    assert utc_iso(vat_qua_dst[1]) == '2026-11-01T08:00Z'
    assert vat_qua_dst[1] - vat_qua_dst[0] == timedelta(hours=2)


def test_gio_bat_dau_nhap_nhang_bao_trum_ca_hai_kha_nang():
    """01:30 ngày fall-back xảy ra hai lần → khoảng phải phủ cả hai mốc thật."""
    occurrences, _ = series(
        '2026-10-25T01:30:00', '2026-10-25T02:30:00',
        recurrence='WEEKLY', byday=['SU'], repeat_count=2
    )

    _, nhap_nhang = occurrences
    assert utc_iso(nhap_nhang[0]) == '2026-11-01T06:30Z'   # lần đầu, CDT
    assert utc_iso(nhap_nhang[1]) == '2026-11-01T08:30Z'   # kết thúc theo CST


def test_buoi_goc_roi_dung_vao_gio_nhap_nhang():
    """DTSTART 01:30 ngày 01/11/2026 — bản thân nó cũng xảy ra hai lần.

    Buổi gốc được giữ theo mốc người dùng gửi (CST), còn luật lặp sinh thêm mốc CDT.
    Cả hai đều được kiểm tra và không buổi nào có end <= start.
    """
    occurrences, _ = series(
        '2026-11-01T01:30:00', '2026-11-01T02:30:00',
        recurrence='WEEKLY', byday=['SU'], repeat_count=2
    )

    for start, end in occurrences:
        assert end > start

    cua_ngay_dau = [utc_iso(s) for s, _ in occurrences if utc_iso(s).startswith('2026-11-01')]
    assert cua_ngay_dau == ['2026-11-01T06:30Z', '2026-11-01T07:30Z']


def test_gio_khong_ton_tai_trong_spring_forward_van_sinh_ra_buoi_hop_le():
    """02:30 ngày 08/03/2026 KHÔNG tồn tại — không được ném lỗi hay đảo ngược end."""
    occurrences, _ = series(
        '2026-03-01T02:30:00', '2026-03-01T03:30:00',
        recurrence='WEEKLY', byday=['SU'], repeat_count=2
    )

    for start, end in occurrences:
        assert end > start
    assert wall_clock(occurrences[1][0]).startswith('2026-03-08')


# --------------------------------------------------------------------------
# 3. Mọi dạng input đầu vào phải cho cùng một kết quả
# --------------------------------------------------------------------------

@pytest.mark.parametrize('start, end', [
    ('2026-03-02T09:00:00', '2026-03-02T10:00:00'),               # naive = giờ treo tường
    ('2026-03-02T15:00:00Z', '2026-03-02T16:00:00Z'),             # UTC
    ('2026-03-02T09:00:00-06:00', '2026-03-02T10:00:00-06:00'),   # có offset
    ('2026-03-02T22:00:00+07:00', '2026-03-02T23:00:00+07:00'),   # gửi từ máy ở VN
])
def test_moi_dang_input_cho_cung_mot_chuoi(start, end):
    occurrences, _ = series(start, end, byday=['MO'], repeat_count=3)

    assert [utc_iso(s) for s, _ in occurrences] == [
        '2026-03-02T15:00Z', '2026-03-09T14:00Z', '2026-03-16T14:00Z',
    ]


def test_datetime_object_cung_duoc_chap_nhan():
    start = CHICAGO.localize(datetime(2026, 3, 2, 9, 0))
    end = CHICAGO.localize(datetime(2026, 3, 2, 10, 0))
    occurrences, _ = series(start, end, byday=['MO'], repeat_count=2)

    assert [utc_iso(s) for s, _ in occurrences] == [
        '2026-03-02T15:00Z', '2026-03-09T14:00Z',
    ]


# --------------------------------------------------------------------------
# 4. Không được làm hỏng hành vi sẵn có
# --------------------------------------------------------------------------

def test_mui_gio_viet_nam_khong_co_dst_giu_nguyen():
    occurrences, _ = series(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00',
        timezone_name='Asia/Ho_Chi_Minh', byday=['MO'], repeat_count=4
    )

    assert [utc_iso(s) for s, _ in occurrences] == [
        '2026-03-02T02:00Z', '2026-03-09T02:00Z',
        '2026-03-16T02:00Z', '2026-03-23T02:00Z',
    ]
    assert offsets(occurrences, SAIGON) == ['+0700'] * 4


def test_su_kien_don_khong_lap_tra_ve_dung_mot_buoi():
    occurrences, truncated = expand_occurrences(
        '2026-03-09T09:00:00', '2026-03-09T10:00:00',
        {'timezone': 'America/Chicago'}
    )

    assert not truncated
    assert len(occurrences) == 1
    assert utc_iso(occurrences[0][0]) == '2026-03-09T14:00Z'


def test_buoi_goc_luon_co_mat_du_khong_khop_byday():
    """DTSTART là thứ Ba nhưng luật chỉ lặp thứ Hai — vẫn phải kiểm tra buổi gốc."""
    occurrences, _ = series(
        '2026-03-03T09:00:00', '2026-03-03T10:00:00', byday=['MO'], repeat_count=2
    )

    wall = [wall_clock(s) for s, _ in occurrences]
    assert '2026-03-03 09:00' in wall          # buổi gốc (thứ Ba)
    assert '2026-03-09 09:00' in wall          # thứ Hai kế tiếp, đã sang CDT
    assert wall == sorted(wall)


def test_ket_qua_luon_duoc_sap_xep_va_khong_trung_lap():
    occurrences, _ = series(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00', byday=['MO'], repeat_count=10
    )

    starts = [s for s, _ in occurrences]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)


def test_chuoi_qua_dai_bi_cat_va_bao_truncated():
    occurrences, truncated = expand_occurrences(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00',
        {'timezone': 'America/Chicago', 'recurrence': 'DAILY', 'repeat_count': 50},
        max_occurrences=5,
    )

    assert truncated
    assert len(occurrences) == 5


def test_end_khong_lon_hon_start_thi_bao_loi():
    with pytest.raises(ValueError):
        series('2026-03-02T10:00:00', '2026-03-02T09:00:00', byday=['MO'])


# --------------------------------------------------------------------------
# 5. Các múi giờ Mỹ khác + bán cầu Nam (DST ngược chiều)
# --------------------------------------------------------------------------

@pytest.mark.parametrize('zone, truoc, sau', [
    ('America/New_York',    '2026-03-02T14:00Z', '2026-03-09T13:00Z'),  # -5 -> -4
    ('America/Chicago',     '2026-03-02T15:00Z', '2026-03-09T14:00Z'),  # -6 -> -5
    ('America/Denver',      '2026-03-02T16:00Z', '2026-03-09T15:00Z'),  # -7 -> -6
    ('America/Los_Angeles', '2026-03-02T17:00Z', '2026-03-09T16:00Z'),  # -8 -> -7
])
def test_cac_mui_gio_my_deu_doi_dung_ngay_08_03(zone, truoc, sau):
    occurrences, _ = series(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00',
        timezone_name=zone, byday=['MO'], repeat_count=2
    )

    assert [utc_iso(s) for s, _ in occurrences] == [truoc, sau]


def test_arizona_khong_ap_dung_dst():
    """Phoenix đứng yên ở -07:00 quanh năm — không được tự ý đổi offset."""
    occurrences, _ = series(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00',
        timezone_name='America/Phoenix', byday=['MO'], repeat_count=2
    )

    assert [utc_iso(s) for s, _ in occurrences] == [
        '2026-03-02T16:00Z', '2026-03-09T16:00Z',
    ]


def test_chau_au_doi_gio_khac_ngay_voi_my():
    """London đổi giờ 29/03/2026, không phải 08/03."""
    occurrences, _ = series(
        '2026-03-23T09:00:00', '2026-03-23T10:00:00',
        timezone_name='Europe/London', byday=['MO'], repeat_count=2
    )

    assert [utc_iso(s) for s, _ in occurrences] == [
        '2026-03-23T09:00Z',   # GMT
        '2026-03-30T08:00Z',   # BST (+01:00)
    ]


def test_ban_cau_nam_lui_gio_thay_vi_tien():
    """Sydney kết thúc DST 05/04/2026: +11:00 -> +10:00."""
    occurrences, _ = series(
        '2026-03-30T09:00:00', '2026-03-30T10:00:00',
        timezone_name='Australia/Sydney', byday=['MO'], repeat_count=2
    )

    assert [utc_iso(s) for s, _ in occurrences] == [
        '2026-03-29T22:00Z',   # +11:00
        '2026-04-05T23:00Z',   # +10:00
    ]


# --------------------------------------------------------------------------
# 6. Hệ quả cuối cùng: dò trùng lịch phải đúng
# --------------------------------------------------------------------------

def google_instance(local_start, local_end, teacher, zone=CHICAGO):
    """Dựng event y như Google trả về cho một occurrence của chuỗi lặp."""
    start = zone.localize(datetime.fromisoformat(local_start))
    end = zone.localize(datetime.fromisoformat(local_end))
    return {
        'id': f'evt_{local_start}',
        'summary': f'Lop A - {teacher} - Program X',
        'description': f'Teacher: {teacher}',
        'start': {'dateTime': start.isoformat(), 'timeZone': str(zone)},
        'end': {'dateTime': end.isoformat(), 'timeZone': str(zone)},
    }


def test_phat_hien_trung_lich_o_buoi_sau_moc_dst():
    """Buổi 09/03 (đã sang CDT) trùng thật → bản cũ so ở 15:00Z nên BỎ SÓT."""
    occurrences, _ = series(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00', byday=['MO'], repeat_count=3
    )
    existing = [google_instance('2026-03-09T09:30', '2026-03-09T10:30', 'Co Lan')]

    result = find_conflicts(existing, 'Co Lan', occurrences)

    assert result['has_conflict']
    assert result['conflict_count'] == 1
    assert result['conflicts'][0]['occurrence_start'] == '2026-03-09T14:00:00Z'


def test_khong_bao_trung_gia_o_khung_gio_cu():
    """10:00-11:00 ngày 09/03 là khung CŨ (sai 1 tiếng) → không được báo trùng."""
    occurrences, _ = series(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00', byday=['MO'], repeat_count=3
    )
    existing = [google_instance('2026-03-09T10:00', '2026-03-09T11:00', 'Co Lan')]

    result = find_conflicts(existing, 'Co Lan', occurrences)

    assert not result['has_conflict']
    assert result['checked_occurrences'] == 3
