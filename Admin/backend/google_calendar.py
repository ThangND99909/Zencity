import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

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

# ⚡ Warm-up (tùy chọn, để kiểm tra kết nối Google API)
try:
    calendar_service.calendarList().list(maxResults=1).execute()
    print("✅ Google Calendar service warmed up successfully!")
except Exception as e:
    print(f"⚠️ Warm-up failed: {e}")

# ========== ĐỊNH NGHĨA 2 CALENDAR ==========
CALENDAR_ODD = '830f3e638fffdc912efe4f419697ea14635c8f0af19fc8fa6bee0a858d98dbf4@group.calendar.google.com'
CALENDAR_EVEN = '2c059c2a3847e37c0ad5e6f598661530724e12871532935903b05f291fca8b2a@group.calendar.google.com'

CALENDARS = {
    'odd': CALENDAR_ODD,
    'even': CALENDAR_EVEN,
    'default': CALENDAR_ODD
}

CALENDAR_TYPES = {
    CALENDAR_ODD: 'odd',
    CALENDAR_EVEN: 'even'
}

print("✅ Google Calendar API initialized")
print(f"📅 Calendar ODD: {CALENDAR_ODD[:30]}...")
print(f"📅 Calendar EVEN: {CALENDAR_EVEN[:30]}...")
