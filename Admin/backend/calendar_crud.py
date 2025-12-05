# backend/calendar_crud.py
from google_calendar import calendar_service, CALENDAR_ID
from googleapiclient.errors import HttpError
import json
from pathlib import Path
from recurrence_helper import build_recurrence_rule
from datetime import datetime, timedelta

EXTRA_FILE = Path("data/classes_extra.json")

# ---------------- JSON Helper ----------------
def load_extra():
    if EXTRA_FILE.exists():
        with open(EXTRA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_extra(data):
    EXTRA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EXTRA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_extra(event_id, meeting_id, passcode, zoom_link="", classname=""):
    extra = load_extra()
    extra[event_id] = {
        "zoom_link": zoom_link,
        "meeting_id": meeting_id,
        "passcode": passcode,
        "classname": classname
    }
    save_extra(extra)

def update_extra(event_id, meeting_id, passcode, zoom_link="", classname=""):
    extra = load_extra()
    extra[event_id] = {
        "zoom_link": zoom_link,
        "meeting_id": meeting_id,
        "passcode": passcode,
        "classname": classname
    }
    save_extra(extra)

def remove_extra(event_id):
    extra = load_extra()
    if event_id in extra:
        del extra[event_id]
        save_extra(extra)

# ---------------- Events CRUD ----------------
def list_events():
    try:
        print("🔄 Lấy tất cả events từ Google Calendar...")
        
        # ✅ THÊM: Tính toán date range để lấy instances
        now = datetime.utcnow()
        time_min = now.isoformat() + 'Z'  # Bắt đầu từ hiện tại
        time_max = (now + timedelta(days=60)).isoformat() + 'Z'  # 60 ngày tới
        
        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            #timeMin=time_min,  # ✅ THÊM: Chỉ lấy events từ hiện tại
            timeMax=time_max,  # ✅ THÊM: Chỉ lấy events trong 60 ngày tới
            maxResults=2500,
            singleEvents=True,
            orderBy='startTime',
            showDeleted=False
        ).execute()
        
        events = events_result.get('items', [])
        
        # ✅ QUAN TRỌNG: FILTER OUT CANCELLED EVENTS
        active_events = []
        cancelled_count = 0
        
        for event in events:
            # Bỏ qua các event đã bị cancelled
            if event.get('status') == 'cancelled':
                cancelled_count += 1
                continue
                
            # Bỏ qua các event đã kết thúc (optional)
            event_end = event.get('end', {}).get('dateTime') or event.get('end', {}).get('date')
            if event_end:
                try:
                    end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                    if end_dt < now:
                        continue  # Bỏ qua event đã qua
                except:
                    pass
                    
            active_events.append(event)
        
        events = active_events
        extra = load_extra()
        
        # Gộp thêm meeting_id và passcode
        for e in events:
            eid = e.get('id')
            if eid in extra:
                e['zoom_link'] = extra[eid].get('zoom_link', '')
                e['meeting_id'] = extra[eid].get('meeting_id', '')
                e['passcode'] = extra[eid].get('passcode', '')
                e['classname'] = extra[eid].get('classname', '')
        
        # ✅ THÊM DEBUG ĐỂ KIỂM TRA FILTER
        print(f"📅 Tìm thấy {len(events)} active events (đã filter {cancelled_count} cancelled events)")
        
        recurring_events = [e for e in events if e.get('recurrence')]
        recurring_instances = [e for e in events if e.get('recurringEventId')]
        
        print(f"🔄 Recurrence Data: {len(recurring_events)} master events, {len(recurring_instances)} instances")
        
        return events
    except HttpError as error:
        print(f"❌ Google Calendar API Error: {error}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return []

# ✅ THÊM HÀM MỚI: Lấy single event bằng ID
def get_event(event_id):
    try:
        if not event_id or event_id == "undefined":
            raise ValueError("Invalid event ID")
            
        print(f"🔍 Fetching single event from Google Calendar: {event_id}")
        
        event = calendar_service.events().get(
            calendarId=CALENDAR_ID,
            eventId=event_id
        ).execute()
        
        # ✅ THÊM EXTRA DATA NẾU CÓ
        extra = load_extra()
        if event_id in extra:
            event['zoom_link'] = extra[event_id].get('zoom_link', '')
            event['meeting_id'] = extra[event_id].get('meeting_id', '')
            event['passcode'] = extra[event_id].get('passcode', '')
            event['classname'] = extra[event_id].get('classname', '')
        
        print(f"✅ Found event: {event.get('summary')}")
        print(f"🔄 Event recurrence: {event.get('recurrence')}")
        
        return event
        
    except HttpError as error:
        print(f"❌ Google Calendar API Error in get_event: {error}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error in get_event: {e}")
        raise

# ----------------- CREATE -----------------
def create_event(class_info):
    try:
        # ✅ THAY THẾ HÀM NORMALIZE_DATETIME
        def normalize_datetime_with_timezone(dt_str, timezone_str):
            """
            Chuẩn hóa datetime với timezone từ request - SUPPORT ALL TIMEZONES
            """
            print(f"🕐 normalize_datetime_with_timezone:")
            print(f"   Input: {dt_str}")
            print(f"   Timezone: {timezone_str}")
            
            if not dt_str:
                raise ValueError("Datetime string is empty")
            
            from datetime import datetime
            import pytz
            
            try:
                # TRƯỜNG HỢP 1: Đã có timezone trong string -> giữ nguyên
                if 'T' in dt_str and ('+' in dt_str.split('T')[1] or '-' in dt_str.split('T')[1] or dt_str.endswith('Z')):
                    print(f"   ✅ Already has timezone info: {dt_str}")
                    return dt_str
                
                # TRƯỜNG HỢP 2: Không có timezone -> thêm timezone từ request
                print(f"   ⚠️ No timezone detected, adding: {timezone_str}")
                
                # Parse datetime (định dạng: "2024-11-28T15:00")
                dt = datetime.fromisoformat(dt_str)
                
                # ✅ KIỂM TRA TIMEZONE CÓ HỢP LỆ KHÔNG
                try:
                    tz = pytz.timezone(timezone_str)
                    print(f"   ✅ Timezone is valid: {timezone_str}")
                except pytz.UnknownTimeZoneError:
                    print(f"   ❌ Unknown timezone: {timezone_str}, falling back to UTC")
                    tz = pytz.UTC
                
                # Áp dụng timezone
                dt_aware = tz.localize(dt)
                
                result = dt_aware.isoformat()
                print(f"   ✅ After adding timezone: {result}")
                return result
                
            except Exception as e:
                print(f"   ❌ Error in normalize_datetime: {e}")
                # Fallback: trả về nguyên bản + thêm timezone cơ bản
                return dt_str + "+00:00"  # UTC fallback

        # ========== PHẦN XỬ LÝ CHÍNH CỦA create_event ==========
        print(f"🎯 ========== TIMEZONE DEBUG START ==========")
        print(f"📥 Received class_info: {class_info}")
        
        # ✅ VALIDATION TIMEZONE - QUAN TRỌNG!
        timezone = class_info.get('timezone', 'Asia/Ho_Chi_Minh')
        
        # Kiểm tra timezone có hợp lệ không
        valid_timezones = [
            'Asia/Ho_Chi_Minh', 'America/Chicago', 'America/New_York', 
            'America/Los_Angeles', 'Europe/London', 'Europe/Paris',
            'Asia/Tokyo', 'Australia/Sydney', 'UTC',
            'America/Denver', 'Europe/Berlin', 'Asia/Seoul',
            'Asia/Singapore', 'Pacific/Auckland'
        ]
        
        if timezone not in valid_timezones:
            print(f"⚠️ Warning: Unknown timezone '{timezone}', using Asia/Ho_Chi_Minh")
            timezone = 'Asia/Ho_Chi_Minh'
        
        print(f"🔍 Timezone from request: '{class_info.get('timezone')}'")
        print(f"🕐 Using validated timezone: {timezone}")
        
        start_normalized = normalize_datetime_with_timezone(class_info['start'], timezone)
        end_normalized = normalize_datetime_with_timezone(class_info['end'], timezone)

        

        print("🐞 class_info nhận được trong create_event:", class_info)

        # TẠO BASE DESCRIPTION
        base_description = (
            f"Classname: {class_info.get('classname', '')}\n"
            f"Teacher: {class_info.get('teacher', '')}\n"
            f"Zoom: {class_info.get('zoom_link', '')}\n"
            f"Meeting ID: {class_info.get('meeting_id', '')}\n"
            f"Passcode: {class_info.get('passcode', '')}\n"
            f"Program: {class_info.get('program', '')}"
        )
        
        # THÊM RECURRENCE DESCRIPTION NẾU CÓ
        recurrence_desc = class_info.get('recurrence_description', '')
        if recurrence_desc:
            description = base_description + f"\nRecurrence: {recurrence_desc}"
            print(f"📝 Added recurrence description: {recurrence_desc}")
        else:
            description = base_description
            print("📝 No recurrence description")
            
        print(f"📝 Final event description: {description}")

        rrule_list = class_info.get("rrule")
        
        print("📆 RRULE được gửi lên Google:", rrule_list)
        
        event = {
            'summary': class_info['name'],
            'description': description,  # ✅ DÙNG DESCRIPTION MỚI
            'location': class_info.get('zoom_link', ''),
            # ✅ DÙNG TIMEZONE TỪ REQUEST
            'start': {'dateTime': start_normalized, 'timeZone': timezone},
            'end': {'dateTime': end_normalized, 'timeZone': timezone},
            'recurrence': rrule_list
        }

        
        rrule_list = class_info.get("rrule")
        if rrule_list and isinstance(rrule_list[0], dict):
            # Nếu là object, extract RRULE string
            rrule_list = [rrule_list[0].get('rrule', '')]
        
        print("📆 RRULE được gửi lên Google:", rrule_list)
        
        event = {
            'summary': class_info['name'],
            'description': description,
            'location': class_info.get('zoom_link', ''),
            # ✅ DÙNG TIMEZONE TỪ REQUEST
            'start': {'dateTime': start_normalized, 'timeZone': timezone},
            'end': {'dateTime': end_normalized, 'timeZone': timezone},
            'recurrence': rrule_list
        }

        # DEBUG chi tiết event trước khi gửi
        print("🎯 Event data gửi lên Google Calendar:")
        print(f"  - Summary: {event['summary']}")
        print(f"  - Start: {event['start']}")
        print(f"  - End: {event['end']}")
        print(f"  - Recurrence: {event['recurrence']}")

        result = calendar_service.events().insert(
            calendarId=CALENDAR_ID,
            body=event
        ).execute()

        event_id = result.get('id')
        add_extra(event_id,
                  class_info.get('meeting_id', ''),
                  class_info.get('passcode', ''),
                  class_info.get('zoom_link', ''),
                  class_info.get('classname', '')
        )

        print(f"✅ Event created: {result.get('summary')} (ID: {event_id})")
        print(f"🔄 Recurrence setting: {rrule_list}")
        return result

    except Exception as e:
        print(f"❌ Error in create_event: {str(e)}")
        raise

# ----------------- UPDATE -----------------
def update_event(event_id, class_info):
    """
    Cập nhật event trên Google Calendar
    """
    try:
        if not event_id or event_id == "undefined":
            raise ValueError("Invalid event ID")

        # ✅ THÊM HÀM normalize_datetime_with_timezone Ở ĐÂY - BÊN TRONG update_event
        def normalize_datetime_with_timezone(dt_str, timezone_str):
            """
            Chuẩn hóa datetime với timezone từ request - SUPPORT ALL TIMEZONES
            """
            print(f"🕐 normalize_datetime_with_timezone:")
            print(f"   Input: {dt_str}")
            print(f"   Timezone: {timezone_str}")
            
            if not dt_str:
                raise ValueError("Datetime string is empty")
            
            from datetime import datetime
            import pytz
            
            try:
                # TRƯỜNG HỢP 1: Đã có timezone trong string -> giữ nguyên
                if 'T' in dt_str and ('+' in dt_str.split('T')[1] or '-' in dt_str.split('T')[1] or dt_str.endswith('Z')):
                    print(f"   ✅ Already has timezone info: {dt_str}")
                    return dt_str
                
                # TRƯỜNG HỢP 2: Không có timezone -> thêm timezone từ request
                print(f"   ⚠️ No timezone detected, adding: {timezone_str}")
                
                # Parse datetime (định dạng: "2024-11-28T15:00")
                dt = datetime.fromisoformat(dt_str)
                
                # ✅ KIỂM TRA TIMEZONE CÓ HỢP LỆ KHÔNG
                try:
                    tz = pytz.timezone(timezone_str)
                    print(f"   ✅ Timezone is valid: {timezone_str}")
                except pytz.UnknownTimeZoneError:
                    print(f"   ❌ Unknown timezone: {timezone_str}, falling back to UTC")
                    tz = pytz.UTC
                
                # Áp dụng timezone
                dt_aware = tz.localize(dt)
                
                result = dt_aware.isoformat()
                print(f"   ✅ After adding timezone: {result}")
                return result
                
            except Exception as e:
                print(f"   ❌ Error in normalize_datetime: {e}")
                # Fallback: trả về nguyên bản + thêm timezone cơ bản
                return dt_str + "+00:00"  # UTC fallback

        # ========== PHẦN XỬ LÝ CHÍNH CỦA update_event ==========
        # Lấy event hiện tại
        event = calendar_service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()

        # ✅ VALIDATION TIMEZONE
        timezone = class_info.get('timezone', 'Asia/Ho_Chi_Minh')
        
        valid_timezones = [
            'Asia/Ho_Chi_Minh', 'America/Chicago', 'America/New_York', 
            'America/Los_Angeles', 'Europe/London', 'Europe/Paris',
            'Asia/Tokyo', 'Australia/Sydney', 'UTC',
            'America/Denver', 'Europe/Berlin', 'Asia/Seoul',
            'Asia/Singapore', 'Pacific/Auckland'
        ]
        
        if timezone not in valid_timezones:
            print(f"⚠️ Warning: Unknown timezone '{timezone}', using Asia/Ho_Chi_Minh")
            timezone = 'Asia/Ho_Chi_Minh'

        print(f"🕐 Using timezone for update: {timezone}")

        # Cập nhật thông tin event
        event['summary'] = class_info.get('name', event.get('summary'))
        # ✅ THAY THẾ PHẦN DESCRIPTION HIỆN TẠI
        base_description = (
            f"Classname: {class_info.get('classname', '')}\n"
            f"Teacher: {class_info.get('teacher', '')}\n"
            f"Zoom: {class_info.get('zoom_link', '')}\n"
            f"Meeting ID: {class_info.get('meeting_id', '')}\n"
            f"Passcode: {class_info.get('passcode', '')}\n"
            f"Program: {class_info.get('program', '')}"
        )
        
        # THÊM RECURRENCE DESCRIPTION NẾU CÓ
        recurrence_desc = class_info.get('recurrence_description', '')
        if recurrence_desc:
            event['description'] = base_description + f"\nRecurrence: {recurrence_desc}"
            print(f"📝 Added recurrence description: {recurrence_desc}")
        else:
            event['description'] = base_description
            print("📝 No recurrence description")
            
        print(f"📝 Final event description for update: {event['description']}")

        event['location'] = class_info.get('zoom_link', '')
        # ✅ DÙNG TIMEZONE TỪ REQUEST
        event['start'] = {
            'dateTime': normalize_datetime_with_timezone(class_info['start'], timezone), 
            'timeZone': timezone
        }
        event['end'] = {
            'dateTime': normalize_datetime_with_timezone(class_info['end'], timezone), 
            'timeZone': timezone
        }
        
        
        rrule_list = class_info.get("rrule")
        event['recurrence'] = rrule_list

        # DEBUG chi tiết
        print("🎯 Event update data gửi lên Google Calendar:")
        print(f"  - Summary: {event['summary']}")
        print(f"  - Start: {event['start']}")
        print(f"  - End: {event['end']}")
        print(f"  - Recurrence: {event['recurrence']}")

        # Cập nhật Google Calendar
        result = calendar_service.events().update(
            calendarId=CALENDAR_ID,
            eventId=event_id,
            body=event
        ).execute()

        # Cập nhật file extra JSON
        update_extra(
            event_id,
            class_info.get('meeting_id', ''),
            class_info.get('passcode', ''),
            class_info.get('zoom_link', ''),
            class_info.get('classname', '')
        )

        print(f"✅ Event updated: {result.get('summary')}")
        print(f"🔄 Recurrence setting: {event['recurrence']}")
        return result

    except Exception as e:
        print(f"❌ Error in update_event: {str(e)}")
        raise

def delete_event(event_id):
    try:
        if not event_id or event_id == "undefined":
            raise ValueError("Invalid event ID")

        # Xóa event Calendar
        calendar_service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        # Xóa JSON extra
        remove_extra(event_id)
        print(f"✅ Event deleted: {event_id}")
        return {"status": "deleted"}

    except Exception as e:
        print(f"❌ Error in delete_event: {str(e)}")
        raise