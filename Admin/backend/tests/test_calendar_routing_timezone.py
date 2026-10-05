"""Calendar CHẴN/LẺ phải chọn theo GIỜ ĐỊA PHƯƠNG của sự kiện, không phải giờ VN.

Quy ước chẵn/lẻ lộ ra tận UI: sidebar có "Calendar Lẻ (Giờ lẻ)" / "Calendar Chẵn
(Giờ chẵn)" và bộ lọc calendarFilter, đều lọc theo calendar mà sự kiện ĐANG NẰM
(CalendarView.js). Nên chọn sai calendar = admin lọc ra sai lớp.

Bản cũ luôn quy giờ bắt đầu về múi giờ Việt Nam. Với lớp ở Mỹ, giờ VN xê dịch 1 tiếng
mỗi lần Mỹ đổi giờ, nên tính chẵn/lẻ của CÙNG một lớp lật qua lật lại theo mùa:

    9:00 Chicago = 21:00 VN (mùa hè, LẺ)  nhưng  22:00 VN (mùa đông, CHẴN)

Hậu quả:
  1. Google lưu cả chuỗi lặp trong MỘT calendar → nửa chuỗi sau mốc DST sai nhãn.
  2. Khi sửa sự kiện, hàm tính ra calendar khác chỗ đang nằm → kích hoạt move
     calendar vô cớ (với chuỗi lặp là insert lại + EXDATE, rất rủi ro).

Giờ địa phương bất biến qua DST — giống cách Google Calendar hiển thị sự kiện theo
timeZone của chính nó — nên quy ước luôn thoả mãn được.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytz

# Dùng lại loader sẵn có: nạp calendar_crud với google_calendar giả, không cần
# credentials và không gọi mạng. CALENDARS = {'odd': 'calendar-odd', ...}
from test_calendar_crud_performance import CRUD as crud
from recurrence_helper import expand_occurrences

ODD = 'calendar-odd'
EVEN = 'calendar-even'

CHICAGO = pytz.timezone('America/Chicago')


def route(dt_str, zone=None):
    return crud.determine_calendar_by_hour(dt_str, zone)


def hour_of(dt_str, zone=None):
    return crud.event_local_hour(dt_str, zone)


# --------------------------------------------------------------------------
# 1. event_local_hour — mọi dạng input cho cùng một giờ
# --------------------------------------------------------------------------

@pytest.mark.parametrize('text', [
    '2026-07-15T09:00:00',            # naive = giờ treo tường Chicago
    '2026-07-15T14:00:00Z',           # cùng mốc, viết theo UTC
    '2026-07-15T09:00:00-05:00',      # cùng mốc, kèm offset Chicago
    '2026-07-15T21:00:00+07:00',      # cùng mốc, gửi từ máy ở VN
])
def test_moi_dang_input_deu_ra_gio_dia_phuong_9(text):
    assert hour_of(text, 'America/Chicago') == 9


def test_gio_dia_phuong_bat_bien_qua_moc_dst():
    """Đây là cả vấn đề: 9:00 Chicago là 9 quanh năm, còn giờ VN thì 21 ↔ 22."""
    assert hour_of('2026-01-15T09:00:00', 'America/Chicago') == 9   # CST
    assert hour_of('2026-07-15T09:00:00', 'America/Chicago') == 9   # CDT

    # Giờ VN tương ứng thật sự đổi — chính là thứ làm parity lật.
    gio_vn_dong = hour_of('2026-01-15T09:00:00-06:00', 'Asia/Ho_Chi_Minh')
    gio_vn_he = hour_of('2026-07-15T09:00:00-05:00', 'Asia/Ho_Chi_Minh')
    assert (gio_vn_dong, gio_vn_he) == (22, 21)
    assert gio_vn_dong % 2 != gio_vn_he % 2


def test_datetime_object_cung_cho_gio_dia_phuong_dung():
    """Truyền datetime thay vì chuỗi không được âm thầm rơi về giờ UTC."""
    moment = CHICAGO.localize(datetime(2026, 7, 15, 9, 0))

    assert hour_of(moment, 'America/Chicago') == 9
    assert hour_of(moment.astimezone(timezone.utc), 'America/Chicago') == 9


@pytest.mark.parametrize('zone, expected', [
    ('America/New_York', 9),
    ('America/Chicago', 9),
    ('America/Denver', 9),
    ('America/Los_Angeles', 9),
    ('America/Phoenix', 9),
    ('Asia/Ho_Chi_Minh', 9),
    ('Europe/London', 9),
    ('Australia/Sydney', 9),
])
def test_naive_luon_la_gio_treo_tuong_cua_mui_gio_do(zone, expected):
    assert hour_of('2026-07-15T09:00:00', zone) == expected


def test_khong_truyen_mui_gio_thi_van_hieu_theo_gio_vn():
    """Tương thích ngược: caller cũ (1 tham số) giữ nguyên hành vi."""
    assert hour_of('2026-07-15T14:00:00Z') == 21          # 14:00Z = 21:00 VN
    assert crud.determine_calendar_by_hour('2026-07-15T14:00:00Z') == ODD


def test_mui_gio_khong_hop_le_roi_ve_gio_vn_khong_no():
    for zone in ('Mars/Olympus', '', 'UTC+7', None):
        assert hour_of('2026-07-15T14:00:00Z', zone) == 21


# --------------------------------------------------------------------------
# 2. determine_calendar_by_hour — lỗi cốt lõi của mục này
# --------------------------------------------------------------------------

def test_lop_my_giu_nguyen_calendar_qua_ca_hai_mua():
    """9:00 Chicago là giờ LẺ quanh năm.

    Bản cũ: mùa hè → VN 21h (LẺ, ODD), mùa đông → VN 22h (CHẴN, EVEN) — cùng một lớp
    nhưng rơi vào hai calendar khác nhau tuỳ mùa.
    """
    assert route('2026-01-15T09:00:00', 'America/Chicago') == ODD   # CST
    assert route('2026-07-15T09:00:00', 'America/Chicago') == ODD   # CDT
    assert route('2026-03-02T09:00:00', 'America/Chicago') == ODD   # trước DST
    assert route('2026-03-09T09:00:00', 'America/Chicago') == ODD   # sau DST


def test_lop_my_gio_chan_cung_on_dinh():
    for ngay in ('2026-01-15', '2026-07-15', '2026-03-02', '2026-03-09'):
        assert route(f'{ngay}T10:00:00', 'America/Chicago') == EVEN


@pytest.mark.parametrize('hour', list(range(24)))
def test_bang_parity_day_du_cho_moi_gio_trong_ngay(hour):
    expected = EVEN if hour % 2 == 0 else ODD

    # Cả hai mùa phải cho cùng kết quả — đó chính là tính bất biến cần có.
    assert route(f'2026-01-20T{hour:02d}:00:00', 'America/Chicago') == expected
    assert route(f'2026-07-20T{hour:02d}:00:00', 'America/Chicago') == expected


def test_gio_vn_van_giu_nguyen_hanh_vi_cu():
    """Lớp Việt Nam không có DST nên kết quả không đổi so với trước."""
    assert route('2026-07-15T21:00:00', 'Asia/Ho_Chi_Minh') == ODD
    assert route('2026-07-15T22:00:00', 'Asia/Ho_Chi_Minh') == EVEN
    assert route('2026-01-15T21:00:00', 'Asia/Ho_Chi_Minh') == ODD
    assert route('2026-01-15T22:00:00', 'Asia/Ho_Chi_Minh') == EVEN


@pytest.mark.parametrize('zone', [
    'America/New_York', 'America/Chicago', 'America/Denver',
    'America/Los_Angeles', 'Europe/London', 'Australia/Sydney',
])
def test_moi_mui_gio_co_dst_deu_on_dinh_qua_ca_nam(zone):
    """Quét 12 tháng: giờ treo tường không đổi thì calendar cũng không được đổi."""
    ket_qua = {
        route(f'2026-{thang:02d}-15T09:00:00', zone) for thang in range(1, 13)
    }
    assert ket_qua == {ODD}


# --------------------------------------------------------------------------
# 3. Chuỗi lặp: MỌI buổi phải cùng một calendar
# --------------------------------------------------------------------------

def series_calendars(start, end, zone, **rule):
    """Bung chuỗi lặp thật rồi hỏi calendar cho từng buổi."""
    class_info = {'timezone': zone, 'recurrence': rule.pop('recurrence', 'WEEKLY'),
                  'repeat_count': rule.pop('repeat_count', 12), **rule}
    occurrences, _ = expand_occurrences(start, end, class_info)
    return [route(s.isoformat(), zone) for s, _ in occurrences], occurrences


def test_ca_chuoi_lap_vat_qua_spring_forward_cung_mot_calendar():
    """Google lưu cả chuỗi trong 1 calendar → mọi buổi phải cùng parity."""
    calendars, occurrences = series_calendars(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00',
        'America/Chicago', byday=['MO'], repeat_count=8
    )

    assert len(occurrences) == 8
    assert set(calendars) == {ODD}


def test_ca_chuoi_lap_vat_qua_fall_back_cung_mot_calendar():
    calendars, occurrences = series_calendars(
        '2026-10-19T09:00:00', '2026-10-19T10:00:00',
        'America/Chicago', byday=['MO'], repeat_count=8
    )

    assert len(occurrences) == 8
    assert set(calendars) == {ODD}


def test_chuoi_daily_mot_nam_van_cung_mot_calendar():
    """Chuỗi dài đi qua CẢ HAI mốc DST trong năm."""
    calendars, occurrences = series_calendars(
        '2026-02-01T09:00:00', '2026-02-01T10:00:00',
        'America/Chicago', recurrence='DAILY', repeat_count=365
    )

    assert len(occurrences) == 365
    assert set(calendars) == {ODD}


def test_chuoi_gio_chan_cung_nhat_quan():
    calendars, _ = series_calendars(
        '2026-03-02T14:00:00', '2026-03-02T15:00:00',
        'America/Chicago', byday=['MO'], repeat_count=8
    )

    assert set(calendars) == {EVEN}


def test_chuoi_cua_ban_cau_nam_cung_nhat_quan():
    calendars, _ = series_calendars(
        '2026-03-30T09:00:00', '2026-03-30T10:00:00',
        'Australia/Sydney', byday=['MO'], repeat_count=8
    )

    assert set(calendars) == {ODD}


def test_ban_cu_that_su_lam_vo_chuoi():
    """Tái hiện logic CŨ để chứng minh chuỗi bị tách làm đôi."""
    vn = pytz.timezone('Asia/Ho_Chi_Minh')
    _, occurrences = series_calendars(
        '2026-03-02T09:00:00', '2026-03-02T10:00:00',
        'America/Chicago', byday=['MO'], repeat_count=8
    )

    cu = {
        EVEN if s.astimezone(vn).hour % 2 == 0 else ODD
        for s, _ in occurrences
    }

    assert cu == {ODD, EVEN}   # logic cũ: chuỗi rơi vào CẢ HAI calendar


# --------------------------------------------------------------------------
# 4. Không còn move calendar vô cớ khi sửa sự kiện
# --------------------------------------------------------------------------

def test_sua_lop_my_o_mua_khac_khong_sinh_move_calendar():
    """Tạo lớp vào mùa hè rồi dời sang một ngày mùa đông, giữ nguyên 9:00 sáng.

    update_event chỉ move calendar khi determine_calendar_by_hour ra kết quả khác chỗ
    đang nằm. Bản cũ ra EVEN ≠ ODD → move nhầm; với chuỗi lặp việc move là insert lại
    + EXDATE, rất rủi ro.
    """
    luc_tao = route('2026-07-15T09:00:00', 'America/Chicago')
    luc_sua = route('2026-12-15T09:00:00', 'America/Chicago')

    assert luc_tao == luc_sua == ODD


def test_doi_gio_that_su_van_phai_doi_calendar():
    """Không được khoá cứng: người dùng đổi 9:00 → 10:00 thì phải sang calendar kia."""
    assert route('2026-07-15T09:00:00', 'America/Chicago') == ODD
    assert route('2026-07-15T10:00:00', 'America/Chicago') == EVEN


def test_doi_mui_gio_co_the_doi_calendar():
    """Cùng một mốc thật, nhưng người dùng đổi múi giờ hiển thị → giờ địa phương khác."""
    assert route('2026-07-15T14:00:00Z', 'America/Chicago') == ODD          # 09:00
    assert route('2026-07-15T14:00:00Z', 'Asia/Ho_Chi_Minh') == ODD         # 21:00
    assert route('2026-07-15T14:00:00Z', 'America/New_York') == EVEN        # 10:00


# --------------------------------------------------------------------------
# 5. Đầu vào hỏng — phải mặc định an toàn, không nổ
# --------------------------------------------------------------------------

@pytest.mark.parametrize('bad', ['', None, '   ', 'not-a-datetime', '2026-13-45T99:99:99'])
def test_dau_vao_hong_roi_ve_calendar_le(bad):
    assert crud.determine_calendar_by_hour(bad, 'America/Chicago') == ODD


def test_dau_vao_hong_tra_none_o_event_local_hour():
    assert hour_of('not-a-datetime', 'America/Chicago') is None


def test_chuoi_chi_co_ngay_duoc_coi_la_nua_dem():
    assert hour_of('2026-07-15', 'America/Chicago') == 0
    assert route('2026-07-15', 'America/Chicago') == EVEN


# --------------------------------------------------------------------------
# 6. Tích hợp: create_event thật sự insert vào đúng calendar
# --------------------------------------------------------------------------

def created_calendar_of(class_info):
    """Chạy create_event thật, chỉ chặn hai tác dụng phụ ra ngoài (Google + file).

    Khoá lại phần NỐI DÂY: create_event phải truyền múi giờ của sự kiện xuống
    determine_calendar_by_hour, chứ không chỉ helper đúng là đủ.
    """
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


def test_create_event_lop_my_vao_calendar_le_ca_hai_mua():
    mua_he = created_calendar_of(
        lop('2026-07-15T09:00:00', '2026-07-15T10:00:00', 'America/Chicago'))
    mua_dong = created_calendar_of(
        lop('2026-01-15T09:00:00', '2026-01-15T10:00:00', 'America/Chicago'))

    assert mua_he['calendar_id'] == ODD
    assert mua_dong['calendar_id'] == ODD          # bản cũ: EVEN (VN 22h)


def test_create_event_gan_dung_timezone_len_google():
    """Sự kiện phải mang theo timeZone của chính nó, giống Google Calendar."""
    captured = created_calendar_of(
        lop('2026-07-15T09:00:00', '2026-07-15T10:00:00', 'America/Chicago'))

    event = captured['event']
    assert event['start']['timeZone'] == 'America/Chicago'
    assert event['end']['timeZone'] == 'America/Chicago'
    assert event['start']['dateTime'].startswith('2026-07-15T09:00:00-05:00')


def test_create_event_lop_viet_nam_khong_doi_hanh_vi():
    le = created_calendar_of(
        lop('2026-07-15T21:00:00', '2026-07-15T22:00:00', 'Asia/Ho_Chi_Minh'))
    chan = created_calendar_of(
        lop('2026-07-15T22:00:00', '2026-07-15T23:00:00', 'Asia/Ho_Chi_Minh'))

    assert le['calendar_id'] == ODD
    assert chan['calendar_id'] == EVEN


def test_create_event_chuoi_lap_my_vat_qua_dst_van_mot_calendar():
    """Master của chuỗi đặt ở đâu thì cả chuỗi ở đó — phải khớp parity mọi buổi."""
    class_info = lop('2026-03-02T09:00:00', '2026-03-02T10:00:00', 'America/Chicago',
                     recurrence='WEEKLY', byday=['MO'], repeat_count=8)
    captured = created_calendar_of(class_info)

    calendars, _ = series_calendars(
        class_info['start'], class_info['end'], 'America/Chicago',
        byday=['MO'], repeat_count=8)

    assert set(calendars) == {captured['calendar_id']} == {ODD}
