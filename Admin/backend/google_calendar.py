from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'service_account.json'

# CALENDAR ID CỦA BẠN
# CALENDAR CHẴN: SỬ DỤNG CHO GIỜ CHẴN
CALENDAR_ID = '830f3e638fffdc912efe4f419697ea14635c8f0af19fc8fa6bee0a858d98dbf4@group.calendar.google.com'

# CALENDAR LẺ: SỬ DỤNG CHO GIỜ LẺ
#CALENDAR_EVEN = 'CALENDAR_EVEN_ID_HERE@group.calendar.google.com'

# Hoặc dùng dictionary để quản lý
#CALENDARS = {
#    'odd': CALENDAR_ODD,
#    'even': CALENDAR_EVEN,
#    'default': CALENDAR_ODD  # Calendar mặc định
#}

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

calendar_service = build('calendar', 'v3', credentials=credentials)