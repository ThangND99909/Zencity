from fastapi.testclient import TestClient

from app import app
from auth import create_access_token, validate_access_token


client = TestClient(app)


def test_signed_token_round_trip_and_tamper_rejection():
    token, _ = create_access_token()
    assert validate_access_token(token) is True
    assert validate_access_token(token + "tampered") is False


def test_protected_route_requires_session():
    response = client.get("/timezones")
    assert response.status_code == 401


def test_login_grants_access_to_protected_route():
    login = client.post("/auth/login", json={"passcode": "1234"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    response = client.get("/timezones", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_invalid_passcode_is_rejected():
    response = client.post(
        "/auth/login",
        json={"passcode": "0000"},
        headers={"x-forwarded-for": "test-invalid-passcode"},
    )
    assert response.status_code == 401
