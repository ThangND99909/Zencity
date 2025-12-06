# google_calendar.py
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'service_account.json'

# ========== ĐỊNH NGHĨA 2 CALENDAR ==========
# Calendar lẻ (giờ lẻ: 1, 3, 5...)
CALENDAR_ODD = '830f3e638fffdc912efe4f419697ea14635c8f0af19fc8fa6bee0a858d98dbf4@group.calendar.google.com'

# Calendar chẵn (giờ chẵn: 2, 4, 6...) - THAY BẰNG CALENDAR THỰC TẾ CỦA BẠN
CALENDAR_EVEN = '2c059c2a3847e37c0ad5e6f598661530724e12871532935903b05f291fca8b2a@group.calendar.google.com'

# Dictionary quản lý calendars
CALENDARS = {
    'odd': CALENDAR_ODD,
    'even': CALENDAR_EVEN,
    'default': CALENDAR_ODD  # Calendar mặc định
}

# Biến global để biết calendar nào là lẻ/chẵn
CALENDAR_TYPES = {
    CALENDAR_ODD: 'odd',
    CALENDAR_EVEN: 'even'
}

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

calendar_service = build('calendar', 'v3', credentials=credentials)

print(f"✅ Google Calendar API initialized")
print(f"📅 Calendar ODD: {CALENDAR_ODD[:30]}...")
print(f"📅 Calendar EVEN: {CALENDAR_EVEN[:30]}...")