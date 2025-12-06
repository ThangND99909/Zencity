# backend/calendar_crud.py
from google_calendar import calendar_service, CALENDARS
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
    Lấy events từ các calendar
    calendar_type: 'odd', 'even', 'both'
    """
    try:
        all_events = []
        cancelled_count = 0
        
        # Xác định calendars cần lấy
        if calendar_type == 'odd':
            calendar_ids = [CALENDARS['odd']]
        elif calendar_type == 'even':
            calendar_ids = [CALENDARS['even']]
        else:  # 'both' mặc định
            calendar_ids = [CALENDARS['odd'], CALENDARS['even']]
        
        print(f"🔄 Fetching events from {len(calendar_ids)} calendar(s): {calendar_type}")
        
        now = datetime.utcnow()
        time_min = now.isoformat() + 'Z'
        time_max = (now + timedelta(days=60)).isoformat() + 'Z'
        
        for calendar_id in calendar_ids:
            try:
                print(f"  📅 Fetching from calendar: {get_calendar_type_by_id(calendar_id)}")
                
                events_result = calendar_service.events().list(
                    calendarId=calendar_id,
                    timeMax=time_max,
                    maxResults=2500,
                    singleEvents=True,
                    orderBy='startTime',
                    showDeleted=False
                ).execute()
                
                events = events_result.get('items', [])
                print(f"  📊 Found {len(events)} events in calendar {get_calendar_type_by_id(calendar_id)}")
                
                # Thêm metadata để phân biệt calendar source
                for event in events:
                    event['_calendar_source'] = get_calendar_type_by_id(calendar_id)
                    event['_calendar_id'] = calendar_id
                
                all_events.extend(events)
                
            except HttpError as error:
                print(f"❌ Error fetching from calendar {calendar_id}: {error}")
                continue
            except Exception as e:
                print(f"❌ Unexpected error with calendar {calendar_id}: {e}")
                continue
        
        # Xử lý và filter events
        active_events = []
        
        for event in all_events:
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
        
        # Gộp thêm meeting_id và passcode từ extra data
        extra = load_extra()
        for e in active_events:
            eid = e.get('id')
            if eid in extra:
                e['zoom_link'] = extra[eid].get('zoom_link', '')
                e['meeting_id'] = extra[eid].get('meeting_id', '')
                e['passcode'] = extra[eid].get('passcode', '')
                e['classname'] = extra[eid].get('classname', '')
                # Lấy calendar_id từ extra nếu có
                if 'calendar_id' in extra[eid]:
                    e['calendar_id'] = extra[eid]['calendar_id']
        
        print(f"📅 Total: {len(active_events)} active events (filtered {cancelled_count} cancelled events)")
        print(f"📊 Calendar breakdown: ODD: {len([e for e in active_events if e.get('_calendar_source') == 'odd'])}, EVEN: {len([e for e in active_events if e.get('_calendar_source') == 'even'])}")
        
        return active_events
        
    except Exception as e:
        print(f"❌ Error in list_events: {e}")
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

def delete_event(event_id):
    """
    Xóa event từ bất kỳ calendar nào
    """
    try:
        if not event_id or event_id == "undefined":
            raise ValueError("Invalid event ID")
        
        print(f"🗑️ Deleting event: {event_id}")
        
        # Thử xóa từ cả 2 calendars
        deleted = False
        deleted_from = None
        
        for calendar_id in [CALENDARS['odd'], CALENDARS['even']]:
            try:
                calendar_service.events().delete(
                    calendarId=calendar_id, 
                    eventId=event_id
                ).execute()
                deleted = True
                deleted_from = 'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'
                print(f"✅ Event deleted from {deleted_from} calendar")
                break
            except HttpError as e:
                if e.resp.status == 404:
                    continue  # Không tìm thấy trong calendar này
                else:
                    raise
        
        if not deleted:
            raise ValueError(f"Event {event_id} not found in any calendar")
        
        # Xóa JSON extra
        remove_extra(event_id)
        
        return {"status": "deleted", "from_calendar": deleted_from}

    except Exception as e:
        print(f"❌ Error in delete_event: {str(e)}")
        raise