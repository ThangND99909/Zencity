"""Giờ treo tường phải được đọc theo múi giờ CỦA SỰ KIỆN, không phải giờ Việt Nam.

Bản cũ của `parse_iso_datetime_flexible` gắn cứng '+07:00' cho mọi chuỗi datetime
không có offset:

    if 'T' in dt_str and '+' not in dt_str and '-' not in dt_str.split('T')[1]:
        dt_str = dt_str + '+07:00'

Với một lớp ở Mỹ, điều đó đẩy sự kiện đi 12–13 tiếng — buổi học bị đem so trùng với
một khung giờ hoàn toàn khác, nên vừa BỎ SÓT xung đột thật vừa BÁO TRÙNG GIẢ. Bản
thân '+07:00' cũng không diễn tả nổi múi giờ có đổi giờ: 9:00 Chicago là -06:00 mùa
đông nhưng -05:00 mùa hè.

Mọi event do hệ thống tạo đều được insert kèm ``'timeZone': <múi giờ người dùng chọn>``
(calendar_crud.create_event), nên đó mới là nguồn đúng để hiểu một giờ treo tường.
"""
from datetime import datetime, timezone

import pytest
import pytz

from check_conflict import (
    DEFAULT_TIMEZONE,
    event_timezone_of,
    find_conflicts,
    parse_iso_datetime_flexible,
    traditional_conflict_check,
)

CHICAGO = pytz.timezone('America/Chicago')


def utc_iso(moment):
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')


def event(start, end, teacher='Co Lan', zone=None, event_id='evt-1'):
    """Event đúng hình dạng Google trả về; `zone` đi vào field 'timeZone'."""
    start_field = {'dateTime': start}
    end_field = {'dateTime': end}
    if zone:
        start_field['timeZone'] = zone
        end_field['timeZone'] = zone
    return {
        'id': event_id,
        'summary': f'Lop A - {teacher} - Program X',
        'description': f'Teacher: {teacher}',
        'start': start_field,
        'end': end_field,
    }


def occurrence(start, end):
    return [(
        datetime.fromisoformat(start.replace('Z', '+00:00')),
        datetime.fromisoformat(end.replace('Z', '+00:00')),
    )]


# --------------------------------------------------------------------------
# 1. parse_iso_datetime_flexible — lõi của mục này
# --------------------------------------------------------------------------

def test_naive_doc_theo_mui_gio_duoc_chi_dinh_chu_khong_phai_gio_vn():
    """9:00 Chicago giữa hè là 14:00Z. Bản cũ trả 02:00Z (hiểu thành giờ VN)."""
    parsed = parse_iso_datetime_flexible('2026-07-15T09:00:00', 'America/Chicago')

    assert utc_iso(parsed) == '2026-07-15T14:00Z'
    # Khoá lại rằng cách hiểu cũ đã biến mất hẳn.
    assert utc_iso(parsed) != '2026-07-15T02:00Z'


def test_naive_theo_mui_gio_my_doi_offset_theo_mua():
    """Cùng 9:00 Chicago: mùa đông -06:00, mùa hè -05:00."""
    mua_dong = parse_iso_datetime_flexible('2026-01-15T09:00:00', 'America/Chicago')
    mua_he = parse_iso_datetime_flexible('2026-07-15T09:00:00', 'America/Chicago')

    assert utc_iso(mua_dong) == '2026-01-15T15:00Z'   # CST
    assert utc_iso(mua_he) == '2026-07-15T14:00Z'     # CDT


@pytest.mark.parametrize('zone, expected', [
    ('America/New_York', '2026-07-15T13:00Z'),
    ('America/Chicago', '2026-07-15T14:00Z'),
    ('America/Denver', '2026-07-15T15:00Z'),
    ('America/Los_Angeles', '2026-07-15T16:00Z'),
    ('America/Phoenix', '2026-07-15T16:00Z'),   # không áp dụng DST
    ('Asia/Ho_Chi_Minh', '2026-07-15T02:00Z'),
])
def test_naive_theo_tung_mui_gio(zone, expected):
    assert utc_iso(parse_iso_datetime_flexible('2026-07-15T09:00:00', zone)) == expected


def test_khong_truyen_mui_gio_thi_van_giu_mac_dinh_viet_nam():
    """Tương thích ngược: caller cũ không truyền gì vẫn được hiểu là giờ VN."""
    assert utc_iso(parse_iso_datetime_flexible('2026-07-15T09:00:00')) == '2026-07-15T02:00Z'
    assert DEFAULT_TIMEZONE == 'Asia/Ho_Chi_Minh'


def test_mui_gio_khong_hop_le_roi_ve_mac_dinh_chu_khong_no():
    for zone in ('Mars/Olympus', '', 'UTC+7', None):
        parsed = parse_iso_datetime_flexible('2026-07-15T09:00:00', zone)
        assert utc_iso(parsed) == '2026-07-15T02:00Z'


