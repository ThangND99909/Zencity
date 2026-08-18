import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import google_auth_httplib2
import httplib2
import threading
from log_config import make_print

print = make_print(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

# 🔹 Lấy giá trị từ biến môi trường
SERVICE_ACCOUNT_RAW = os.getenv("GOOGLE_SERVICE_ACCOUNT", "service_account.json")

# 🔹 Kiểm tra xem là JSON thật hay chỉ là tên file
if SERVICE_ACCOUNT_RAW.strip().startswith("{"):
    # Là JSON → parse trực tiếp
    print("🔐 Using service account from environment variable")
    info = json.loads(SERVICE_ACCOUNT_RAW)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
else:
    # Là tên file → dùng như local
    print("📄 Using service account from local file")
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_RAW, scopes=SCOPES
    )

# 🔹 Khởi tạo Calendar service
calendar_service = build('calendar', 'v3', credentials=credentials)

_transport_local = threading.local()


def create_calendar_http(timeout=30):
    """Return a reusable authorized transport scoped to the current thread.

    ``httplib2.Http`` is not thread-safe, so a single global transport cannot be
    shared by FastAPI workers. Keeping one transport per thread preserves that
    isolation while allowing TCP/TLS connections to be reused across the Google
    calls that make up one CRUD operation.
    """
    transport = getattr(_transport_local, "transport", None)
    transport_timeout = getattr(_transport_local, "timeout", None)
    if transport is None or transport_timeout != timeout:
        transport = google_auth_httplib2.AuthorizedHttp(
            credentials,
            http=httplib2.Http(timeout=timeout)
        )
        _transport_local.transport = transport
        _transport_local.timeout = timeout
    return transport

# Giữ nguyên bước kiểm tra kết nối cũ khi backend khởi động.
try:
    calendar_service.calendarList().list(maxResults=1).execute()
    print("✅ Google Calendar service warmed up successfully!")
except Exception as e:
    print(f"⚠️ Warm-up failed: {e}")

# ========== ĐỊNH NGHĨA 2 CALENDAR ==========
CALENDAR_ODD = 'cf06d74dce3c09de7fcf3926e7c50d80b8d607f3eaadfa7eb1b52fdd361fb8eb@group.calendar.google.com'
CALENDAR_EVEN = '2c0db271c8b768080efd745887e99bfa6b29e6e8e72b7f3a11e8406401a2ac94@group.calendar.google.com'

CALENDARS = {
    'odd': CALENDAR_ODD,
    'even': CALENDAR_EVEN
}

print("✅ Google Calendar API initialized")
print(f"📅 Calendar ODD: {CALENDAR_ODD[:30]}...")
print(f"📅 Calendar EVEN: {CALENDAR_EVEN[:30]}...")
