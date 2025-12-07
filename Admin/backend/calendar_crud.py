# backend/calendar_crud.py
from google_calendar import calendar_service, CALENDARS
from googleapiclient.errors import HttpError
import json
from pathlib import Path
from recurrence_helper import build_recurrence_rule
from datetime import datetime, timedelta

EXTRA_FILE = Path("data/classes_extra.json")

try:
    from recurrence_utils import (
        update_recurrence_for_following_delete,
        is_first_recurring_instance,
        parse_rrule_string,
        stop_recurrence_at_instance,
        parse_and_update_recurrence_rule
    )
    HAS_RECURRENCE_UTILS = True
    print("✅ Recurrence utils imported successfully")
except ImportError as e:
    HAS_RECURRENCE_UTILS = False
    print(f"⚠️ Could not import recurrence_utils: {e}")

    # Define fallback functions
    def stop_recurrence_at_instance(master_event, instance_start_str):
        print("⚠️ Using simplified stop_recurrence_at_instance")
        from datetime import datetime, timedelta
        import re
        
        try:
            instance_dt = datetime.fromisoformat(instance_start_str.replace('Z', '+00:00'))
            until_str = (instance_dt - timedelta(seconds=1)).strftime('%Y%m%dT%H%M%SZ')
            
            recurrence = master_event.get('recurrence', [])
            updated = []
            
            for rule in recurrence:
                if 'RRULE:' in rule:
                    rrule = rule.replace('RRULE:', '')
                    # Simple: replace or add UNTIL
                    if 'UNTIL=' in rrule:
                        rrule = re.sub(r'UNTIL=[\dTZ]+', f'UNTIL={until_str}', rrule)
                    else:
                        rrule = f'{rrule};UNTIL={until_str}'
                    updated.append(f'RRULE:{rrule}')
                else:
                    updated.append(rule)
            
            return updated
        except:
            return master_event.get('recurrence', [])

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

def add_extra(event_id, meeting_id, passcode, zoom_link="", classname="", calendar_id=""):
    extra = load_extra()
    extra[event_id] = {
        "zoom_link": zoom_link,
        "meeting_id": meeting_id,
        "passcode": passcode,
        "classname": classname,
        "calendar_id": calendar_id
    }
    save_extra(extra)
    print(f"✅ Extra data saved for event {event_id} with calendar_id: {calendar_id}")

def update_extra(event_id, meeting_id, passcode, zoom_link="", classname="", calendar_id=""):
    extra = load_extra()
    extra[event_id] = {
        "zoom_link": zoom_link,
        "meeting_id": meeting_id,
        "passcode": passcode,
        "classname": classname,
        "calendar_id": calendar_id
    }
    save_extra(extra)
    print(f"✅ Extra data updated for event {event_id} with calendar_id: {calendar_id}")

def remove_extra(event_id):
    extra = load_extra()
    if event_id in extra:
        del extra[event_id]
        save_extra(extra)

# ========== HÀM XÁC ĐỊNH CALENDAR ==========
def determine_calendar_by_hour(start_datetime_str):
    """
    Xác định calendar dựa trên giờ bắt đầu
    Giờ chẵn (0, 2, 4, ...) -> calendar chẵn
    Giờ lẻ (1, 3, 5, ...) -> calendar lẻ
    """
    try:
        if not start_datetime_str:
            print("⚠️ Empty datetime, using default calendar")
            return CALENDARS['default']
        
        # Parse datetime string
        from datetime import datetime
        
        # Xử lý các định dạng datetime
        dt_str = start_datetime_str
        
        # Xử lý string có Z
        if dt_str.endswith('Z'):
            dt_str = dt_str.replace('Z', '+00:00')
        
        # Nếu không có timezone, thêm timezone mặc định
        if 'T' in dt_str and '+' not in dt_str and '-' not in dt_str.split('T')[1]:
            dt_str = dt_str + '+00:00'
        
        # Parse datetime
        start_dt = datetime.fromisoformat(dt_str)
        hour = start_dt.hour
        
        # Logic chẵn lẻ
        if hour % 2 == 0:  # Giờ chẵn
            print(f"🕐 Hour {hour} is EVEN -> Calendar EVEN")
            return CALENDARS['even']
        else:  # Giờ lẻ
            print(f"🕐 Hour {hour} is ODD -> Calendar ODD")
            return CALENDARS['odd']
            
    except Exception as e:
        print(f"❌ Error determining calendar by hour: {e}")
        print(f"📝 Raw datetime string: {start_datetime_str}")
        return CALENDARS['default']
    
