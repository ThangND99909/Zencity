"""Danh sách múi giờ cho phép chọn khi tạo lớp: CHỈ Việt Nam và Chicago.

Trung tâm chỉ xếp lớp theo giờ Việt Nam (ASVN) và giờ Texas/Chicago (ASUS). Dropdown có
thêm múi giờ khác chỉ làm admin dễ chọn nhầm.
"""
import pytz
import pytest
from fastapi.testclient import TestClient

from app import SUPPORTED_TIMEZONES, app

client = TestClient(app)

VIETNAM = "Asia/Ho_Chi_Minh"
CHICAGO = "America/Chicago"


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


def test_chi_co_viet_nam_va_chicago_dung_thu_tu():
    """VN là mặc định của sản phẩm nên đứng đầu dropdown."""
    assert values() == [VIETNAM, CHICAGO]


@pytest.mark.parametrize("zone", [VIETNAM, CHICAGO])
def test_moi_mui_gio_deu_la_ten_iana_hop_le(zone):
    """Tên sai sẽ bị validate_timezone âm thầm nuốt và fallback về giờ VN."""
    pytz.timezone(zone)  # ném UnknownTimeZoneError nếu sai


def test_co_nhan_hien_thi():
    for tz in SUPPORTED_TIMEZONES:
        assert tz["label"].strip()
        assert set(tz.keys()) == {"value", "label"}


@pytest.mark.parametrize("zone", [VIETNAM, CHICAGO])
def test_moi_lua_chon_deu_song_sot_qua_validate_timezone(zone):
    """Chọn trong dropdown mà bị fallback về VN là hỏng toàn bộ chuỗi xử lý phía sau."""
    from calendar_crud import validate_timezone
    from recurrence_helper import validate_recurrence_timezone

    assert validate_timezone(zone) == zone
    assert validate_recurrence_timezone(zone) == zone