def test_alias_mui_gio_van_duoc_chap_nhan():
    assert utc_iso(parse_iso_datetime_flexible('2026-07-15T09:00:00', 'Asia/Saigon')) \
        == '2026-07-15T02:00Z'


# --------------------------------------------------------------------------
# 2. Chuỗi ĐÃ có offset thì không được đụng vào
# --------------------------------------------------------------------------

@pytest.mark.parametrize('text, expected', [
    ('2026-07-15T14:00:00Z', '2026-07-15T14:00Z'),
    ('2026-07-15T09:00:00-05:00', '2026-07-15T14:00Z'),
    ('2026-07-15T21:00:00+07:00', '2026-07-15T14:00Z'),
    ('2026-07-15T14:00:00+00:00', '2026-07-15T14:00Z'),
])
def test_chuoi_co_offset_giu_nguyen_moc_that(text, expected):
    """default_timezone phải bị BỎ QUA khi chuỗi đã tự khai offset."""
    for zone in (None, 'America/Chicago', 'Australia/Sydney'):
        assert utc_iso(parse_iso_datetime_flexible(text, zone)) == expected


def test_ket_qua_luon_la_datetime_aware():
    """Trả về naive sẽ khiến .astimezone() ở find_conflicts âm thầm dùng giờ máy chủ."""
    for text in ('2026-07-15T09:00:00', '2026-07-15T14:00:00Z', '2026-07-15'):
        parsed = parse_iso_datetime_flexible(text, 'America/Chicago')
        assert parsed is not None
        assert parsed.tzinfo is not None


def test_chuoi_chi_co_ngay_cung_duoc_gan_mui_gio():
    """Bản cũ để lọt dạng này ra ngoài dưới dạng naive (không có 'T')."""
    parsed = parse_iso_datetime_flexible('2026-07-15', 'America/Chicago')

    assert parsed.tzinfo is not None
    assert utc_iso(parsed) == '2026-07-15T05:00Z'   # nửa đêm giờ Chicago


@pytest.mark.parametrize('bad', ['', None, '   ', 'not-a-datetime', '2026-13-45T99:99:99'])
def test_dau_vao_hong_van_tra_ve_none(bad):
    assert parse_iso_datetime_flexible(bad, 'America/Chicago') is None


# --------------------------------------------------------------------------
# 3. Hai mốc DST: khoảng phải được nới rộng (fail-closed)
# --------------------------------------------------------------------------

def test_gio_nhap_nhang_fall_back_earliest_va_latest():
    """01:30 ngày 01/11/2026 giờ Chicago xảy ra HAI lần, cách nhau 1 tiếng."""
    som = parse_iso_datetime_flexible('2026-11-01T01:30:00', 'America/Chicago', 'earliest')
    muon = parse_iso_datetime_flexible('2026-11-01T01:30:00', 'America/Chicago', 'latest')

    assert utc_iso(som) == '2026-11-01T06:30Z'    # CDT
    assert utc_iso(muon) == '2026-11-01T07:30Z'   # CST
    assert som < muon


def test_gio_khong_ton_tai_spring_forward_khong_no():
    """02:30 ngày 08/03/2026 giờ Chicago không tồn tại — vẫn phải trả mốc hợp lệ."""
    som = parse_iso_datetime_flexible('2026-03-08T02:30:00', 'America/Chicago', 'earliest')
    muon = parse_iso_datetime_flexible('2026-03-08T02:30:00', 'America/Chicago', 'latest')

    assert som is not None and muon is not None
    assert som <= muon


def test_gio_binh_thuong_thi_earliest_va_latest_bang_nhau():
    som = parse_iso_datetime_flexible('2026-07-15T09:00:00', 'America/Chicago', 'earliest')
    muon = parse_iso_datetime_flexible('2026-07-15T09:00:00', 'America/Chicago', 'latest')

    assert som == muon


# --------------------------------------------------------------------------
# 4. event_timezone_of
# --------------------------------------------------------------------------

def test_doc_mui_gio_tu_event_google():
    assert event_timezone_of(event('2026-07-15T09:00:00', '2026-07-15T10:00:00',
                                   zone='America/Chicago')) == 'America/Chicago'


def test_lay_mui_gio_o_end_khi_start_thieu():
    cls = {'start': {'dateTime': 'x'}, 'end': {'dateTime': 'y', 'timeZone': 'America/Denver'}}
    assert event_timezone_of(cls) == 'America/Denver'


def test_khong_co_mui_gio_thi_tra_none():
    assert event_timezone_of(event('2026-07-15T09:00:00', '2026-07-15T10:00:00')) is None
    assert event_timezone_of({}) is None
    assert event_timezone_of({'start': None, 'end': None}) is None


# --------------------------------------------------------------------------
# 5. Hệ quả thật trong find_conflicts
# --------------------------------------------------------------------------

