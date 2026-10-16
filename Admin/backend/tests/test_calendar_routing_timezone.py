"""Calendar CHẴN/LẺ chọn theo GIỜ VIỆT NAM của thời điểm bắt đầu (yêu cầu khách hàng).

Quy tắc khách hàng nêu khi Mỹ hết giờ mùa hè (Chủ nhật 01/11/2026):

    "A class starts with even time is now scheduled until Nov 1.
     On Nov 2, it must be in the Odd calendar."

    20:00 Chicago = 08:00 VN trước mốc (CHẴN → EVEN) = 09:00 VN sau mốc (LẺ → ODD)

Quy ước chẵn/lẻ lộ ra tận UI: sidebar "Calendar Lẻ (Giờ lẻ)" / "Calendar Chẵn (Giờ
chẵn)" lọc theo calendar mà sự kiện ĐANG NẰM, nên chọn sai calendar = lọc ra sai lớp.
Việc tách chuỗi lặp tại mốc đổi giờ được test ở test_dst_series_segments.py.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytz

# Dùng lại loader sẵn có: nạp calendar_crud với google_calendar giả, không cần
# credentials và không gọi mạng. CALENDARS = {'odd': 'calendar-odd', ...}
from test_calendar_crud_performance import CRUD as crud

ODD = 'calendar-odd'
EVEN = 'calendar-even'

CHICAGO = pytz.timezone('America/Chicago')


def route(dt_str, zone=None):
    return crud.determine_calendar_by_hour(dt_str, zone)


# --------------------------------------------------------------------------
# 1. Đúng ví dụ của khách hàng quanh mốc đổi giờ 01/11/2026
# --------------------------------------------------------------------------

def test_vi_du_cua_khach_hang_lop_gio_chan_sang_calendar_le_tu_02_11():
    assert route('2026-10-26T20:00:00', 'America/Chicago') == EVEN   # 08:00 VN
    assert route('2026-11-02T20:00:00', 'America/Chicago') == ODD    # 09:00 VN


def test_lop_gio_le_chicago_sang_calendar_chan_sau_moc():
    assert route('2026-10-27T19:00:00', 'America/Chicago') == ODD    # 07:00 VN
    assert route('2026-11-03T19:00:00', 'America/Chicago') == EVEN   # 08:00 VN


def test_chu_nhat_01_11_buoi_toi_da_theo_gio_moi():
    """Mỹ đổi giờ lúc 2:00 sáng CN 01/11 — buổi tối hôm đó đã là giờ mùa đông."""
    assert route('2026-11-01T01:00:00-05:00', 'America/Chicago') == ODD   # 13:00 VN (CDT)
    assert route('2026-11-01T19:00:00', 'America/Chicago') == EVEN        # 08:00 VN (CST)
    assert route('2026-11-01T17:00:00', 'America/Chicago') == EVEN        # 06:00 VN


def test_mua_xuan_nam_sau_lat_lai():
    """Mỹ vào giờ mùa hè CN 14/03/2027: 20:00 Chicago từ 09:00 VN về 08:00 VN."""
    assert route('2027-03-08T20:00:00', 'America/Chicago') == ODD    # CST → 09:00 VN
    assert route('2027-03-15T20:00:00', 'America/Chicago') == EVEN   # CDT → 08:00 VN


# --------------------------------------------------------------------------
# 2. Mọi dạng input của cùng một thời điểm cho cùng một calendar
# --------------------------------------------------------------------------

@pytest.mark.parametrize('text', [
    '2026-10-26T20:00:00',            # naive = giờ treo tường Chicago
    '2026-10-27T01:00:00Z',           # cùng mốc, viết theo UTC
    '2026-10-26T20:00:00-05:00',      # cùng mốc, kèm offset Chicago
    '2026-10-27T08:00:00+07:00',      # cùng mốc, gửi từ máy ở VN
])
def test_moi_dang_input_cung_mot_thoi_diem(text):
    assert route(text, 'America/Chicago') == EVEN


def test_datetime_object_cung_duoc_hieu_dung():
    moment = CHICAGO.localize(datetime(2026, 11, 2, 20, 0))
    assert route(moment, 'America/Chicago') == ODD
    assert route(moment.astimezone(timezone.utc), 'America/Chicago') == ODD


@pytest.mark.parametrize('hour', list(range(24)))
def test_bang_parity_theo_gio_vn_cho_moi_gio_trong_ngay(hour):
    expected = EVEN if hour % 2 == 0 else ODD
    assert route(f'2026-07-20T{hour:02d}:00:00', 'Asia/Ho_Chi_Minh') == expected
    assert route(f'2026-07-20T{hour:02d}:00:00+07:00', 'America/Chicago') == expected


@pytest.mark.parametrize('zone, summer, winter', [
    # Giờ VN của 20:00 địa phương: mùa hè và mùa đông khác nhau 1 tiếng → đổi calendar.
    ('America/New_York', ODD, EVEN),      # 07:00 VN → 08:00 VN
    ('America/Chicago', EVEN, ODD),       # 08:00 VN → 09:00 VN
    ('America/Denver', ODD, EVEN),        # 09:00 VN → 10:00 VN
    ('America/Los_Angeles', EVEN, ODD),   # 10:00 VN → 11:00 VN
])
def test_cac_mui_gio_my_doi_calendar_theo_mua(zone, summer, winter):
    tz = pytz.timezone(zone)
    vn = pytz.timezone('Asia/Ho_Chi_Minh')
    for day, expected in (('2026-07-15', summer), ('2026-12-15', winter)):
        moment = tz.localize(datetime.fromisoformat(f'{day}T20:00:00'))
        vn_hour = moment.astimezone(vn).hour
        assert (EVEN if vn_hour % 2 == 0 else ODD) == expected
        assert route(f'{day}T20:00:00', zone) == expected


def test_mui_gio_khong_doi_gio_thi_khong_doi_calendar():
    """Arizona và Nam Phi không có DST → giờ VN cố định quanh năm."""
    for zone in ('America/Phoenix', 'Africa/Johannesburg', 'Asia/Ho_Chi_Minh'):
        assert len({route(f'2026-{m:02d}-15T20:00:00', zone) for m in range(1, 13)}) == 1


def test_lop_viet_nam_khong_doi_hanh_vi():
    assert route('2026-07-15T21:00:00', 'Asia/Ho_Chi_Minh') == ODD
    assert route('2026-07-15T22:00:00', 'Asia/Ho_Chi_Minh') == EVEN
    assert route('2026-01-15T21:00:00', 'Asia/Ho_Chi_Minh') == ODD
    assert route('2026-01-15T22:00:00', 'Asia/Ho_Chi_Minh') == EVEN


def test_khong_truyen_mui_gio_thi_hieu_chuoi_naive_theo_gio_vn():
    assert route('2026-07-15T21:00:00') == ODD
    assert route('2026-07-15T14:00:00Z') == ODD          # 14:00Z = 21:00 VN


def test_mui_gio_khong_hop_le_roi_ve_gio_vn_khong_no():
    for zone in ('Mars/Olympus', '', 'UTC+7', None):
        assert route('2026-07-15T14:00:00Z', zone) == ODD


# --------------------------------------------------------------------------
# 3. Đầu vào hỏng — phải mặc định an toàn, không nổ
# --------------------------------------------------------------------------

@pytest.mark.parametrize('bad', ['', None, '   ', 'not-a-datetime', '2026-13-45T99:99:99'])
def test_dau_vao_hong_roi_ve_calendar_le(bad):
    assert route(bad, 'America/Chicago') == ODD


def test_chuoi_chi_co_ngay_duoc_coi_la_nua_dem_dia_phuong():
    # 00:00 Chicago (CDT) = 12:00 VN → CHẴN
    assert route('2026-07-15', 'America/Chicago') == EVEN
    assert route('2026-07-15', 'Asia/Ho_Chi_Minh') == EVEN


# --------------------------------------------------------------------------
# 4. Tích hợp: create_event (sự kiện đơn) insert vào đúng calendar
# --------------------------------------------------------------------------

def created_calendar_of(class_info):
    """Chạy create_event thật, chỉ chặn hai tác dụng phụ ra ngoài (Google + file)."""
    captured = {}

    def fake_insert(calendar_id, event, idempotency_key=None):
        captured['calendar_id'] = calendar_id
        captured['event'] = event
        return {'id': 'evt-created'}

    with patch.object(crud, '_insert_event_idempotently', side_effect=fake_insert), \
            patch.object(crud, 'add_extra'):
        crud.create_event(class_info)

    return captured


def lop(start, end, zone, **extra):
    return {'name': 'Lop A', 'start': start, 'end': end, 'timezone': zone,
            'teacher': 'Co Lan', 'program': 'P1', **extra}


def test_create_event_lop_my_doi_calendar_theo_mua():
    truoc = created_calendar_of(
        lop('2026-10-26T20:00:00', '2026-10-26T21:00:00', 'America/Chicago'))
    sau = created_calendar_of(
        lop('2026-11-02T20:00:00', '2026-11-02T21:00:00', 'America/Chicago'))

    assert truoc['calendar_id'] == EVEN
    assert sau['calendar_id'] == ODD


def test_create_event_gan_dung_timezone_len_google():
    """Sự kiện phải mang theo timeZone của chính nó, giống Google Calendar."""
    event = created_calendar_of(
        lop('2026-07-15T09:00:00', '2026-07-15T10:00:00', 'America/Chicago'))['event']

    assert event['start']['timeZone'] == 'America/Chicago'
    assert event['end']['timeZone'] == 'America/Chicago'
    assert event['start']['dateTime'].startswith('2026-07-15T09:00:00-05:00')


def test_create_event_lop_viet_nam_khong_doi_hanh_vi():
    assert created_calendar_of(
        lop('2026-07-15T21:00:00', '2026-07-15T22:00:00', 'Asia/Ho_Chi_Minh'))['calendar_id'] == ODD
    assert created_calendar_of(
        lop('2026-07-15T22:00:00', '2026-07-15T23:00:00', 'Asia/Ho_Chi_Minh'))['calendar_id'] == EVEN


def test_create_event_don_khong_gan_ma_chuoi():
    """Sự kiện đơn không phải chuỗi → payload giữ nguyên như trước (không thêm property)."""
    event = created_calendar_of(
        lop('2026-07-15T21:00:00', '2026-07-15T22:00:00', 'Asia/Ho_Chi_Minh'))['event']
    assert 'extendedProperties' not in event