def get_calendar_type_by_id(calendar_id):
    """Lấy loại calendar từ calendar_id"""
    if calendar_id == CALENDARS['odd']:
        return 'odd'
    elif calendar_id == CALENDARS['even']:
        return 'even'
    else:
        return 'unknown'
# ---------------- Events CRUD ----------------
# ========== HÀM LẤY EVENTS TỪ MULTIPLE CALENDARS ==========
def list_events(calendar_type='both'):
    """
    Lấy events từ các calendar - HIỆU QUẢ & ĐƠN GIẢN
    """
    try:
        all_events = []
        cancelled_count = 0
        
        # Load extra data trước
        extra = load_extra()
        
        # Xác định calendars cần lấy
        calendar_ids = []
        if calendar_type == 'odd' or calendar_type == 'both':
            calendar_ids.append(CALENDARS['odd'])
        if calendar_type == 'even' or calendar_type == 'both':
            calendar_ids.append(CALENDARS['even'])
        
        print(f"🔄 Fetching events from {len(calendar_ids)} calendar(s): {calendar_type}")
        
        now = datetime.utcnow()
        time_min = now.isoformat() + 'Z'
        time_max = (now + timedelta(days=60)).isoformat() + 'Z'
        
        for calendar_id in calendar_ids:
            try:
                calendar_type_name = get_calendar_type_by_id(calendar_id)
                print(f"  📅 Fetching from calendar: {calendar_type_name}")
                
                # **CÁCH TỐI ƯU: FETCH 1 LẦN VỚI singleEvents=True**
                # Google Calendar API đã expand instances cho chúng ta
                events_result = calendar_service.events().list(
                    calendarId=calendar_id,
                    #timeMin=time_min,
                    timeMax=time_max,
                    maxResults=2500,
                    singleEvents=True,  # ⚠️ QUAN TRỌNG: True để có instances
                    orderBy='startTime',
                    showDeleted=False
                ).execute()
                
                events = events_result.get('items', [])
                print(f"  📊 Found {len(events)} events")
                
                # **XỬ LÝ TỪNG EVENT**
                for event in events:
                    event_id = event.get('id')
                    
                    # Skip cancelled events
                    if event.get('status') == 'cancelled':
                        cancelled_count += 1
                        continue
                    
                    # **PHÂN LOẠI EVENT**
                    recurring_event_id = event.get('recurringEventId')
                    has_recurrence = event.get('recurrence')
                    
                    # THÊM METADATA
                    event['_calendar_source'] = calendar_type_name
                    event['_calendar_id'] = calendar_id
                    
                    if recurring_event_id:
                        # Đây là instance của recurring event
                        event['_is_instance'] = True
                        event['_is_master'] = False
                        event['_master_event_id'] = recurring_event_id
                    elif has_recurrence:
                        # Đây là master event - KHÔNG HIỂN THỊ TRÊN CALENDAR VIEW
                        event['_is_master'] = True
                        event['_is_instance'] = False
                        
                        # **QUAN TRỌNG: SKIP MASTER EVENTS - không thêm vào all_events**
                        # Master events chỉ là template, không có thời gian cụ thể
                        continue
                    else:
                        # Regular non-recurring event
                        event['_is_master'] = False
                        event['_is_instance'] = False
                    
                    # THÊM EXTRA DATA
                    if event_id in extra:
                        event['zoom_link'] = extra[event_id].get('zoom_link', '')
                        event['meeting_id'] = extra[event_id].get('meeting_id', '')
                        event['passcode'] = extra[event_id].get('passcode', '')
                        event['classname'] = extra[event_id].get('classname', '')
                    
                    # THÊM VÀO ALL_EVENTS
                    all_events.append(event)
                
                # **THỐNG KÊ CHO CALENDAR NÀY**
                masters_skipped = len([e for e in events if e.get('recurrence') and not e.get('recurringEventId')])
                instances_added = len([e for e in all_events if e.get('_calendar_id') == calendar_id and e.get('_is_instance')])
                regular_added = len([e for e in all_events if e.get('_calendar_id') == calendar_id and not e.get('_is_instance') and not e.get('_is_master')])
                
                print(f"    👑 Skipped {masters_skipped} master events (hidden)")
                print(f"    ➕ Added {instances_added} instances")
                print(f"    📌 Added {regular_added} regular events")
                
            except HttpError as error:
                print(f"❌ Error fetching from calendar {calendar_id}: {error}")
                continue
            except Exception as e:
                print(f"❌ Unexpected error with calendar {calendar_id}: {e}")
                continue
        
        # **SORT LẠI (cho chắc chắn)**
        def get_start_time(event):
            start = event.get('start', {})
            dt_str = start.get('dateTime') or start.get('date')
            if dt_str:
                try:
                    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                except:
                    return datetime.max
            return datetime.max
        
        all_events.sort(key=get_start_time)
        
        # **THỐNG KÊ TỔNG**
        total_masters_skipped = len([e for e in all_events if e.get('_is_master')])
        total_instances = len([e for e in all_events if e.get('_is_instance')])
        total_regular = len([e for e in all_events if not e.get('_is_instance') and not e.get('_is_master')])
        
        print(f"📅 Total displayed: {len(all_events)} events")
        print(f"📊 Calendar breakdown: ODD: {len([e for e in all_events if e.get('_calendar_source') == 'odd'])}, EVEN: {len([e for e in all_events if e.get('_calendar_source') == 'even'])}")
        print(f"📈 Event types: {total_masters_skipped} masters hidden, {total_instances} instances, {total_regular} regular")
        
        # **DEBUG: Hiển thị sample events**
        if all_events and len(all_events) > 0:
            print(f"🔍 Sample events to display:")
            for i, event in enumerate(all_events[:3]):  # 3 events đầu
                event_type = "INSTANCE" if event.get('_is_instance') else "REGULAR"
                print(f"   {i+1}. {event.get('summary', 'No title')[:30]}... ({event_type})")
        
        return all_events
        
    except Exception as e:
        print(f"❌ Error in list_events: {e}")
        import traceback
        traceback.print_exc()
        return []