def test_bat_duoc_trung_lich_voi_event_my_luu_dang_naive():
    """Event Chicago 09:00–10:00 (naive + timeZone) = 14:00Z–15:00Z.

    Buổi mới 14:30Z–15:30Z trùng thật. Bản cũ đọc event thành 02:00Z–03:00Z nên
    KHÔNG thấy trùng — đúng loại lỗi nguy hiểm nhất: âm thầm cho tạo lớp chồng giờ.
    """
    existing = [event('2026-07-15T09:00:00', '2026-07-15T10:00:00', zone='America/Chicago')]

    result = find_conflicts(existing, 'Co Lan',
                            occurrence('2026-07-15T14:30:00Z', '2026-07-15T15:30:00Z'))

    assert result['has_conflict']
    assert result['conflict_count'] == 1


def test_khong_bao_trung_gia_o_khung_gio_vn_hieu_nham():
    """02:30Z–03:30Z là khung mà bản cũ NHẦM tưởng event đang chiếm."""
    existing = [event('2026-07-15T09:00:00', '2026-07-15T10:00:00', zone='America/Chicago')]

    result = find_conflicts(existing, 'Co Lan',
                            occurrence('2026-07-15T02:30:00Z', '2026-07-15T03:30:00Z'))

    assert not result['has_conflict']


def test_moi_mui_gio_cua_tung_event_duoc_ton_trong_rieng():
    """Hai event cùng ghi '09:00' nhưng khác múi giờ → hai mốc thật khác nhau."""
    existing = [
        event('2026-07-15T09:00:00', '2026-07-15T10:00:00',
              zone='America/Chicago', event_id='chicago'),
        event('2026-07-15T09:00:00', '2026-07-15T10:00:00',
              zone='Asia/Ho_Chi_Minh', event_id='saigon'),
    ]

    trung_chicago = find_conflicts(existing, 'Co Lan',
                                   occurrence('2026-07-15T14:30:00Z', '2026-07-15T15:30:00Z'))
    trung_saigon = find_conflicts(existing, 'Co Lan',
                                  occurrence('2026-07-15T02:30:00Z', '2026-07-15T03:30:00Z'))

    assert trung_chicago['conflict_count'] == 1
    assert trung_saigon['conflict_count'] == 1


def test_event_thieu_timezone_van_roi_ve_gio_vn_nhu_cu():
    """Dữ liệu cũ không có field timeZone → giữ nguyên hành vi mặc định, không nổ."""
    existing = [event('2026-07-15T09:00:00', '2026-07-15T10:00:00')]

    result = find_conflicts(existing, 'Co Lan',
                            occurrence('2026-07-15T02:30:00Z', '2026-07-15T03:30:00Z'))

    assert result['has_conflict']


def test_event_co_offset_san_khong_bi_timezone_field_lam_lech():
    """dateTime đã có offset thì 'timeZone' chỉ là thông tin phụ, không được ghi đè."""
    cls = event('2026-07-15T09:00:00-05:00', '2026-07-15T10:00:00-05:00',
                zone='Asia/Ho_Chi_Minh')

    result = find_conflicts([cls], 'Co Lan',
                            occurrence('2026-07-15T14:30:00Z', '2026-07-15T15:30:00Z'))

    assert result['has_conflict']


# --------------------------------------------------------------------------
# 6. traditional_conflict_check
# --------------------------------------------------------------------------

def test_traditional_check_nhan_mui_gio_cua_su_kien():
    existing = [event('2026-07-15T14:30:00Z', '2026-07-15T15:30:00Z')]

    result = traditional_conflict_check(
        existing_classes=existing,
        teacher='Co Lan',
        new_start='2026-07-15T09:00:00',
        new_end='2026-07-15T10:00:00',
        timezone_name='America/Chicago',
    )

    assert result['has_conflict']


def test_traditional_check_khong_co_mui_gio_van_hieu_la_gio_vn():
    existing = [event('2026-07-15T02:30:00Z', '2026-07-15T03:30:00Z')]

    result = traditional_conflict_check(
        existing_classes=existing,
        teacher='Co Lan',
        new_start='2026-07-15T09:00:00',
        new_end='2026-07-15T10:00:00',
    )

    assert result['has_conflict']


def test_traditional_check_van_bao_loi_voi_datetime_hong():
    with pytest.raises(ValueError):
        traditional_conflict_check(
            existing_classes=[],
            teacher='Co Lan',
            new_start='not-a-datetime',
            new_end='2026-07-15T10:00:00',
            timezone_name='America/Chicago',
        )


def test_traditional_check_giu_nguyen_hanh_vi_voi_chuoi_utc():
    """Hồi quy: đường đi thực tế của frontend (luôn gửi 'Z') không đổi gì."""
    existing = [event('2026-07-15T14:30:00Z', '2026-07-15T15:30:00Z')]

    trung = traditional_conflict_check(
        existing_classes=existing, teacher='Co Lan',
        new_start='2026-07-15T14:00:00Z', new_end='2026-07-15T15:00:00Z')
    khong_trung = traditional_conflict_check(
        existing_classes=existing, teacher='Co Lan',
        new_start='2026-07-15T16:00:00Z', new_end='2026-07-15T17:00:00Z')

    assert trung['has_conflict']
    assert not khong_trung['has_conflict']
