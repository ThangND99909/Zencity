"""Chuỗi lặp vắt qua mốc đổi giờ Mỹ phải được tách đoạn, mỗi đoạn đúng calendar theo giờ VN.

Yêu cầu của khách hàng (Mỹ hết giờ mùa hè CN 01/11/2026): lớp 20:00 Chicago là 08:00 VN
(EVEN) đến hết 01/11, từ 02/11 là 09:00 VN nên phải nằm ở ODD.

Google lưu cả chuỗi lặp trong MỘT calendar, nên app tạo nhiều đoạn (mỗi đoạn một chuỗi
riêng) và liên kết chúng bằng extendedProperties.private.zencitySeriesId để sửa/xóa
"following"/"all" xử lý trọn chuỗi. Các test E2E chạy calendar_crud thật trên
FakeCalendarService — không gọi Google, không chạm hai lịch thật.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from calendar_parity import (
    MAX_SERIES_OCCURRENCES,
    parity_of,
    plan_series_segments,
    segment_recurrence,
    series_occurrence_starts,
)
from fake_calendar import CALENDAR_EVEN, CALENDAR_ODD, FakeCalendarService, http_error, load_calendar_crud
from recurrence_helper import build_recurrence_rule

VN = ZoneInfo('Asia/Ho_Chi_Minh')
CT = ZoneInfo('America/Chicago')
CAL_OF = {'even': CALENDAR_EVEN, 'odd': CALENDAR_ODD}


def utc(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00')).astimezone(timezone.utc)


def ct_label(moment):
    return moment.astimezone(CT).strftime('%a %d/%m %H:%M')


# ==========================================================================
# 1. Ngữ nghĩa lặp đã kiểm chứng trên Google Calendar thật (16/10/2026)
# ==========================================================================
# Kết quả events.instances() thật trên calendar riêng của service account (đã xóa sau test).
GOOGLE_VERIFIED = [
    (  # 20:00 Chicago giữ nguyên giờ treo tường qua mốc 01/11
        '2026-10-26T20:00:00', ['RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=3'],
        ['2026-10-27T01:00:00Z', '2026-11-03T02:00:00Z', '2026-11-10T02:00:00Z'],
    ),
    (  # UNTIL bao gồm chính buổi trùng mốc
        '2026-10-19T20:00:00', ['RRULE:FREQ=WEEKLY;BYDAY=MO;UNTIL=20261027T010000Z'],
        ['2026-10-20T01:00:00Z', '2026-10-27T01:00:00Z'],
    ),
    (  # DTSTART (thứ 2) không khớp BYDAY vẫn là một buổi; COUNT chỉ đếm buổi khớp luật
        '2026-10-19T20:00:00', ['RRULE:FREQ=WEEKLY;BYDAY=TU,TH;COUNT=3'],
        ['2026-10-20T01:00:00Z', '2026-10-21T01:00:00Z', '2026-10-23T01:00:00Z', '2026-10-28T01:00:00Z'],
    ),
]


@pytest.mark.parametrize('start, recurrence, google', GOOGLE_VERIFIED)
def test_bung_chuoi_khop_dung_google_that(start, recurrence, google):
    expected = [utc(value) for value in google]
    assert series_occurrence_starts(start, 'America/Chicago', recurrence) == expected


@pytest.mark.parametrize('start, recurrence, google', GOOGLE_VERIFIED)
def test_calendar_gia_cung_khop_google_that(start, recurrence, google):
    """Calendar giả dùng cho E2E phải hành xử như Google, không thì test vô nghĩa."""
    master = {
        'id': 'm', 'recurrence': recurrence,
        'start': {'dateTime': datetime.fromisoformat(start).replace(tzinfo=CT).isoformat(),
                  'timeZone': 'America/Chicago'},
    }
    produced = [moment.astimezone(timezone.utc) for moment in FakeCalendarService.occurrences(master)]
    assert produced == [utc(value) for value in google]


# ==========================================================================
# 2. Lập kế hoạch tách đoạn (calendar_parity)
# ==========================================================================

MWF_12 = ['RRULE:FREQ=WEEKLY;COUNT=12;BYDAY=MO,WE,FR;INTERVAL=1']


def test_vi_du_khach_hang_tach_dung_tai_moc_doi_gio():
    segments = plan_series_segments('2026-10-19T20:00:00', 'America/Chicago', MWF_12)

    assert [s.parity for s in segments] == ['even', 'odd']
    assert [ct_label(m) for m in segments[0].starts] == [
        'Mon 19/10 20:00', 'Wed 21/10 20:00', 'Fri 23/10 20:00',
        'Mon 26/10 20:00', 'Wed 28/10 20:00', 'Fri 30/10 20:00']
    assert [ct_label(m) for m in segments[1].starts] == [
        'Mon 02/11 20:00', 'Wed 04/11 20:00', 'Fri 06/11 20:00',
        'Mon 09/11 20:00', 'Wed 11/11 20:00', 'Fri 13/11 20:00']


def test_buoi_toi_chu_nhat_01_11_thuoc_doan_sau():
    segments = plan_series_segments(
        '2026-10-25T19:00:00', 'America/Chicago', ['RRULE:FREQ=WEEKLY;COUNT=3;BYDAY=SU'])
    assert [(s.parity, [ct_label(m) for m in s.starts]) for s in segments] == [
        ('odd', ['Sun 25/10 19:00']),                       # 07:00 VN
        ('even', ['Sun 01/11 19:00', 'Sun 08/11 19:00']),   # 08:00 VN
    ]


def test_chuoi_khong_vat_qua_moc_chi_mot_doan():
    segments = plan_series_segments('2026-11-02T20:00:00', 'America/Chicago', MWF_12)
    assert len(segments) == 1 and segments[0].parity == 'odd'


@pytest.mark.parametrize('zone', ['Asia/Ho_Chi_Minh', 'Africa/Johannesburg', 'America/Phoenix'])
def test_mui_gio_khong_doi_gio_khong_bao_gio_tach(zone):
    daily_year = ['RRULE:FREQ=DAILY;COUNT=400;INTERVAL=1']
    assert len(plan_series_segments('2026-01-05T20:00:00', zone, daily_year)) == 1


@pytest.mark.parametrize('zone', ['America/Chicago', 'America/New_York', 'America/Los_Angeles', 'Europe/London'])
@pytest.mark.parametrize('hour', [6, 11, 17, 18, 19, 20, 21, 22])
def test_tach_doan_khong_mat_khong_thua_buoi_va_dung_parity(zone, hour):
    """Một năm hằng ngày (đi qua cả hai mốc đổi giờ): hợp các đoạn = chuỗi gốc."""
    rule = ['RRULE:FREQ=DAILY;COUNT=400;INTERVAL=1']
    start = f'2026-01-05T{hour:02d}:30:00'
    segments = plan_series_segments(start, zone, rule)
    joined = [moment for segment in segments for moment in segment.starts]

    assert joined == series_occurrence_starts(start, zone, rule)
    assert len(joined) == 400
    for segment in segments:
        assert all(parity_of(moment) == segment.parity for moment in segment.starts)
    for before, after in zip(segments, segments[1:]):
        assert before.parity != after.parity and before.last < after.first
    assert len(segments) == 3   # mùa đông → mùa hè → mùa đông


def test_luat_lap_cua_doan_ket_thuc_bang_until():
    segments = plan_series_segments('2026-10-19T20:00:00', 'America/Chicago', MWF_12)
    lines = segment_recurrence(MWF_12 + ['EXDATE;TZID=America/Chicago:20261021T200000'], segments[0])

    assert lines[0] == 'RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;INTERVAL=1;UNTIL=20261031T010000Z'
    assert lines[1] == 'EXDATE;TZID=America/Chicago:20261021T200000'   # dòng khác giữ nguyên


def test_chuoi_vo_han_bi_tu_choi():
    with pytest.raises(ValueError, match='end'):
        plan_series_segments('2026-10-19T20:00:00', 'America/Chicago', ['RRULE:FREQ=WEEKLY;BYDAY=MO'])


def test_chuoi_qua_dai_bi_tu_choi():
    rule = [f'RRULE:FREQ=DAILY;COUNT={MAX_SERIES_OCCURRENCES + 5}']
    with pytest.raises(ValueError, match='longer'):
        plan_series_segments('2026-01-05T20:00:00', 'America/Chicago', rule)


# ==========================================================================
# 3. E2E: calendar_crud thật trên Google Calendar giả
# ==========================================================================

@pytest.fixture
def calendar(tmp_path):
    service = FakeCalendarService()
    crud = load_calendar_crud(service, tmp_path / 'classes_extra.json')
    return service, crud


def class_info(start='2026-10-19T20:00:00', end='2026-10-19T21:00:00', byday=('MO', 'WE', 'FR'),
               count=12, zone='America/Chicago', **extra):
    info = {
        'name': 'Room 8E - Grade 3 Martin Mai - ASUS', 'classname': 'Room 8E', 'teacher': 'Mr. Rudi',
        'program': 'ASUS', 'zoom_link': 'https://zoom.example/j/1', 'meeting_id': '1', 'passcode': 'zen',
        'start': start, 'end': end, 'timezone': zone,
        'recurrence': 'WEEKLY' if byday else '', 'byday': list(byday or []), 'repeat_count': count,
        **extra,
    }
    rule = build_recurrence_rule(info)
    info['rrule'] = [rule] if rule else None
    return info


def occurrences(service):
    """Mọi buổi đang hiển thị: [(calendar_id, start_utc, event)] — instance + sự kiện đơn."""
    found = []
    for calendar_id, events in service.store.items():
        for event in events.values():
            if event.get('recurrence'):
                continue   # master: Google hiển thị qua instance của nó
            found.append((calendar_id, utc(event['start']['dateTime']), event))
    return sorted(found, key=lambda item: item[1])


def masters(service):
    return {
        event_id: (calendar_id, event)
        for calendar_id, events in service.store.items()
        for event_id, event in events.items() if event.get('recurrence')
    }


def assert_all_in_right_calendar(service):
    for calendar_id, start, event in occurrences(service):
        assert calendar_id == CAL_OF[parity_of(start)], f"{event['id']} @ {ct_label(start)} sai calendar"


def assert_no_duplicates(service):
    starts = [(event['summary'], start) for _, start, event in occurrences(service)]
    assert len(starts) == len(set(starts)), "có buổi bị trùng"


def schedule(service):
    return [(ct_label(start), calendar_id) for calendar_id, start, _ in occurrences(service)]


EXPECTED_MWF_12 = [
    ('Mon 19/10 20:00', CALENDAR_EVEN), ('Wed 21/10 20:00', CALENDAR_EVEN),
    ('Fri 23/10 20:00', CALENDAR_EVEN), ('Mon 26/10 20:00', CALENDAR_EVEN),
    ('Wed 28/10 20:00', CALENDAR_EVEN), ('Fri 30/10 20:00', CALENDAR_EVEN),
    ('Mon 02/11 20:00', CALENDAR_ODD), ('Wed 04/11 20:00', CALENDAR_ODD),
    ('Fri 06/11 20:00', CALENDAR_ODD), ('Mon 09/11 20:00', CALENDAR_ODD),
    ('Wed 11/11 20:00', CALENDAR_ODD), ('Fri 13/11 20:00', CALENDAR_ODD),
]


def create_mwf(crud, key='req-1', **overrides):
    return crud.create_event(class_info(**overrides), idempotency_key=key)


# ---------------- CREATE ----------------

def test_tao_chuoi_vat_qua_moc_doi_gio_tach_dung_hai_calendar(calendar):
    service, crud = calendar
    result = create_mwf(crud)

    assert schedule(service) == EXPECTED_MWF_12
    assert_all_in_right_calendar(service)
    assert_no_duplicates(service)

    found = masters(service)
    assert len(found) == 2
    series_ids = {event['extendedProperties']['private']['zencitySeriesId'] for _, event in found.values()}
    assert len(series_ids) == 1
    assert [s['calendar'] for s in result['_segments']] == ['even', 'odd']
    # Giờ kết thúc vẫn 21:00 Chicago sau mốc đổi giờ.
    for _, start, event in occurrences(service):
        assert (utc(event['end']['dateTime']) - start).total_seconds() == 3600


def test_tao_chuoi_luu_extra_cho_moi_doan(calendar):
    service, crud = calendar
    create_mwf(crud)
    extra = crud.load_extra()
    for event_id, (calendar_id, _) in masters(service).items():
        assert extra[event_id]['calendar_id'] == calendar_id
        assert extra[event_id]['meeting_id'] == '1'


def test_tao_chuoi_khong_vat_qua_moc_giu_nguyen_luat_goc(calendar):
    service, crud = calendar
    result = create_mwf(crud, start='2026-11-02T20:00:00', end='2026-11-02T21:00:00')

    [(calendar_id, master)] = masters(service).values()
    assert calendar_id == CALENDAR_ODD
    assert master['recurrence'] == ['RRULE:FREQ=WEEKLY;COUNT=12;BYDAY=MO,WE,FR;INTERVAL=1']
    assert '_segments' not in result
    assert len(occurrences(service)) == 12
    assert_all_in_right_calendar(service)


def test_tao_su_kien_don_theo_gio_vn(calendar):
    service, crud = calendar
    crud.create_event(class_info(start='2026-11-02T20:00:00', end='2026-11-02T21:00:00', byday=None))
    crud.create_event(class_info(start='2026-10-26T20:00:00', end='2026-10-26T21:00:00', byday=None))
    assert schedule(service) == [('Mon 26/10 20:00', CALENDAR_EVEN), ('Mon 02/11 20:00', CALENDAR_ODD)]


def test_lop_viet_nam_khong_bi_tach(calendar):
    service, crud = calendar
    create_mwf(crud, start='2026-10-19T20:00:00', end='2026-10-19T21:00:00', zone='Asia/Ho_Chi_Minh')
    assert len(masters(service)) == 1
    assert {calendar_id for calendar_id, _, _ in occurrences(service)} == {CALENDAR_EVEN}


def test_gui_lai_cung_idempotency_key_khong_sinh_ban_trung(calendar):
    service, crud = calendar
    first = create_mwf(crud, key='same-key')
    second = create_mwf(crud, key='same-key')

    assert [s['id'] for s in first['_segments']] == [s['id'] for s in second['_segments']]
    assert len(masters(service)) == 2
    assert schedule(service) == EXPECTED_MWF_12


def test_loi_khi_tao_doan_sau_thi_go_doan_truoc_khong_de_chuoi_khuyet(calendar):
    service, crud = calendar
    real_insert = service.insert
    calls = {'n': 0}

    def flaky_insert(calendar_id, body):
        calls['n'] += 1
        if calls['n'] == 2:
            raise http_error(400, 'Bad Request')
        return real_insert(calendar_id, body)

    service.insert = flaky_insert
    with pytest.raises(Exception):
        create_mwf(crud)

    assert service.total_events() == 0


def test_khong_coi_su_kien_da_xoa_la_tao_thanh_cong(calendar):
    """Tạo → xóa → gửi lại cùng key: phải báo lỗi, không im lặng trả về bản đã hủy."""
    service, crud = calendar
    created = crud.create_event(class_info(byday=None), idempotency_key='k-deleted')
    service.store[CALENDAR_EVEN][created['id']]['status'] = 'cancelled'
    real_insert = service.insert

    def conflict_insert(calendar_id, body):
        if body.get('id') == created['id']:
            raise http_error(409, 'Conflict')
        return real_insert(calendar_id, body)

    service.insert = conflict_insert
    with pytest.raises(crud.IdempotencyConflictError):
        crud.create_event(class_info(byday=None), idempotency_key='k-deleted')


# ---------------- DELETE ----------------

def instance_at(service, label):
    for calendar_id, start, event in occurrences(service):
        if ct_label(start) == label:
            return event['id']
    raise AssertionError(f'không có buổi {label}')


def test_xoa_tat_ca_tu_doan_sau_xoa_ca_hai_doan(calendar):
    service, crud = calendar
    create_mwf(crud)
    result = crud.delete_event(instance_at(service, 'Wed 04/11 20:00'), delete_mode='all')

    assert result['status'] == 'deleted' and result['deleted_segments'] == 1
    assert service.total_events() == 0


def test_xoa_tat_ca_tu_doan_dau_xoa_ca_hai_doan(calendar):
    service, crud = calendar
    create_mwf(crud)
    crud.delete_event(instance_at(service, 'Mon 19/10 20:00'), delete_mode='all')
    assert service.total_events() == 0


def test_xoa_tu_buoi_nay_tro_di_o_doan_dau_xoa_luon_doan_sau(calendar):
    service, crud = calendar
    create_mwf(crud)
    result = crud.delete_event(instance_at(service, 'Fri 23/10 20:00'), delete_mode='following')

    assert result['deleted_segments'] == 1
    assert schedule(service) == EXPECTED_MWF_12[:2]


def test_xoa_tu_buoi_nay_tro_di_o_doan_sau_giu_nguyen_doan_dau(calendar):
    service, crud = calendar
    create_mwf(crud)
    crud.delete_event(instance_at(service, 'Fri 06/11 20:00'), delete_mode='following')
    assert schedule(service) == EXPECTED_MWF_12[:8]


def test_xoa_mot_buoi_khong_dung_doan_khac(calendar):
    service, crud = calendar
    create_mwf(crud)
    crud.delete_event(instance_at(service, 'Mon 09/11 20:00'), delete_mode='this')
    assert schedule(service) == EXPECTED_MWF_12[:9] + EXPECTED_MWF_12[10:]


def test_chuoi_cu_khong_co_ma_chuoi_xoa_tat_ca_nhu_truoc(calendar):
    """Dữ liệu nhập tay trên Google (không có zencitySeriesId) — chỉ xóa đúng master đó."""
    service, crud = calendar
    service.seed_series(CALENDAR_ODD, 'legacyA', 'Lop A', '2026-10-19T19:00:00+07:00', count=3)
    service.seed_series(CALENDAR_EVEN, 'legacyB', 'Lop B', '2026-10-19T20:00:00+07:00', count=3)

    crud.delete_event('legacyA', delete_mode='all')

    assert set(masters(service)) == {'legacyB'}
    assert len(service.instance_ids(CALENDAR_EVEN, 'legacyB')) == 3


def test_xoa_tat_ca_khi_master_da_mat_khong_doan_mo(calendar):
    """Master đoạn 1 bị xóa ngoài app (Google xóa luôn mọi instance) rồi UI cũ gửi
    'all' với id đã cũ: không còn gì để biết mã chuỗi → báo đã xóa, KHÔNG dò theo tên
    hay thời gian để xóa thay (quy tắc an toàn của luồng xóa). Đoạn 2 vẫn hiển thị,
    người dùng thấy và xóa được."""
    service, crud = calendar
    create_mwf(crud)
    target = instance_at(service, 'Mon 19/10 20:00')
    service.delete(CALENDAR_EVEN, target.rsplit('_', 1)[0])

    result = crud.delete_event(target, delete_mode='all')

    assert result['status'] == 'already_deleted'
    assert schedule(service) == EXPECTED_MWF_12[6:]


# ---------------- UPDATE ----------------

def follow_edit(start, end, count, **extra):
    info = class_info(start=start, end=end, count=count, **extra)
    info['edit_mode'] = 'following'
    return info


def test_sua_tu_buoi_nay_tro_di_doi_gio_tach_lai_dung_calendar(calendar):
    """Dời lớp từ 20:00 sang 19:00 kể từ 26/10: 19:00 Chicago là 07:00 VN (ODD) trước
    mốc và 08:00 VN (EVEN) sau mốc. Đoạn sau của chuỗi cũ (ODD 20:00) phải biến mất."""
    service, crud = calendar
    create_mwf(crud)

    crud.update_event(
        instance_at(service, 'Mon 26/10 20:00'),
        follow_edit('2026-10-26T19:00:00', '2026-10-26T20:00:00', count=9),
    )

    assert schedule(service) == EXPECTED_MWF_12[:3] + [
        ('Mon 26/10 19:00', CALENDAR_ODD), ('Wed 28/10 19:00', CALENDAR_ODD),
        ('Fri 30/10 19:00', CALENDAR_ODD),
        ('Mon 02/11 19:00', CALENDAR_EVEN), ('Wed 04/11 19:00', CALENDAR_EVEN),
        ('Fri 06/11 19:00', CALENDAR_EVEN), ('Mon 09/11 19:00', CALENDAR_EVEN),
        ('Wed 11/11 19:00', CALENDAR_EVEN), ('Fri 13/11 19:00', CALENDAR_EVEN),
    ]
    assert_all_in_right_calendar(service)
    assert_no_duplicates(service)


def test_sua_tu_buoi_o_doan_sau_khong_dung_doan_dau(calendar):
    service, crud = calendar
    create_mwf(crud)

    crud.update_event(
        instance_at(service, 'Mon 09/11 20:00'),
        follow_edit('2026-11-09T20:30:00', '2026-11-09T21:30:00', count=3),
    )

    assert schedule(service) == EXPECTED_MWF_12[:9] + [
        ('Mon 09/11 20:30', CALENDAR_ODD), ('Wed 11/11 20:30', CALENDAR_ODD),
        ('Fri 13/11 20:30', CALENDAR_ODD),
    ]
    assert_all_in_right_calendar(service)


def test_sua_tu_buoi_nay_loi_khi_cat_chuoi_cu_thi_go_chuoi_moi(calendar):
    service, crud = calendar
    create_mwf(crud)
    before = schedule(service)
    target = instance_at(service, 'Mon 26/10 20:00')
    master_id = target.rsplit('_', 1)[0]
    real_update = service.update

    def failing_update(calendar_id, event_id, body):
        if event_id == master_id:
            raise http_error(503, 'Backend Error')
        return real_update(calendar_id, event_id, body)

    service.update = failing_update
    with pytest.raises(Exception):
        crud.update_event(target, follow_edit('2026-10-26T19:00:00', '2026-10-26T20:00:00', count=9))

    assert schedule(service) == before   # chuỗi cũ nguyên vẹn, không còn mảnh chuỗi mới


def test_sua_mot_buoi_sang_gio_le_chuyen_sang_calendar_le(calendar):
    service, crud = calendar
    create_mwf(crud)
    info = class_info(start='2026-10-21T21:00:00', end='2026-10-21T22:00:00', byday=None)
    info['edit_mode'] = 'this'

    crud.update_event(instance_at(service, 'Wed 21/10 20:00'), info)

    labels = schedule(service)
    assert ('Wed 21/10 20:00', CALENDAR_EVEN) not in labels
    assert ('Wed 21/10 21:00', CALENDAR_ODD) in labels      # 09:00 VN
    assert len(labels) == 12
    assert_all_in_right_calendar(service)


# ---------------- API ----------------

def test_api_tu_choi_repeat_count_0_vi_sinh_chuoi_vo_han():
    import app

    with pytest.raises(ValidationError):
        app.ClassInfo(name='A', classname='A', teacher='T', program='P',
                      start='2026-10-19T20:00:00', end='2026-10-19T21:00:00',
                      recurrence='WEEKLY', byday=['MO'], repeat_count=0)
