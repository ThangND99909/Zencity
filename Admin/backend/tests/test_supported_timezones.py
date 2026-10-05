"""Danh sách múi giờ cho phép chọn khi tạo lớp: CHỈ Việt Nam và Hoa Kỳ.

Trước đây endpoint chỉ trả về VN + Chicago, nên thầy cô ở New York buộc phải chọn
"Giờ Miền Trung" → lệch 1 tiếng, Los Angeles lệch 2 tiếng, và không ai ở Denver /
Arizona / Alaska / Hawaii chọn đúng được múi giờ của mình.
"""
import pytz
import pytest
from fastapi.testclient import TestClient

from app import SUPPORTED_TIMEZONES, app

client = TestClient(app)

VIETNAM = "Asia/Ho_Chi_Minh"

# Toàn bộ múi giờ lục địa + hải ngoại của Hoa Kỳ mà sản phẩm phục vụ.
US_TIMEZONES = {
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
}


def values():
    return [tz["value"] for tz in SUPPORTED_TIMEZONES]


def auth_headers():
    login = client.post("/auth/login", json={"passcode": "1234"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_endpoint_tra_ve_dung_danh_sach():
    response = client.get("/timezones", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["timezones"] == SUPPORTED_TIMEZONES


def test_endpoint_van_yeu_cau_dang_nhap():
    assert client.get("/timezones").status_code == 401


def test_chi_co_viet_nam_va_hoa_ky():
    assert set(values()) == {VIETNAM} | US_TIMEZONES


def test_khong_lot_mui_gio_nuoc_khac():
    """Chốt yêu cầu: không có London / Paris / Tokyo / Sydney… trong danh sách."""
    ngoai_le = [
        value for value in values()
        if value != VIETNAM and value not in US_TIMEZONES
    ]
    assert ngoai_le == []


def test_viet_nam_dung_dau_danh_sach():
    """VN là mặc định của sản phẩm nên phải là lựa chọn đầu tiên trong dropdown."""
    assert values()[0] == VIETNAM


@pytest.mark.parametrize("zone", sorted({VIETNAM} | US_TIMEZONES))
def test_moi_mui_gio_deu_la_ten_iana_hop_le(zone):
    """Tên sai sẽ bị validate_timezone âm thầm nuốt và fallback về giờ VN."""
    assert zone in values()
    pytz.timezone(zone)  # ném UnknownTimeZoneError nếu sai


def test_khong_trung_lap_va_co_nhan_hien_thi():
    assert len(values()) == len(set(values()))
    for tz in SUPPORTED_TIMEZONES:
        assert tz["label"].strip()
        assert set(tz.keys()) == {"value", "label"}


def test_khong_co_hai_mui_gio_my_nao_trung_nhau_ca_nam():
    """Mỗi lựa chọn phải thật sự khác nhau — nếu không thì một cái là thừa.

    Phải so CẢ HAI mùa: tháng 7 thì Phoenix và Los Angeles đều -07:00, chỉ tháng 1
    mới tách ra (-07:00 vs -08:00). Chính chỗ này là lý do không được gộp Arizona
    vào Miền Tây hay Miền Núi.
    """
    from datetime import datetime

    dau_van = {
        zone: (
            pytz.timezone(zone).localize(datetime(2026, 1, 15, 12, 0)).utcoffset(),
            pytz.timezone(zone).localize(datetime(2026, 7, 15, 12, 0)).utcoffset(),
        )
        for zone in US_TIMEZONES
    }

    assert len(set(dau_van.values())) == len(US_TIMEZONES)
    # Và khẳng định rõ cặp dễ nhầm nhất.
    assert dau_van["America/Phoenix"][1] == dau_van["America/Los_Angeles"][1]  # hè: trùng
    assert dau_van["America/Phoenix"][0] != dau_van["America/Los_Angeles"][0]  # đông: khác


def test_arizona_va_hawaii_khong_ap_dung_dst():
    """Hai vùng này đứng yên quanh năm — gộp vào Denver/Alaska sẽ sai 1 tiếng nửa năm."""
    from datetime import datetime

    for zone in ("America/Phoenix", "Pacific/Honolulu"):
        tz = pytz.timezone(zone)
        mua_dong = tz.localize(datetime(2026, 1, 15, 12, 0)).utcoffset()
        mua_he = tz.localize(datetime(2026, 7, 15, 12, 0)).utcoffset()
        assert mua_dong == mua_he

    for zone in ("America/Denver", "America/Anchorage"):
        tz = pytz.timezone(zone)
        mua_dong = tz.localize(datetime(2026, 1, 15, 12, 0)).utcoffset()
        mua_he = tz.localize(datetime(2026, 7, 15, 12, 0)).utcoffset()
        assert mua_dong != mua_he


@pytest.mark.parametrize("zone", sorted({VIETNAM} | US_TIMEZONES))
def test_moi_lua_chon_deu_song_sot_qua_validate_timezone(zone):
    """Chọn trong dropdown mà bị fallback về VN là hỏng toàn bộ chuỗi xử lý phía sau."""
    from calendar_crud import validate_timezone
    from recurrence_helper import validate_recurrence_timezone

    assert validate_timezone(zone) == zone
    assert validate_recurrence_timezone(zone) == zone