# ✅ THÊM HÀM MỚI: Lấy single event bằng ID
def get_event(event_id):
    """
    Tìm event trên cả 2 calendars
    """
    try:
        if not event_id or event_id == "undefined":
            raise ValueError("Invalid event ID")
            
        print(f"🔍 Fetching single event: {event_id}")
        
        # Thử tìm trên cả 2 calendars
        found_event = None
        found_calendar = None
        
        for calendar_id, cal_type in [(CALENDARS['odd'], 'odd'), (CALENDARS['even'], 'even')]:
            try:
                event = calendar_service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
                found_event = event
                found_calendar = calendar_id
                event['_calendar_source'] = cal_type
                event['_calendar_id'] = calendar_id
                print(f"✅ Found event in {cal_type.upper()} calendar")
                break
            except HttpError as e:
                if e.resp.status == 404:
                    continue  # Không tìm thấy trong calendar này, thử calendar khác
                else:
                    raise  # Lỗi khác, raise lên
        
        if not found_event:
            raise HttpError(resp=type('obj', (object,), {'status': 404})(), content=b'Event not found')
        
        # ✅ THÊM EXTRA DATA NẾU CÓ
        extra = load_extra()
        if event_id in extra:
            found_event['zoom_link'] = extra[event_id].get('zoom_link', '')
            found_event['meeting_id'] = extra[event_id].get('meeting_id', '')
            found_event['passcode'] = extra[event_id].get('passcode', '')
            found_event['classname'] = extra[event_id].get('classname', '')
            found_event['calendar_id'] = extra[event_id].get('calendar_id', found_calendar)
        else:
            found_event['calendar_id'] = found_calendar
        
        return found_event
        
    except HttpError as error:
        print(f"❌ Google Calendar API Error in get_event: {error}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error in get_event: {e}")
        raise

