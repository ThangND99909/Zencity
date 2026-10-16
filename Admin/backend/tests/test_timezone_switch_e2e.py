"""E2E thêm / sửa / xóa khi đổi múi giờ VN ↔ Mỹ và qua mốc đổi giờ của Mỹ.

Chạy calendar_crud thật trên FakeCalendarService — KHÔNG gọi Google, KHÔNG chạm hai
lịch thật của khách hàng. Giờ gửi lên mô phỏng đúng `formatForBackend` của frontend
(CalendarView.js):
  - bình thường: giờ treo tường kèm offset của múi giờ đã chọn ("...-06:00");
  - khi người dùng đổi múi giờ trong form: quy về UTC ("...Z").

Bất biến kiểm tra sau MỌI thao tác:
  - mỗi buổi nằm đúng calendar theo giờ Việt Nam (chẵn → EVEN, lẻ → ODD);
  - không buổi nào bị trùng;
  - đúng danh sách buổi mong đợi (không thiếu, không thừa), đúng giờ treo tường.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from calendar_parity import parity_of
from fake_calendar import CALENDAR_EVEN, CALENDAR_ODD, FakeCalendarService, load_calendar_crud
from recurrence_helper import build_recurrence_rule

VN_TZ = 'Asia/Ho_Chi_Minh'
CHI_TZ = 'America/Chicago'
CAL_OF = {'even': CALENDAR_EVEN, 'odd': CALENDAR_ODD}
CODES = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']


@pytest.fixture
def env(tmp_path):
    service = FakeCalendarService()
    return service, load_calendar_crud(service, tmp_path / 'classes_extra.json')


# ---------------------------------------------------------------- helpers

def fe_time(local, zone, utc=False):
    """Giống formatForBackend: moment.tz(local, zone) → offset, hoặc → UTC 'Z'."""
    moment = datetime.fromisoformat(local).replace(tzinfo=ZoneInfo(zone))
    if utc:
        return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return moment.isoformat()


def payload(start, end, zone, byday=None, count=1, utc=False, **extra):
    info = {
        'name': 'Room 9E - Grade 2 Thanh Son - ASUS', 'classname': 'Room 9E', 'teacher': 'Ms. Wendy',
        'program': 'ASUS', 'zoom_link': 'https://zoom.example/j/9', 'meeting_id': '9', 'passcode': 'zen',
        'start': fe_time(start, zone, utc), 'end': fe_time(end, zone, utc), 'timezone': zone,
        'recurrence': 'WEEKLY' if byday else '', 'byday': list(byday or []), 'repeat_count': count,
        **extra,
    }
    rule = build_recurrence_rule(info)
    info['rrule'] = [rule] if rule else None
    return info


def sessions(service):
    """[(calendar_id, start_utc, event)] của mọi buổi đang hiển thị (instance + sự kiện đơn)."""
    found = [
        (calendar_id, datetime.fromisoformat(event['start']['dateTime']).astimezone(timezone.utc), event)
        for calendar_id, events in service.store.items()
        for event in events.values() if not event.get('recurrence')
    ]
    return sorted(found, key=lambda item: item[1])


def label(moment, zone):
    local = moment.astimezone(ZoneInfo(zone))
    return f"{local:%a %d/%m %H:%M}"


def schedule(service, zone=CHI_TZ):
    return [label(start, zone) for _, start, _ in sessions(service)]


def check_invariants(service):
    seen = set()
    for calendar_id, start, event in sessions(service):
        assert calendar_id == CAL_OF[parity_of(start)], \
            f"{event['id']} lúc {label(start, VN_TZ)} giờ VN nằm sai calendar"
        key = (event['summary'], start)
        assert key not in seen, f"trùng buổi {label(start, CHI_TZ)}"
        seen.add(key)
        end = datetime.fromisoformat(event['end']['dateTime']).astimezone(timezone.utc)
        assert end > start


def at(service, wanted, zone=CHI_TZ):
    for _, start, event in sessions(service):
        if label(start, zone) == wanted:
            return event['id']
    raise AssertionError(f"không có buổi {wanted} ({zone}); đang có {schedule(service, zone)}")


def edit(service, crud, event_label, info, mode, zone=CHI_TZ):
    info['edit_mode'] = mode
    return crud.update_event(at(service, event_label, zone), info)


# ================================================================ sự kiện đơn

def test_tao_su_kien_don_vn_roi_doi_sang_gio_my(env):
    service, crud = env
    crud.create_event(payload('2026-10-26T20:00', '2026-10-26T21:00', VN_TZ))
    assert [c for c, _, _ in sessions(service)] == [CALENDAR_EVEN]          # 20:00 VN

    # Đổi sang 20:00 Chicago ngày 02/11 (frontend gửi UTC 'Z' vì đổi múi giờ)
    edit(service, crud, 'Mon 26/10 20:00',
         payload('2026-11-02T20:00', '2026-11-02T21:00', CHI_TZ, utc=True), 'this', zone=VN_TZ)

    [(calendar_id, start, event)] = sessions(service)
    assert calendar_id == CALENDAR_ODD                                       # 09:00 VN
    assert label(start, CHI_TZ) == 'Mon 02/11 20:00'
    assert event['start']['timeZone'] == CHI_TZ
    check_invariants(service)


def test_tao_su_kien_don_gio_my_roi_doi_sang_gio_vn(env):
    service, crud = env
    crud.create_event(payload('2026-10-26T20:00', '2026-10-26T21:00', CHI_TZ))
    assert [c for c, _, _ in sessions(service)] == [CALENDAR_EVEN]          # 08:00 VN

    edit(service, crud, 'Mon 26/10 20:00',
         payload('2026-10-27T21:00', '2026-10-27T22:00', VN_TZ, utc=True), 'this')

    [(calendar_id, start, event)] = sessions(service)
    assert calendar_id == CALENDAR_ODD and label(start, VN_TZ) == 'Tue 27/10 21:00'
    assert event['start']['timeZone'] == VN_TZ
    check_invariants(service)


def test_doi_ngay_su_kien_don_qua_moc_doi_gio_chuyen_calendar(env):
    service, crud = env
    created = crud.create_event(payload('2026-10-26T20:00', '2026-10-26T21:00', CHI_TZ))

    edit(service, crud, 'Mon 26/10 20:00', payload('2026-11-02T20:00', '2026-11-02T21:00', CHI_TZ), 'this')

    [(calendar_id, start, event)] = sessions(service)
    assert (calendar_id, label(start, CHI_TZ)) == (CALENDAR_ODD, 'Mon 02/11 20:00')
    assert event['id'] == created['id']                                     # move giữ nguyên id
    check_invariants(service)


def test_sua_su_kien_don_cung_parity_cap_nhat_tai_cho(env):
    service, crud = env
    created = crud.create_event(payload('2026-11-02T20:00', '2026-11-02T21:00', CHI_TZ))

    info = payload('2026-11-02T20:00', '2026-11-02T21:30', CHI_TZ, teacher='Ms. Lan')
    edit(service, crud, 'Mon 02/11 20:00', info, 'this')

    [(calendar_id, _, event)] = sessions(service)
    assert calendar_id == CALENDAR_ODD and event['id'] == created['id']
    assert 'Ms. Lan' in event['description']
    assert event['end']['dateTime'].startswith('2026-11-02T21:30:00-06:00')


def test_xoa_su_kien_don(env):
    service, crud = env
    crud.create_event(payload('2026-11-02T20:00', '2026-11-02T21:00', CHI_TZ))
    result = crud.delete_event(at(service, 'Mon 02/11 20:00'), delete_mode='this')
    assert result['status'] == 'deleted' and service.total_events() == 0


# ================================================================ chuỗi lặp: tạo

@pytest.mark.parametrize('zone, start, before_cal, after_cal', [
    ('America/New_York', '2026-10-19T20:00', CALENDAR_ODD, CALENDAR_EVEN),      # 07h → 08h VN
    ('America/Chicago', '2026-10-19T20:00', CALENDAR_EVEN, CALENDAR_ODD),       # 08h → 09h VN
    ('America/Denver', '2026-10-19T20:00', CALENDAR_ODD, CALENDAR_EVEN),        # 09h → 10h VN
    ('America/Los_Angeles', '2026-10-19T20:00', CALENDAR_EVEN, CALENDAR_ODD),   # 10h → 11h VN
])
def test_tao_chuoi_cac_mui_gio_my_qua_moc_01_11(env, zone, start, before_cal, after_cal):
    service, crud = env
    end = start.replace('T20:00', 'T21:00')
    crud.create_event(payload(start, end, zone, byday=['MO', 'WE', 'FR'], count=12), idempotency_key='k')

    found = sessions(service)
    assert len(found) == 12
    assert {label(s, zone)[-5:] for _, s, _ in found} == {'20:00'}         # giờ treo tường giữ nguyên
    assert [c for c, _, _ in found] == [before_cal] * 6 + [after_cal] * 6
    check_invariants(service)


def test_tao_chuoi_qua_moc_mua_xuan_2027(env):
    """Mỹ vào giờ mùa hè CN 14/03/2027: 20:00 Chicago từ 09h VN (ODD) về 08h VN (EVEN)."""
    service, crud = env
    crud.create_event(payload('2027-03-01T20:00', '2027-03-01T21:00', CHI_TZ, byday=['MO'], count=5))

    assert [(label(s, CHI_TZ), c) for c, s, _ in sessions(service)] == [
        ('Mon 01/03 20:00', CALENDAR_ODD), ('Mon 08/03 20:00', CALENDAR_ODD),
        ('Mon 15/03 20:00', CALENDAR_EVEN), ('Mon 22/03 20:00', CALENDAR_EVEN),
        ('Mon 29/03 20:00', CALENDAR_EVEN),
    ]
    check_invariants(service)


def test_tao_chuoi_ca_nam_hoc_qua_hai_moc(env):
    service, crud = env
    crud.create_event(payload('2026-09-07T19:00', '2026-09-07T20:00', CHI_TZ, byday=['MO', 'TH'], count=80))

    found = sessions(service)
    assert len(found) == 80
    masters = [e for events in service.store.values() for e in events.values() if e.get('recurrence')]
    assert len(masters) == 3                                                # hè → đông → hè
    check_invariants(service)


def test_tao_chuoi_gio_vn_khong_tach_va_giu_luat_goc(env):
    service, crud = env
    crud.create_event(payload('2026-10-19T20:00', '2026-10-19T21:00', VN_TZ, byday=['MO', 'WE'], count=20))

    masters = [e for events in service.store.values() for e in events.values() if e.get('recurrence')]
    assert len(masters) == 1
    assert masters[0]['recurrence'] == ['RRULE:FREQ=WEEKLY;COUNT=20;BYDAY=MO,WE;INTERVAL=1']
    assert len(sessions(service)) == 20
    check_invariants(service)


# ================================================================ chuỗi lặp: sửa + đổi múi giờ

def test_chuoi_vn_sua_tu_buoi_3_doi_sang_gio_my(env):
    """VN 20:00 thứ 2/4 → từ buổi 3 đổi sang 20:00 Chicago (vắt qua 01/11)."""
    service, crud = env
    crud.create_event(payload('2026-10-19T20:00', '2026-10-19T21:00', VN_TZ, byday=['MO', 'WE'], count=8))

    edit(service, crud, 'Mon 26/10 20:00',
         payload('2026-10-26T20:00', '2026-10-26T21:00', CHI_TZ, byday=['MO', 'WE'], count=6, utc=True),
         'following', zone=VN_TZ)

    found = sessions(service)
    vn_part = [label(s, VN_TZ) for _, s, e in found if e['start'].get('timeZone') == VN_TZ]
    us_part = [(label(s, CHI_TZ), c) for c, s, e in found if e['start'].get('timeZone') == CHI_TZ]
    assert vn_part == ['Mon 19/10 20:00', 'Wed 21/10 20:00']
    assert us_part == [
        ('Mon 26/10 20:00', CALENDAR_EVEN), ('Wed 28/10 20:00', CALENDAR_EVEN),
        ('Mon 02/11 20:00', CALENDAR_ODD), ('Wed 04/11 20:00', CALENDAR_ODD),
        ('Mon 09/11 20:00', CALENDAR_ODD), ('Wed 11/11 20:00', CALENDAR_ODD),
    ]
    check_invariants(service)


def test_chuoi_my_tach_doan_sua_tat_ca_tu_dau_doi_sang_gio_vn(env):
    """Chuỗi Chicago đã tách 2 đoạn → sửa từ buổi đầu sang 19:00 VN: cả hai đoạn cũ phải biến mất."""
    service, crud = env
    crud.create_event(payload('2026-10-19T20:00', '2026-10-19T21:00', CHI_TZ, byday=['MO', 'WE', 'FR'], count=12),
                      idempotency_key='k')

    edit(service, crud, 'Mon 19/10 20:00',
         payload('2026-10-20T19:00', '2026-10-20T20:00', VN_TZ, byday=['TU', 'TH'], count=8, utc=True),
         'following')

    found = sessions(service)
    assert len(found) == 8
    assert {e['start'].get('timeZone') for _, _, e in found} == {VN_TZ}
    assert {c for c, _, _ in found} == {CALENDAR_ODD}                       # 19h VN
    assert schedule(service, VN_TZ)[:2] == ['Tue 20/10 19:00', 'Thu 22/10 19:00']
    check_invariants(service)


def test_chuoi_my_sua_tu_doan_sau_doi_gio_giu_nguyen_doan_dau(env):
    service, crud = env
    crud.create_event(payload('2026-10-19T20:00', '2026-10-19T21:00', CHI_TZ, byday=['MO', 'WE', 'FR'], count=12))

    edit(service, crud, 'Wed 04/11 20:00',
         payload('2026-11-04T18:00', '2026-11-04T19:00', CHI_TZ, byday=['MO', 'WE', 'FR'], count=5),
         'following')

    assert [(label(s, CHI_TZ), c) for c, s, _ in sessions(service)] == [
        ('Mon 19/10 20:00', CALENDAR_EVEN), ('Wed 21/10 20:00', CALENDAR_EVEN),
        ('Fri 23/10 20:00', CALENDAR_EVEN), ('Mon 26/10 20:00', CALENDAR_EVEN),
        ('Wed 28/10 20:00', CALENDAR_EVEN), ('Fri 30/10 20:00', CALENDAR_EVEN),
        ('Mon 02/11 20:00', CALENDAR_ODD),
        ('Wed 04/11 18:00', CALENDAR_ODD), ('Fri 06/11 18:00', CALENDAR_ODD),     # 07:00 VN
        ('Mon 09/11 18:00', CALENDAR_ODD), ('Wed 11/11 18:00', CALENDAR_ODD),
        ('Fri 13/11 18:00', CALENDAR_ODD),
    ]
    check_invariants(service)


def test_sua_mot_buoi_cua_chuoi_my_sang_gio_vn(env):
    service, crud = env
    crud.create_event(payload('2026-10-19T20:00', '2026-10-19T21:00', CHI_TZ, byday=['MO', 'WE', 'FR'], count=12))

    edit(service, crud, 'Fri 06/11 20:00',
         payload('2026-11-07T20:00', '2026-11-07T21:00', VN_TZ, utc=True), 'this')

    found = sessions(service)
    assert len(found) == 12
    assert 'Fri 06/11 20:00' not in schedule(service)
    [(calendar_id, start, event)] = [(c, s, e) for c, s, e in found if e['start'].get('timeZone') == VN_TZ]
    assert (calendar_id, label(start, VN_TZ)) == (CALENDAR_EVEN, 'Sat 07/11 20:00')
    check_invariants(service)


def test_sua_mot_buoi_chuoi_vn_sang_gio_my_sau_moc(env):
    service, crud = env
    crud.create_event(payload('2026-10-19T21:00', '2026-10-19T22:00', VN_TZ, byday=['MO'], count=4))

    # 21:00 VN (ODD) → 19:00 Chicago ngày 02/11 = 08:00 VN 03/11 (EVEN)
    edit(service, crud, 'Mon 02/11 21:00',
         payload('2026-11-02T19:00', '2026-11-02T20:00', CHI_TZ, utc=True), 'this', zone=VN_TZ)

    found = sessions(service)
    assert len(found) == 4
    moved = [(c, s) for c, s, e in found if e['start'].get('timeZone') == CHI_TZ]
    assert [(c, label(s, CHI_TZ)) for c, s in moved] == [(CALENDAR_EVEN, 'Mon 02/11 19:00')]
    check_invariants(service)


def test_su_kien_don_chuyen_thanh_chuoi_gio_my_qua_moc(env):
    """edit_mode='all' trên sự kiện đơn = xóa đơn, tạo chuỗi mới (cũng phải tách đoạn)."""
    service, crud = env
    crud.create_event(payload('2026-10-19T20:00', '2026-10-19T21:00', VN_TZ))

    edit(service, crud, 'Mon 19/10 20:00',
         payload('2026-10-26T20:00', '2026-10-26T21:00', CHI_TZ, byday=['MO'], count=4, utc=True),
         'all', zone=VN_TZ)

    assert [(label(s, CHI_TZ), c) for c, s, _ in sessions(service)] == [
        ('Mon 26/10 20:00', CALENDAR_EVEN), ('Mon 02/11 20:00', CALENDAR_ODD),
        ('Mon 09/11 20:00', CALENDAR_ODD), ('Mon 16/11 20:00', CALENDAR_ODD),
    ]
    check_invariants(service)


# ================================================================ xóa sau khi đã đổi múi giờ

def test_xoa_tat_ca_sau_khi_sua_following_sang_gio_my(env):
    service, crud = env
    crud.create_event(payload('2026-10-19T20:00', '2026-10-19T21:00', VN_TZ, byday=['MO', 'WE'], count=8))
    edit(service, crud, 'Mon 26/10 20:00',
         payload('2026-10-26T20:00', '2026-10-26T21:00', CHI_TZ, byday=['MO', 'WE'], count=6, utc=True),
         'following', zone=VN_TZ)

    # Xóa "tất cả" từ một buổi của chuỗi MỚI (đoạn sau 01/11): xóa cả 2 đoạn mới,
    # giữ phần chuỗi VN trước đó (giống Google: sửa 'following' tạo chuỗi riêng).
    crud.delete_event(at(service, 'Mon 09/11 20:00'), delete_mode='all')

    assert schedule(service, VN_TZ) == ['Mon 19/10 20:00', 'Wed 21/10 20:00']
    check_invariants(service)


def test_xoa_tu_buoi_nay_tro_di_sau_khi_doi_gio(env):
    service, crud = env
    crud.create_event(payload('2026-10-19T20:00', '2026-10-19T21:00', VN_TZ, byday=['MO', 'WE'], count=8))
    edit(service, crud, 'Mon 26/10 20:00',
         payload('2026-10-26T20:00', '2026-10-26T21:00', CHI_TZ, byday=['MO', 'WE'], count=6, utc=True),
         'following', zone=VN_TZ)

    crud.delete_event(at(service, 'Wed 28/10 20:00'), delete_mode='following')

    assert schedule(service) == [
        label(datetime(2026, 10, 19, 13, tzinfo=timezone.utc), CHI_TZ),
        label(datetime(2026, 10, 21, 13, tzinfo=timezone.utc), CHI_TZ),
        'Mon 26/10 20:00',
    ]
    check_invariants(service)


def test_xoa_mot_buoi_sau_moc_giu_nguyen_phan_con_lai(env):
    service, crud = env
    crud.create_event(payload('2026-10-19T20:00', '2026-10-19T21:00', CHI_TZ, byday=['MO', 'WE', 'FR'], count=12))
    before = schedule(service)

    crud.delete_event(at(service, 'Mon 02/11 20:00'), delete_mode='this')

    assert schedule(service) == [x for x in before if x != 'Mon 02/11 20:00']
    check_invariants(service)


# ================================================================ chuỗi cũ nhập tay (không có mã chuỗi)

def test_chuoi_nhap_tay_sua_mot_buoi_khong_dung_buoi_khac(env):
    """Dữ liệu thật hiện nay do nhân viên nhập tay (không có zencitySeriesId)."""
    service, crud = env
    service.seed_series(CALENDAR_EVEN, 'manual1', 'Room 2K - Martin Mai - ASUS',
                        '2026-10-20T20:00:00+07:00', count=5)
    before = len(sessions(service))

    instance = service.instance_ids(CALENDAR_EVEN, 'manual1')[2]
    info = payload('2026-10-22T21:00', '2026-10-22T22:00', VN_TZ)
    info['edit_mode'] = 'this'
    crud.update_event(instance, info)

    assert len(sessions(service)) == before
    assert len(service.instance_ids(CALENDAR_EVEN, 'manual1')) == 4
    check_invariants(service)
