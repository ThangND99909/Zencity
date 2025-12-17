from google_calendar import calendar_service, CALENDARS
from googleapiclient.errors import HttpError
import json
from pathlib import Path
from recurrence_helper import build_recurrence_rule
from datetime import datetime, timedelta
import pytz

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
        
def handle_calendar_change(event_id, old_calendar_id, new_calendar_id, class_info, edit_mode, current_event=None):
    pass

# ========== HELPER FUNCTIONS ==========
def normalize_datetime_with_timezone(dt_str, timezone_str):
    """
    Normalize datetime string với timezone - FIXED cho đổi timezone
    """
    print(f"🕐 normalize_datetime_with_timezone:")
    print(f"   Input: {dt_str}")
    print(f"   Target timezone: {timezone_str}")
    
    if not dt_str:
        raise ValueError("Datetime string is empty")
    
    try:
        # Nếu đã có Z (UTC)
        if dt_str.endswith('Z'):
            print(f"   ⚠️ UTC datetime detected, converting to {timezone_str}")
            
            # Parse UTC time
            dt_utc = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            
            # Convert sang timezone target
            try:
                tz = pytz.timezone(timezone_str)
                dt_in_timezone = dt_utc.astimezone(tz)
                result = dt_in_timezone.isoformat()
                print(f"   ✅ Converted UTC→{timezone_str}: {dt_str} → {result}")
                return result
            except pytz.UnknownTimeZoneError:
                print(f"   ❌ Unknown timezone: {timezone_str}, keeping UTC")
                return dt_str
        
        # Nếu đã có timezone offset
        if 'T' in dt_str and ('+' in dt_str.split('T')[1] or '-' in dt_str.split('T')[1]):
            print(f"   ✅ Already has timezone offset: {dt_str}")
            
            try:
                # Parse datetime với timezone hiện tại
                dt_with_tz = datetime.fromisoformat(dt_str)
                
                # Kiểm tra xem có cần convert sang timezone mới không
                # (Luôn convert để đảm bảo đúng timezone target)
                try:
                    tz = pytz.timezone(timezone_str)
                    dt_converted = dt_with_tz.astimezone(tz)
                    result = dt_converted.isoformat()
                    print(f"   🔄 Converted to {timezone_str}: {result}")
                    return result
                except:
                    # Nếu không convert được, giữ nguyên
                    return dt_str
            except:
                # Nếu parse lỗi, giữ nguyên
                return dt_str
        
        # Không có timezone → thêm timezone
        print(f"   ⚠️ No timezone detected, adding: {timezone_str}")
        
        dt = datetime.fromisoformat(dt_str)
        try:
            tz = pytz.timezone(timezone_str)
            dt_aware = tz.localize(dt)
            result = dt_aware.isoformat()
            print(f"   ✅ After adding timezone: {result}")
            return result
        except pytz.UnknownTimeZoneError:
            print(f"   ❌ Unknown timezone: {timezone_str}, using UTC")
            return dt_str + "Z"
        
    except Exception as e:
        print(f"   ❌ Error in normalize_datetime: {e}")
        return dt_str

def validate_timezone(timezone_str):
    """Validate và chuẩn hóa timezone"""
    valid_timezones = [
        'Asia/Ho_Chi_Minh', 'America/Chicago', 'America/New_York', 
        'America/Los_Angeles', 'Europe/London', 'Europe/Paris',
        'Asia/Tokyo', 'Australia/Sydney', 'UTC',
        'America/Denver', 'Europe/Berlin', 'Asia/Seoul',
        'Asia/Singapore', 'Pacific/Auckland'
    ]
    
    if timezone_str not in valid_timezones:
        print(f"⚠️ Warning: Unknown timezone '{timezone_str}', using Asia/Ho_Chi_Minh")
        return 'Asia/Ho_Chi_Minh'
    return timezone_str