# ----------------- CREATE -----------------
def create_event(class_info):
    """
    Tạo event với calendar tự động chọn dựa trên giờ bắt đầu
    """
    try:
        # ✅ XÁC ĐỊNH CALENDAR DỰA TRÊN GIỜ BẮT ĐẦU
        start_time = class_info.get('start', '')
        calendar_id = determine_calendar_by_hour(start_time)
        
        print(f"🎯 ========== CREATE EVENT ==========")
        print(f"📥 Received class_info: {class_info}")
        print(f"🕐 Auto-selected calendar: {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'}")
        print(f"🔧 Calendar ID: {calendar_id[:50]}...")
        
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
        
        print(f"🕐 Using validated timezone: {timezone}")
        
        # ✅ NORMALIZE DATETIME WITH TIMEZONE
        def normalize_datetime_with_timezone(dt_str, timezone_str):
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
        
        start_normalized = normalize_datetime_with_timezone(class_info['start'], timezone)
        end_normalized = normalize_datetime_with_timezone(class_info['end'], timezone)

        # ✅ TẠO DESCRIPTION
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
        
        # ✅ TẠO EVENT OBJECT
        event = {
            'summary': class_info['name'],
            'description': description,
            'location': class_info.get('zoom_link', ''),
            'start': {'dateTime': start_normalized, 'timeZone': timezone},
            'end': {'dateTime': end_normalized, 'timeZone': timezone},
            'recurrence': rrule_list
        }

        # DEBUG chi tiết event trước khi gửi
        print("🎯 Event data gửi lên Google Calendar:")
        print(f"  - Summary: {event['summary']}")
        print(f"  - Calendar: {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'}")
        print(f"  - Start: {event['start']}")
        print(f"  - End: {event['end']}")
        print(f"  - Recurrence: {event['recurrence']}")

        # ✅ GỬI REQUEST TẠO EVENT VÀO CALENDAR ĐÃ CHỌN
        result = calendar_service.events().insert(
            calendarId=calendar_id,  # SỬ DỤNG CALENDAR ĐÃ XÁC ĐỊNH
            body=event
        ).execute()

        event_id = result.get('id')
        
        # ✅ LƯU EXTRA DATA VỚI CALENDAR_ID
        add_extra(event_id,
                  class_info.get('meeting_id', ''),
                  class_info.get('passcode', ''),
                  class_info.get('zoom_link', ''),
                  class_info.get('classname', ''),
                  calendar_id  # LƯU CALENDAR_ID
        )

        print(f"✅ Event created in {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'} calendar")
        print(f"🔄 Recurrence setting: {rrule_list}")
        return result

    except Exception as e:
        print(f"❌ Error in create_event: {str(e)}")
        raise

