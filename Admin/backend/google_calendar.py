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
CALENDAR_ODD = '2c059c2a3847e37c0ad5e6f598661530724e12871532935903b05f291fca8b2a@group.calendar.google.com'
CALENDAR_EVEN = '830f3e638fffdc912efe4f419697ea14635c8f0af19fc8fa6bee0a858d98dbf4@group.calendar.google.com'

CALENDARS = {
    'odd': CALENDAR_ODD,
    'even': CALENDAR_EVEN
}

print("✅ Google Calendar API initialized")
print(f"📅 Calendar ODD: {CALENDAR_ODD[:30]}...")
print(f"📅 Calendar EVEN: {CALENDAR_EVEN[:30]}...")