def build_event_description(class_info):
    """Tạo description chung cho event"""
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
        base_description += f"\nRecurrence: {recurrence_desc}"
    
    return base_description

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
    Xác định calendar dựa trên giờ bắt đầu (theo múi giờ Việt Nam)
    """
    try:
        if not start_datetime_str:
            print("⚠️ Empty datetime, using default calendar")
            return CALENDARS['odd']  # Mặc định calendar lẻ
        
        print(f"🔍 determine_calendar_by_hour INPUT: {start_datetime_str}")
        
        # Parse datetime string
        dt_str = start_datetime_str
        
        # Xử lý timezone: luôn convert về giờ Việt Nam
        if dt_str.endswith('Z'):
            # UTC time → convert to VN time
            dt_utc = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
            dt_vn = dt_utc.astimezone(vn_tz)
            hour = dt_vn.hour
            print(f"  ⚡ UTC → VN: {dt_utc.hour}:00 UTC → {dt_vn.hour}:00 VN")
            
        elif '+' in dt_str or dt_str.count('-') >= 3:
            # Có timezone offset
            try:
                dt_with_tz = datetime.fromisoformat(dt_str)
                # Convert to VN time
                vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                dt_vn = dt_with_tz.astimezone(vn_tz)
                hour = dt_vn.hour
                print(f"  ⚡ With tz → VN: {hour}:00 VN")
            except:
                # Fallback: parse as naive and assume VN time
                if 'T' in dt_str:
                    naive_part = dt_str.split('+')[0].split('-')[0] if '+' in dt_str else dt_str.split('-')[0]
                    naive_dt = datetime.fromisoformat(naive_part)
                    hour = naive_dt.hour
                    print(f"  ⚡ Fallback naive: {hour}:00 (assume VN)")
                else:
                    hour = 0
        
        else:
            # Không có timezone → giả sử là giờ Việt Nam
            dt_naive = datetime.fromisoformat(dt_str)
            hour = dt_naive.hour
            print(f"  ⚡ Naive datetime: {hour}:00 (assume VN)")
        
        # ⚠️ **QUAN TRỌNG: Sửa logic chẵn lẻ**
        # 3 giờ là LẺ → Calendar LẺ
        # Logic đúng: giờ lẻ (1, 3, 5, ...) → calendar ODD
        #              giờ chẵn (0, 2, 4, ...) → calendar EVEN
        
        print(f"  🔢 Hour in VN: {hour}h → {'CHẴN' if hour % 2 == 0 else 'LẺ'}")
        
        if hour % 2 == 0:  # Giờ CHẴN (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)
            print(f"🎯 Decision: Calendar EVEN")
            return CALENDARS['even']
        else:  # Giờ LẺ (1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23)
            print(f"🎯 Decision: Calendar ODD")
            return CALENDARS['odd']
            
    except Exception as e:
        print(f"❌ Error determining calendar by hour: {e}")
        print(f"📝 Raw datetime string: {start_datetime_str}")
        return CALENDARS['odd']  # Default to ODD calendar
    
def get_calendar_type_by_id(calendar_id):
    """Lấy loại calendar từ calendar_id"""
    if calendar_id == CALENDARS['odd']:
        return 'odd'
    elif calendar_id == CALENDARS['even']:
        return 'even'
    else:
        return 'unknown'

def handle_calendar_change(event_id, old_calendar_id, new_calendar_id, class_info, edit_mode, current_event=None):
    """
    Xử lý chuyển event từ calendar này sang calendar khác
    """
    try:
        print(f"🎯 ========== CALENDAR CHANGE ==========")
        print(f"📦 Event ID: {event_id}")
        print(f"🔄 From: {'EVEN' if old_calendar_id == CALENDARS['even'] else 'ODD'}")
        print(f"🔄 To: {'EVEN' if new_calendar_id == CALENDARS['even'] else 'ODD'}")
        print(f"📝 Edit mode: {edit_mode}")
        
        # Lấy thông tin từ event cũ nếu không có trong class_info
        if current_event:
            if 'name' not in class_info or not class_info['name']:
                class_info['name'] = current_event.get('summary', '')
            if 'zoom_link' not in class_info or not class_info['zoom_link']:
                class_info['zoom_link'] = current_event.get('location', '')
            if 'teacher' not in class_info:
                # Parse từ description cũ
                desc = current_event.get('description', '')
                if 'Teacher:' in desc:
                    teacher_line = [l for l in desc.split('\n') if 'Teacher:' in l]
                    if teacher_line:
                        class_info['teacher'] = teacher_line[0].replace('Teacher:', '').strip()
        
        # Xác định loại event
        is_recurring_instance = current_event and current_event.get('recurringEventId')
        is_master_event = current_event and current_event.get('recurrence')
        
        print(f"📊 Event type: {'MASTER' if is_master_event else 'INSTANCE' if is_recurring_instance else 'SINGLE'}")
        
        # 1. XÓA KHỎI CALENDAR CŨ
        try:
            calendar_service.events().delete(
                calendarId=old_calendar_id,
                eventId=event_id
            ).execute()
            print(f"✅ Deleted from old calendar")
            
            # Xóa extra data cũ
            remove_extra(event_id)
            
        except Exception as delete_error:
            print(f"⚠️ Delete error (might be already moved): {delete_error}")
        
        # 2. XỬ LÝ RECURRENCE THEO EDIT MODE
        timezone = validate_timezone(class_info.get('timezone', 'Asia/Ho_Chi_Minh'))
        
        start_normalized = normalize_datetime_with_timezone(
            class_info.get('start'), 
            timezone
        )
        end_normalized = normalize_datetime_with_timezone(
            class_info.get('end'), 
            timezone
        )
        
        # TẠO EVENT MỚI
        event_data = {
            'summary': class_info.get('name', 'Event'),
            'description': build_event_description(class_info),
            'location': class_info.get('zoom_link', ''),
            'start': {'dateTime': start_normalized, 'timeZone': timezone},
            'end': {'dateTime': end_normalized, 'timeZone': timezone},
        }
        
        # XỬ LÝ RECURRENCE
        if edit_mode in ['following', 'all'] and class_info.get('recurrence'):
            # Giữ nguyên recurrence
            rrule_list = build_recurrence_rule(class_info)
            event_data['recurrence'] = rrule_list
            print(f"🔄 Keeping recurrence for '{edit_mode}' mode")
            
        elif edit_mode == 'this' and (is_recurring_instance or is_master_event):
            # 'this' mode trên recurring event → tạo single event
            event_data['description'] += "\n(Single event - moved from recurring series)"
            print(f"🔄 Creating single event (no recurrence for 'this' mode)")
        
        # 3. TẠO TRONG CALENDAR MỚI
        result = calendar_service.events().insert(
            calendarId=new_calendar_id,
            body=event_data
        ).execute()
        
        new_event_id = result.get('id')
        print(f"✅ Created in new calendar: {new_event_id}")
        
        # 4. CẬP NHẬT EXTRA DATA VỚI CALENDAR MỚI
        update_extra(
            new_event_id,
            class_info.get('meeting_id', ''),
            class_info.get('passcode', ''),
            class_info.get('zoom_link', ''),
            class_info.get('classname', ''),
            new_calendar_id  # LƯU CALENDAR MỚI
        )
        
        print(f"✅ Calendar change completed successfully!")
        print(f"📊 Summary:")
        print(f"   - Old: {event_id} in {'EVEN' if old_calendar_id == CALENDARS['even'] else 'ODD'}")
        print(f"   - New: {new_event_id} in {'EVEN' if new_calendar_id == CALENDARS['even'] else 'ODD'}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in handle_calendar_change: {e}")
        import traceback
        traceback.print_exc()
        raise
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
                
                # **QUAN TRỌNG: CHỈNH SỬA Ở ĐÂY**
                # Sử dụng timeMin để chỉ lấy events tương lai
                events_result = calendar_service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,  # ⚠️ THÊM timeMin để chỉ lấy events tương lai
                    timeMax=time_max,
                    maxResults=2500,
                    singleEvents=True,  # ⚠️ QUAN TRỌNG: True để có instances
                    orderBy='startTime',
                    showDeleted=False
                ).execute()
                
                events = events_result.get('items', [])
                print(f"  📊 Found {len(events)} events")
                
                # **QUAN TRỌNG: LOG CHI TIẾT ĐỂ DEBUG**
                master_events = []
                instance_events = []
                regular_events = []
                
                for event in events:
                    if event.get('recurrence') and not event.get('recurringEventId'):
                        master_events.append(event)
                    elif event.get('recurringEventId'):
                        instance_events.append(event)
                    else:
                        regular_events.append(event)
                
                print(f"    👑 Master events: {len(master_events)}")
                print(f"    🔄 Instance events: {len(instance_events)}")
                print(f"    📌 Regular events: {len(regular_events)}")
                
                # **XỬ LÝ TỪNG EVENT**
                for event in events:
                    event_id = event.get('id')
                    
                    # Skip cancelled events
                    if event.get('status') == 'cancelled':
                        cancelled_count += 1
                        continue
                    
                    # **PHÂN LOẠI EVENT - SỬA LẠI LOGIC**
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
                        # **QUAN TRỌNG: MASTER EVENT - KHÔNG THÊM VÀO ALL_EVENTS**
                        event['_is_master'] = True
                        event['_is_instance'] = False
                        
                        # **SKIP MASTER EVENTS HOÀN TOÀN**
                        print(f"    🚫 Skipping master event: {event.get('summary', 'No title')}")
                        continue  # ⚠️ KHÔNG THÊM MASTER VÀO ALL_EVENTS
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
                
                print(f"    ✅ Added to display: {len([e for e in all_events if e.get('_calendar_id') == calendar_id])} events")
                
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
        total_instances = len([e for e in all_events if e.get('_is_instance')])
        total_regular = len([e for e in all_events if not e.get('_is_instance') and not e.get('_is_master')])
        
        print(f"📅 Total displayed: {len(all_events)} events")
        print(f"📊 Calendar breakdown: ODD: {len([e for e in all_events if e.get('_calendar_source') == 'odd'])}, EVEN: {len([e for e in all_events if e.get('_calendar_source') == 'even'])}")
        print(f"📈 Event types: {total_instances} instances, {total_regular} regular")
        
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
        timezone = validate_timezone(class_info.get('timezone', 'Asia/Ho_Chi_Minh'))
        print(f"🕐 Using validated timezone: {timezone}")
        
        # ✅ NORMALIZE DATETIME WITH TIMEZONE
        start_normalized = normalize_datetime_with_timezone(class_info['start'], timezone)
        end_normalized = normalize_datetime_with_timezone(class_info['end'], timezone)

        # ✅ TẠO DESCRIPTION
        description = build_event_description(class_info)
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
# ========== GOOGLE CALENDAR UPDATE FUNCTIONS ==========

def update_this_instance(instance_id, master_event_id, calendar_id, class_info):
    """
    Google Calendar 'this' mode: Only this instance
    """
    try:
        print(f"🎯 [GOOGLE] 'this' mode - Creating exception")
        
        # 1. Get instance and master
        instance = calendar_service.events().get(
            calendarId=calendar_id,
            eventId=instance_id
        ).execute()
        
        master_event = calendar_service.events().get(
            calendarId=calendar_id,
            eventId=master_event_id
        ).execute()
        
        instance_start = instance.get('start', {}).get('dateTime')
        if not instance_start:
            raise ValueError("No instance start time")
        
        # 2. Add EXDATE to master
        print(f"🔄 Adding EXDATE to master")
        from recurrence_utils import add_exdate_to_master
        
        updated_recurrence = add_exdate_to_master(master_event, instance_start)
        
        if updated_recurrence:
            master_event['recurrence'] = updated_recurrence
            calendar_service.events().update(
                calendarId=calendar_id,
                eventId=master_event_id,
                body=master_event
            ).execute()
            print(f"✅ Master updated with EXDATE")
        
        # 3. Delete old instance
        print(f"🔄 Deleting old instance")
        calendar_service.events().delete(
            calendarId=calendar_id,
            eventId=instance_id
        ).execute()
        remove_extra(instance_id)
        
        # 4. Create new independent event (NO RECURRENCE)
        print(f"🔄 Creating independent event")
        
        timezone = validate_timezone(class_info.get('timezone', 'Asia/Ho_Chi_Minh'))
        
        start_normalized = normalize_datetime_with_timezone(
            class_info['start'], 
            timezone
        )
        end_normalized = normalize_datetime_with_timezone(
            class_info['end'], 
            timezone
        )
        
        # Create event WITHOUT recurrence
        new_event = {
            'summary': class_info.get('name', master_event.get('summary', '')),
            'description': build_event_description(class_info) + "\n(Single event exception)",
            'location': class_info.get('zoom_link', master_event.get('location', '')),
            'start': {'dateTime': start_normalized, 'timeZone': timezone},
            'end': {'dateTime': end_normalized, 'timeZone': timezone},
        }
        
        # IMPORTANT: NO recurrence for independent event
        if 'recurrence' in new_event:
            del new_event['recurrence']
        
        result = calendar_service.events().insert(
            calendarId=calendar_id,
            body=new_event
        ).execute()
        
        new_event_id = result.get('id')
        print(f"✅ Created independent event: {new_event_id}")
        
        # 5. Update extra data
        update_extra(
            new_event_id,
            class_info.get('meeting_id', ''),
            class_info.get('passcode', ''),
            class_info.get('zoom_link', ''),
            class_info.get('classname', ''),
            calendar_id
        )
        
        return result
        
    except Exception as e:
        print(f"❌ Error in 'this' mode: {e}")
        raise



def update_single_event(event_id, calendar_id, class_info):
    """
    Update non-recurring event
    """
    try:
        print(f"🎯 [GOOGLE] Updating single event")
        
        event = calendar_service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        timezone = validate_timezone(class_info.get('timezone', 'Asia/Ho_Chi_Minh'))
        
        start_normalized = normalize_datetime_with_timezone(
            class_info['start'], 
            timezone
        )
        end_normalized = normalize_datetime_with_timezone(
            class_info['end'], 
            timezone
        )
        
        event['summary'] = class_info.get('name', event.get('summary'))
        event['description'] = build_event_description(class_info)
        event['location'] = class_info.get('zoom_link', '')
        event['start'] = {'dateTime': start_normalized, 'timeZone': timezone}
        event['end'] = {'dateTime': end_normalized, 'timeZone': timezone}
        
        # Remove recurrence for single event
        if 'recurrence' in event:
            del event['recurrence']
        
        result = calendar_service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()
        
        update_extra(
            event_id,
            class_info.get('meeting_id', ''),
            class_info.get('passcode', ''),
            class_info.get('zoom_link', ''),
            class_info.get('classname', ''),
            calendar_id
        )
        
        return result
        
    except Exception as e:
        print(f"❌ Error updating single event: {e}")
        raise


def update_event(event_id, class_info):
    
    try:
        edit_mode = class_info.get('edit_mode', 'this')
        for key, value in class_info.items():
            if key.startswith('_'):
                print(f"   - {key}: {value}")
        
        # **QUAN TRỌNG: Check nếu đây là instance ID nhưng gửi master ID**
        is_instance_id = ('_' in event_id and 
                         (event_id.count('_') >= 2 or 
                          '_R' in event_id or 
                          '_Z' in event_id))
        

        
        # Find which calendar has this event
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
                print(f"✅ Found in {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'} calendar")
                break
            except HttpError as e:
                if e.resp.status == 404:
                    continue
                else:
                    raise
        
        # **THỬ TÌM BẰNG MASTER ID NẾU KHÔNG TÌM THẤY**
        if not current_event and class_info.get('master_event_id'):
            print(f"🔄 Event {event_id} not found, trying master ID: {class_info['master_event_id']}")
            for calendar_id in [CALENDARS['odd'], CALENDARS['even']]:
                try:
                    event = calendar_service.events().get(
                        calendarId=calendar_id,
                        eventId=class_info['master_event_id']
                    ).execute()
                    current_event = event
                    current_calendar_id = calendar_id
                    event_id = class_info['master_event_id']  # Update to master ID
                    print(f"✅ Found MASTER in {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'} calendar")
                    break
                except HttpError as e:
                    if e.resp.status == 404:
                        continue
                    else:
                        raise
        
        if not current_event:
            raise ValueError(f"Event {event_id} not found in any calendar")
        
        # ⚠️ **XỬ LÝ EDIT_MODE='all' CHỈ CHO SINGLE EVENTS**
        if edit_mode == 'all':
            # KIỂM TRA: Chỉ áp dụng cho single events
            if current_event.get('recurrence'):
                print("⚠️ WARNING: 'all' mode not supported for recurring events")
                print("   Falling back to 'this' mode")
                edit_mode = 'this'  # Fallback
            elif current_event.get('recurringEventId'):
                print("⚠️ WARNING: 'all' mode not supported for recurring instances")
                print("   Falling back to 'this' mode")
                edit_mode = 'this'  # Fallback
            else:
                print("✅ 'all' mode for single event → recurring conversion")
                return handle_all_mode_for_single(event_id, current_calendar_id, class_info)
        
        new_start_time = class_info.get('start')
        new_calendar_id = None

        if new_start_time and new_start_time.strip():  # Thêm check không rỗng
            try:
                new_calendar_id = determine_calendar_by_hour(new_start_time)
                print(f"🔄 New hour analysis:")
                print(f"   - New start: {new_start_time}")
                print(f"   - Calendar: {'EVEN' if new_calendar_id == CALENDARS['even'] else 'ODD'}")
            except Exception as e:
                print(f"⚠️ Error analyzing new calendar: {e}")
                # Nếu không xác định được, giữ calendar cũ
                new_calendar_id = current_calendar_id

        # 3. NẾU CÓ THAY ĐỔI CALENDAR → XỬ LÝ
        if new_calendar_id and new_calendar_id != current_calendar_id:
            print(f"🎯 CALENDAR CHANGE DETECTED!")
            return handle_calendar_change(
                event_id=event_id,
                old_calendar_id=current_calendar_id,
                new_calendar_id=new_calendar_id,
                class_info=class_info,
                edit_mode=edit_mode,
                current_event=current_event
            )
        
        # **QUAN TRỌNG: Xác định master event ID với metadata từ frontend**
        master_event_id = None
        
        # Cách 1: Dùng từ frontend nếu có
        if class_info.get('master_event_id'):
            master_event_id = class_info['master_event_id']
            print(f"👑 Using master_event_id from frontend: {master_event_id}")
        
        # Cách 2: Từ event hiện tại
        elif current_event.get('recurringEventId'):
            master_event_id = current_event['recurringEventId']
            print(f"👑 This is INSTANCE, master ID: {master_event_id}")
        
        # Cách 3: Đây là master event
        elif current_event.get('recurrence'):
            master_event_id = event_id
            print(f"👑 This is MASTER event")
        
        print(f"🎯 Final master event ID: {master_event_id}")
        
        
        
        # Các mode khác
        if master_event_id and edit_mode == 'following':
            print(f"🎯 Mode 'following'")
            return update_following_events(event_id, master_event_id, current_calendar_id, class_info)
        
        elif master_event_id and edit_mode == 'this':
            print(f"🎯 Mode 'this'")
            return update_this_instance(event_id, master_event_id, current_calendar_id, class_info)
        
        else:
            # Non-recurring event
            print(f"🎯 Non-recurring event update")
            return update_single_event(event_id, current_calendar_id, class_info)
            
    except Exception as e:
        print(f"❌ Error in update_event: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def handle_all_mode_for_single(event_id, calendar_id, class_info):
    """
    Xử lý edit_mode='all' cho single event
    Thực chất là: xóa single cũ, tạo recurring mới
    """
    try:
        print("🔄 ========== 'all' MODE: Single → Recurring ==========")
        
        # 1. XÓA SINGLE EVENT CŨ
        print(f"🗑️ Deleting single event: {event_id}")
        calendar_service.events().delete(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        # Xóa extra data
        remove_extra(event_id)
        
        # 2. TẠO RECURRING EVENT MỚI
        print(f"🔄 Creating new recurring event")
        
        # Chuẩn bị data
        create_data = {
            'name': class_info.get('name', ''),
            'classname': class_info.get('classname', ''),
            'teacher': class_info.get('teacher', ''),
            'zoom_link': class_info.get('zoom_link', ''),
            'program': class_info.get('program', ''),
            'start': class_info.get('start'),
            'end': class_info.get('end'),
            'meeting_id': class_info.get('meeting_id', ''),
            'passcode': class_info.get('passcode', ''),
            'recurrence': class_info.get('recurrence', ''),
            'repeat_count': class_info.get('repeat_count', 1),
            'byday': class_info.get('byday', []),
            'bymonthday': class_info.get('bymonthday', []),
            'bymonth': class_info.get('bymonth', []),
            'timezone': class_info.get('timezone', 'Asia/Ho_Chi_Minh')
        }
        
        # Build recurrence
        recurrence_rule = build_recurrence_rule(create_data)
        create_data["rrule"] = [recurrence_rule] if recurrence_rule else None
        
        # Gọi hàm create có sẵn
        result = create_event(create_data)
        
        print(f"✅ Conversion completed!")
        return result
        
    except Exception as e:
        print(f"❌ Error in 'all' mode: {e}")
        raise
# ----------------- UPDATE FOLLOWING EVENTS -----------------
def update_following_events(instance_id, master_event_id, calendar_id, class_info):
    """
    Google Calendar 'following' mode - FIXED: Tạo thêm events nếu repeat_count > remaining
    """
    try:
        print(f"🎯 [FOLLOWING MODE FIXED] Starting...")
        
        # 1. Lấy instance và master
        current_instance = calendar_service.events().get(
            calendarId=calendar_id,
            eventId=instance_id
        ).execute()
        
        master_event = calendar_service.events().get(
            calendarId=calendar_id,
            eventId=master_event_id
        ).execute()
        
        original_instance_start = current_instance.get('start', {}).get('dateTime')
        if not original_instance_start:
            raise ValueError("Cannot get instance start time")
        
        # 2. ⚠️ **TÍNH TOÁN QUAN TRỌNG**
        # a) Lấy repeat_count từ REQUEST (số events user muốn trong series mới)
        request_repeat_count = class_info.get('repeat_count', 1)
        
        # b) Tính số events còn lại từ series cũ
        master_recurrence = master_event.get('recurrence', [])
        old_total_count = 1  # Mặc định
        rrule_freq = "DAILY"
        
        for rule in master_recurrence:
            if 'RRULE:' in rule:
                rrule_str = rule.replace('RRULE:', '')
                import re
                
                # Lấy FREQ
                freq_match = re.search(r'FREQ=(\w+)', rrule_str, re.IGNORECASE)
                if freq_match:
                    rrule_freq = freq_match.group(1).upper()
                
                # Lấy COUNT cũ
                count_match = re.search(r'COUNT=(\d+)', rrule_str, re.IGNORECASE)
                if count_match:
                    old_total_count = int(count_match.group(1))
                break
        
        # c) Tính instance index (instance thứ mấy)
        master_start = master_event.get('start', {}).get('dateTime')
        instance_index = 1
        
        if master_start:
            try:
                master_dt = datetime.fromisoformat(master_start.replace('Z', '+00:00'))
                instance_dt = datetime.fromisoformat(original_instance_start.replace('Z', '+00:00'))
                
                if rrule_freq == 'DAILY':
                    days_diff = (instance_dt - master_dt).days
                    instance_index = max(1, days_diff + 1)
                elif rrule_freq == 'WEEKLY':
                    weeks_diff = (instance_dt - master_dt).days // 7
                    instance_index = max(1, weeks_diff + 1)
                elif rrule_freq == 'MONTHLY':
                    year_diff = instance_dt.year - master_dt.year
                    month_diff = instance_dt.month - master_dt.month
                    total_months = (year_diff * 12) + month_diff
                    instance_index = max(1, total_months + 1)
            except:
                pass
        
        # d) Tính remaining events từ series cũ
        remaining_from_old = max(1, old_total_count - (instance_index - 1))
        
        print(f"📊 ========== CALCULATION ==========")
        print(f"   Old series: {old_total_count} events total")
        print(f"   This is instance #{instance_index}")
        print(f"   Remaining from old: {remaining_from_old} events")
        print(f"   Requested new count: {request_repeat_count} events")
        
        # ⚠️ **SO SÁNH: Có cần tạo thêm events không?**
        extra_events_needed = max(0, request_repeat_count - remaining_from_old)
        
        if extra_events_needed > 0:
            print(f"   ⭐ NEED TO CREATE {extra_events_needed} EXTRA EVENTS!")
        else:
            print(f"   📌 No extra events needed")
        
        # 3. DỪNG SERIES CŨ TRƯỚC INSTANCE NÀY
        print(f"🔄 Stopping old series...")
        updated_recurrence = stop_recurrence_at_instance(master_event, original_instance_start)
        
        if updated_recurrence:
            master_event['recurrence'] = updated_recurrence
            calendar_service.events().update(
                calendarId=calendar_id,
                eventId=master_event_id,
                body=master_event
            ).execute()
            print(f"✅ Old series stopped before instance #{instance_index}")
        
        # 4. XÓA INSTANCE CŨ
        print(f"🔄 Deleting old instance...")
        try:
            calendar_service.events().delete(
                calendarId=calendar_id,
                eventId=instance_id
            ).execute()
            remove_extra(instance_id)
        except Exception as e:
            print(f"⚠️ Could not delete instance: {e}")
        
        # 5. **TẠO SERIES MỚI VỚI ĐÚNG SỐ EVENTS**
        print(f"🔄 Creating new series...")
        
        timezone = validate_timezone(class_info.get('timezone', 'Asia/Ho_Chi_Minh'))
        
        start_normalized = normalize_datetime_with_timezone(
            class_info['start'], 
            timezone
        )
        end_normalized = normalize_datetime_with_timezone(
            class_info['end'], 
            timezone
        )
        
        # Xây dựng RRULE mới với repeat_count từ request
        recurrence_type = class_info.get('recurrence', rrule_freq)
        rrule_parts = [f"FREQ={recurrence_type}", f"COUNT={request_repeat_count}"]
        
        # Thêm các rules khác
        byday = class_info.get('byday', [])
        if byday and recurrence_type == "WEEKLY":
            rrule_parts.append(f"BYDAY={','.join(byday)}")
        
        bymonthday = class_info.get('bymonthday', [])
        if bymonthday and recurrence_type == "MONTHLY":
            rrule_parts.append(f"BYMONTHDAY={','.join(map(str, bymonthday))}")
        
        if recurrence_type == "YEARLY":
            bymonth = class_info.get('bymonth', [])
            if bymonth:
                rrule_parts.append(f"BYMONTH={','.join(map(str, bymonth))}")
            if bymonthday:
                rrule_parts.append(f"BYMONTHDAY={','.join(map(str, bymonthday))}")
        
        rrule_parts.append("INTERVAL=1")
        
        new_rrule_str = ";".join(rrule_parts)
        rrule_list = [f"RRULE:{new_rrule_str}"]
        
        # Tạo event mới
        description = build_event_description(class_info)
        description += f"\n(New series: {request_repeat_count} events)"
        
        if extra_events_needed > 0:
            description += f" [+{extra_events_needed} new events]"
        
        new_event = {
            'summary': class_info.get('name', master_event.get('summary', '')),
            'description': description,
            'location': class_info.get('zoom_link', master_event.get('location', '')),
            'start': {'dateTime': start_normalized, 'timeZone': timezone},
            'end': {'dateTime': end_normalized, 'timeZone': timezone},
            'recurrence': rrule_list
        }
        
        result = calendar_service.events().insert(
            calendarId=calendar_id,
            body=new_event
        ).execute()
        
        new_event_id = result.get('id')
        
        # 6. CẬP NHẬT EXTRA DATA
        update_extra(
            new_event_id,
            class_info.get('meeting_id', ''),
            class_info.get('passcode', ''),
            class_info.get('zoom_link', ''),
            class_info.get('classname', ''),
            calendar_id
        )
        
        print(f"✅ 'following' mode completed!")
        print(f"   Summary:")
        print(f"   - Old series: {old_total_count} events (stopped at #{instance_index-1})")
        print(f"   - New series: {request_repeat_count} events")
        print(f"   - Extra events created: {extra_events_needed}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in update_following_events: {e}")
        import traceback
        traceback.print_exc()
        raise

def calculate_event_dates(start_dt, recurrence_type, count, byday=None, interval=1):
    """
    Tính toán dates cho các events trong series
    """
    from datetime import datetime, timedelta
    
    dates = [start_dt]
    
    if recurrence_type == "DAILY":
        for i in range(1, count):
            next_date = start_dt + timedelta(days=i * interval)
            dates.append(next_date)
    
    elif recurrence_type == "WEEKLY":
        # Map day codes to weekday numbers
        day_map = {'MO': 0, 'TU': 1, 'WE': 2, 'TH': 3, 'FR': 4, 'SA': 5, 'SU': 6}
        
        if byday:
            target_days = [day_map.get(day.upper(), 0) for day in byday]
        else:
            # Mặc định: cùng ngày trong tuần
            target_days = [start_dt.weekday()]
        
        week_count = 0
        current_date = start_dt
        
        while len(dates) < count:
            current_date = current_date + timedelta(days=1)
            week_count = (current_date - start_dt).days // 7
            
            if week_count % interval == 0 and current_date.weekday() in target_days:
                dates.append(current_date)
    
    elif recurrence_type == "MONTHLY":
        for i in range(1, count):
            # Thêm i tháng
            year = start_dt.year + (start_dt.month + i - 1) // 12
            month = (start_dt.month + i - 1) % 12 + 1
            day = min(start_dt.day, 28)  # Đơn giản hóa
            
            try:
                next_date = datetime(year, month, day, start_dt.hour, start_dt.minute)
                dates.append(next_date)
            except:
                # Fallback: thêm 30 ngày
                next_date = start_dt + timedelta(days=30 * i)
                dates.append(next_date)
    
    return dates[:count]  # Đảm bảo đúng số lượng

# ----------------- DELETE -----------------
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