# ----------------- UPDATE -----------------
# ========== HÀM CẬP NHẬT EVENT VỚI CALENDAR TỰ ĐỘNG ==========
def update_event(event_id, class_info):
    """
    Cập nhật event - có thể chuyển sang calendar khác nếu giờ thay đổi
    """
    try:
        if not event_id or event_id == "undefined":
            raise ValueError("Invalid event ID")
        
        print(f"🔄 ========== UPDATE EVENT ==========")
        print(f"🆔 Event ID: {event_id}")
        print(f"📝 Update data: {class_info}")
        
        # ✅ HÀM normalize_datetime_with_timezone (giống trong create_event)
        def normalize_datetime_with_timezone(dt_str, timezone_str):
            print(f"🕐 normalize_datetime_with_timezone:")
            print(f"   Input: {dt_str}")
            print(f"   Timezone: {timezone_str}")
            
            if not dt_str:
                raise ValueError("Datetime string is empty")
            
            from datetime import datetime
            import pytz
            
            try:
                if 'T' in dt_str and ('+' in dt_str.split('T')[1] or '-' in dt_str.split('T')[1] or dt_str.endswith('Z')):
                    print(f"   ✅ Already has timezone info: {dt_str}")
                    return dt_str
                
                print(f"   ⚠️ No timezone detected, adding: {timezone_str}")
                dt = datetime.fromisoformat(dt_str)
                
                try:
                    tz = pytz.timezone(timezone_str)
                    print(f"   ✅ Timezone is valid: {timezone_str}")
                except pytz.UnknownTimeZoneError:
                    print(f"   ❌ Unknown timezone: {timezone_str}, falling back to UTC")
                    tz = pytz.UTC
                
                dt_aware = tz.localize(dt)
                result = dt_aware.isoformat()
                print(f"   ✅ After adding timezone: {result}")
                return result
                
            except Exception as e:
                print(f"   ❌ Error in normalize_datetime: {e}")
                return dt_str + "+00:00"
        
        # ✅ TÌM EVENT HIỆN TẠI TRÊN CALENDAR NÀO
        current_event = None
        current_calendar_id = None
        
        # Thử tìm trên cả 2 calendars
        for calendar_id in [CALENDARS['odd'], CALENDARS['even']]:
            try:
                event = calendar_service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
                current_event = event
                current_calendar_id = calendar_id
                print(f"✅ Found existing event in {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'} calendar")
                break
            except HttpError as e:
                if e.resp.status == 404:
                    continue  # Không tìm thấy trong calendar này
                else:
                    raise
        
        if not current_event:
            raise ValueError(f"Event {event_id} not found in any calendar")
        
        # ✅ XÁC ĐỊNH CALENDAR MỚI DỰA TRÊN GIỜ MỚI
        new_start_time = class_info.get('start', '')
        new_calendar_id = determine_calendar_by_hour(new_start_time)
        
        print(f"🔄 Calendar check:")
        print(f"  - Current: {'EVEN' if current_calendar_id == CALENDARS['even'] else 'ODD'}")
        print(f"  - New: {'EVEN' if new_calendar_id == CALENDARS['even'] else 'ODD'}")
        
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
        
        print(f"🕐 Using validated timezone: {timezone}")
        
        # ✅ NORMALIZE DATETIME
        start_normalized = normalize_datetime_with_timezone(class_info['start'], timezone)
        end_normalized = normalize_datetime_with_timezone(class_info['end'], timezone)
        
        # ✅ TẠO DESCRIPTION MỚI
        base_description = (
            f"Classname: {class_info.get('classname', '')}\n"
            f"Teacher: {class_info.get('teacher', '')}\n"
            f"Zoom: {class_info.get('zoom_link', '')}\n"
            f"Meeting ID: {class_info.get('meeting_id', '')}\n"
            f"Passcode: {class_info.get('passcode', '')}\n"
            f"Program: {class_info.get('program', '')}"
        )
        
        recurrence_desc = class_info.get('recurrence_description', '')
        if recurrence_desc:
            description = base_description + f"\nRecurrence: {recurrence_desc}"
            print(f"📝 Added recurrence description: {recurrence_desc}")
        else:
            description = base_description
            print("📝 No recurrence description")
        
        rrule_list = class_info.get("rrule")
        
        # ✅ TRƯỜNG HỢP 1: CALENDAR THAY ĐỔI -> XÓA CŨ, TẠO MỚI
        if new_calendar_id != current_calendar_id:
            print(f"🔄 Calendar changed! Deleting old and creating new...")
            
            # Xóa event cũ
            try:
                calendar_service.events().delete(
                    calendarId=current_calendar_id,
                    eventId=event_id
                ).execute()
                print(f"🗑️ Deleted event from old calendar")
            except Exception as delete_error:
                print(f"⚠️ Error deleting from old calendar: {delete_error}")
            
            # Tạo event mới với calendar mới
            class_info['calendar_id'] = new_calendar_id
            return create_event(class_info)
        
        # ✅ TRƯỜNG HỢP 2: CÙNG CALENDAR -> UPDATE BÌNH THƯỜNG
        else:
            print(f"🔄 Same calendar, updating normally...")
            
            # Cập nhật thông tin event
            current_event['summary'] = class_info.get('name', current_event.get('summary'))
            current_event['description'] = description
            current_event['location'] = class_info.get('zoom_link', '')
            current_event['start'] = {
                'dateTime': start_normalized, 
                'timeZone': timezone
            }
            current_event['end'] = {
                'dateTime': end_normalized, 
                'timeZone': timezone
            }
            current_event['recurrence'] = rrule_list

            # DEBUG chi tiết
            print("🎯 Event update data:")
            print(f"  - Summary: {current_event['summary']}")
            print(f"  - Calendar: {'EVEN' if current_calendar_id == CALENDARS['even'] else 'ODD'}")
            print(f"  - Start: {current_event['start']}")
            print(f"  - End: {current_event['end']}")
            print(f"  - Recurrence: {current_event['recurrence']}")

            # Cập nhật Google Calendar
            result = calendar_service.events().update(
                calendarId=current_calendar_id,
                eventId=event_id,
                body=current_event
            ).execute()

            # Cập nhật file extra JSON
            update_extra(
                event_id,
                class_info.get('meeting_id', ''),
                class_info.get('passcode', ''),
                class_info.get('zoom_link', ''),
                class_info.get('classname', ''),
                current_calendar_id  # Lưu calendar_id
            )

            print(f"✅ Event updated in {'EVEN' if current_calendar_id == CALENDARS['even'] else 'ODD'} calendar")
            print(f"🔄 Recurrence setting: {current_event['recurrence']}")
            return result

    except Exception as e:
        print(f"❌ Error in update_event: {str(e)}")
        raise

def delete_event(event_id, delete_mode='this'):
    """
    Xóa event với các mode khác nhau cho recurring events
    delete_mode: 'this', 'following', 'all'
    """
    try:
        if not event_id or event_id == "undefined":
            raise ValueError("Invalid event ID")
        
        print(f"🗑️ Deleting event: {event_id}, mode: {delete_mode}")
        
        # **KHỞI TẠO BIẾN deleted_from TRƯỚC**
        deleted_from = 'unknown'  # Khởi tạo giá trị mặc định
        
        # **THÊM LOGIC PHÂN BIỆT MASTER/INSTANCE**
        is_instance = '_' in event_id and event_id.count('_') >= 2
        master_event_id = None
        
        if is_instance:
            # Extract master event ID từ instance ID
            parts = event_id.rsplit('_', 1)
            if len(parts) == 2:
                master_event_id = parts[0]
                print(f"🔍 Instance detected, master ID: {master_event_id}")
        
        # Tìm event trên calendar nào
        current_event = None
        current_calendar_id = None
        
        for calendar_id in [CALENDARS['odd'], CALENDARS['even']]:
            try:
                event = calendar_service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
                current_event = event
                current_calendar_id = calendar_id
                
                # Nếu là instance và chưa có master_event_id, lấy từ recurringEventId
                if not master_event_id:
                    master_event_id = event.get('recurringEventId')
                
                print(f"✅ Found event in {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'} calendar")
                print(f"🔄 Event type: {'INSTANCE' if master_event_id else 'MASTER'}")
                print(f"🔄 Master event ID: {master_event_id}")
                break
            except HttpError as e:
                if e.resp.status == 404:
                    continue
                else:
                    raise
        
        if not current_event:
            raise ValueError(f"Event {event_id} not found in any calendar")
        
        # **CẬP NHẬT deleted_from DỰA TRÊN CALENDAR**
        deleted_from = 'EVEN' if current_calendar_id == CALENDARS['even'] else 'ODD'
        
        # **XỬ LÝ CÁC MODE XÓA**
        if delete_mode == 'all' and master_event_id:
            # Xóa toàn bộ series (xóa master event)
            print(f"🗑️ Deleting entire series (master: {master_event_id})")
            calendar_service.events().delete(
                calendarId=current_calendar_id,
                eventId=master_event_id
            ).execute()
            print(f"✅ Entire series deleted from {deleted_from} calendar")
            
            # Cũng thử xóa instance hiện tại nếu còn tồn tại
            try:
                calendar_service.events().delete(
                    calendarId=current_calendar_id,
                    eventId=event_id
                ).execute()
            except:
                pass  # Instance có thể đã bị xóa cùng master
            
            # Xóa extra data của cả master và instance
            remove_extra(master_event_id)
            remove_extra(event_id)
            
        elif delete_mode == 'following' and master_event_id:
            print(f"🗑️ Deleting this and following events from series")
            
            try:
                # 1. Lấy master event
                master_event = calendar_service.events().get(
                    calendarId=current_calendar_id,
                    eventId=master_event_id
                ).execute()
                
                # 2. Lấy start time của instance
                instance_start = current_event.get('start', {}).get('dateTime')
                if not instance_start:
                    raise ValueError("Cannot get instance start time")
                
                print(f"🕐 Instance to delete starts at: {instance_start}")
                
                # 3. Kiểm tra đây có phải instance đầu tiên không
                master_start = master_event.get('start', {}).get('dateTime')
                is_first_instance = False
                
                if master_start:
                    from datetime import datetime
                    master_dt = datetime.fromisoformat(master_start.replace('Z', '+00:00'))
                    instance_dt = datetime.fromisoformat(instance_start.replace('Z', '+00:00'))
                    
                    # Cho phép sai số 1 phút do timezone
                    time_diff = abs((instance_dt - master_dt).total_seconds())
                    is_first_instance = time_diff < 60
                    
                    if is_first_instance:
                        print(f"⚠️ This is the FIRST instance in the series")
                
                # 4. Xóa instance hiện tại
                calendar_service.events().delete(
                    calendarId=current_calendar_id,
                    eventId=event_id
                ).execute()
                print(f"✅ Instance {event_id} deleted")
                
                # 5. Xử lý master event
                if is_first_instance:
                    # Nếu là instance đầu tiên → xóa toàn bộ series
                    print(f"🗑️ First instance deleted, deleting entire series")
                    calendar_service.events().delete(
                        calendarId=current_calendar_id,
                        eventId=master_event_id
                    ).execute()
                    print(f"✅ Entire series deleted")
                    
                    # Xóa extra data của master
                    remove_extra(master_event_id)
                    
                else:
                    # Không phải instance đầu tiên → dùng UNTIL để dừng recurrence
                    print(f"🔄 Updating master event to stop BEFORE this instance")
                    
                    try:
                        # Cập nhật recurrence với UNTIL
                        updated_recurrence = stop_recurrence_at_instance(master_event, instance_start)
                        
                        if updated_recurrence:
                            master_event['recurrence'] = updated_recurrence
                            
                            # Cập nhật master event
                            calendar_service.events().update(
                                calendarId=current_calendar_id,
                                eventId=master_event_id,
                                body=master_event
                            ).execute()
                            print(f"✅ Master event updated with UNTIL")
                        else:
                            print(f"⚠️ Could not update recurrence")
                            
                    except Exception as update_error:
                        print(f"⚠️ Error updating master event: {update_error}")
                        # Tiếp tục dù có lỗi update master
                
                print(f"✅ Following delete completed from {deleted_from} calendar")
                
            except Exception as e:
                print(f"⚠️ Error in 'following' delete: {e}")
                # Fallback: chỉ xóa instance này
                try:
                    calendar_service.events().delete(
                        calendarId=current_calendar_id,
                        eventId=event_id
                    ).execute()
                    print(f"✅ Instance deleted (fallback)")
                except Exception as delete_error:
                    print(f"❌ Even fallback delete failed: {delete_error}")
                    raise
                
            # Xóa extra data của instance
            remove_extra(event_id)
            
        else:
            # Xóa single event, instance, hoặc master không recurring
            calendar_service.events().delete(
                calendarId=current_calendar_id,
                eventId=event_id
            ).execute()
            print(f"✅ Event deleted from {deleted_from} calendar (this mode)")
            
            # Xóa JSON extra
            remove_extra(event_id)
        
        return {
            "status": "deleted", 
            "from_calendar": deleted_from,
            "delete_mode": delete_mode,
            "master_event_id": master_event_id,
            "is_instance": is_instance
        }

    except Exception as e:
        print(f"❌ Error in delete_event: {str(e)}")
        raise