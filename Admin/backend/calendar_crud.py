from google_calendar import calendar_service, CALENDARS
from googleapiclient.errors import HttpError
import json
from pathlib import Path
from recurrence_helper import build_recurrence_rule
from datetime import datetime, timedelta, timezone
import pytz
from calendar_utils import force_delete_event_by_summary_and_time

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
    ✅ Google Calendar-like normalization:
       - Nếu datetime là UTC (có 'Z'), convert sang target timezone.
       - Nếu datetime có offset (+07:00), convert sang target timezone.
       - Nếu không có offset (naive), assume local rồi thêm timezone.
       - Luôn trả về ISO 8601 có offset, giúp hiển thị đúng khi đổi timezone.
    """
    print(f"🕐 normalize_datetime_with_timezone:")
    print(f"   Input: {dt_str}")
    print(f"   Target timezone: {timezone_str}")

    if not dt_str:
        raise ValueError("Datetime string is empty")

    timezone_str = validate_timezone(timezone_str)
    tz = pytz.timezone(timezone_str)

    try:
        # === UTC dạng ...Z ===
        if dt_str.endswith('Z'):
            dt_utc = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            dt_local = dt_utc.astimezone(tz)
            result = dt_local.isoformat()
            print(f"   ✅ Converted UTC→{timezone_str}: {dt_str} → {result}")
            return result

        # === Đã có offset ===
        if 'T' in dt_str and ('+' in dt_str.split('T')[1] or '-' in dt_str.split('T')[1]):
            dt_with_tz = datetime.fromisoformat(dt_str)
            dt_converted = dt_with_tz.astimezone(tz)
            result = dt_converted.isoformat()
            print(f"   🔄 Converted offset→{timezone_str}: {result}")
            return result

        # === Không có timezone (naive) ===
        dt_naive = datetime.fromisoformat(dt_str)
        dt_localized = tz.localize(dt_naive)
        result = dt_localized.isoformat()
        print(f"   ⚙️ Localized naive datetime: {result}")
        return result

    except Exception as e:
        print(f"   ❌ Error normalize_datetime_with_timezone: {e}")
        return dt_str

def validate_timezone(tz_str: str) -> str:
    """
    ✅ Validate timezone theo chuẩn Google Calendar (dùng pytz).
    - Cho phép tất cả timezone hợp lệ (VD: Asia/Shanghai, America/Toronto)
    - Nếu không hợp lệ, fallback về 'Asia/Ho_Chi_Minh'
    """
    # Alias thông dụng (đề phòng frontend gửi tên khác)
    aliases = {
        "Asia/Saigon": "Asia/Ho_Chi_Minh",
        "Asia/HoChiMinh": "Asia/Ho_Chi_Minh",
    }

    # Chuẩn hóa tên alias
    tz_str = aliases.get(tz_str, tz_str)

    try:
        pytz.timezone(tz_str)
        return tz_str
    except pytz.UnknownTimeZoneError:
        print(f"⚠️ Warning: Unknown timezone '{tz_str}', fallback to 'Asia/Ho_Chi_Minh'")
        return "Asia/Ho_Chi_Minh"

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
                    #timeMin=time_min,  # ⚠️ THÊM timeMin để chỉ lấy events tương lai
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
    Tạo event với đầy đủ hỗ trợ:
    - Recurrence (lặp lại)
    - Calendar chẵn/lẻ tự động dựa trên giờ VN sau convert
    - Giữ giờ gốc cho grid view
    - Tự động move calendar khi đổi timezone
    """
    try:
        from datetime import datetime
        import pytz
        import ssl

        print(f"🎯 ========== CREATE EVENT ==========")
        print(f"📥 Received class_info: {class_info}")

        # 1️⃣ XÁC ĐỊNH TIMEZONE NGƯỜI DÙNG
        timezone = validate_timezone(class_info.get('timezone', 'Asia/Ho_Chi_Minh'))
        tz = pytz.timezone(timezone)
        print(f"🕐 Using timezone: {timezone}")

        # 2️⃣ NORMALIZE START/END DATETIME
        start_iso = normalize_datetime_with_timezone(class_info['start'], timezone)
        end_iso = normalize_datetime_with_timezone(class_info['end'], timezone)

        # 3️⃣ CHUYỂN START SANG GIỜ VN để xác định calendar chẵn/lẻ
        dt_start = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
        dt_vn = dt_start.astimezone(pytz.timezone('Asia/Ho_Chi_Minh'))
        hour_vn = dt_vn.hour
        print(f"🌏 Start time in VN: {dt_vn.strftime('%Y-%m-%d %H:%M')} → Hour: {hour_vn}")

        # 4️⃣ CHỌN CALENDAR DỰA TRÊN GIỜ VN
        if hour_vn % 2 == 0:
            calendar_id = CALENDARS['even']
            print(f"🎯 Selected calendar: EVEN")
        else:
            calendar_id = CALENDARS['odd']
            print(f"🎯 Selected calendar: ODD")

        # 5️⃣ TẠO DESCRIPTION
        description = build_event_description(class_info)

        # 6️⃣ TẠO EVENT OBJECT
        event = {
            'summary': class_info['name'],
            'description': description,
            'location': class_info.get('zoom_link', ''),
            'start': {'dateTime': start_iso, 'timeZone': timezone},
            'end': {'dateTime': end_iso, 'timeZone': timezone},
            'recurrence': class_info.get('rrule', [])
        }

        # 7️⃣ GỬI LÊN GOOGLE CALENDAR
        try:
            result = calendar_service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
        except ssl.SSLError as ssl_err:
            # SSL error qua Cloudflare tunnel nhưng event vẫn được tạo
            if "LENGTH_MISMATCH" in str(ssl_err) or "internal error" in str(ssl_err):
                print(f"⚠️  SSL warning (event may be created): {ssl_err}")
                # Thử lấy event gần nhất theo summary + time để verify
                try:
                    events = calendar_service.events().list(
                        calendarId=calendar_id,
                        q=class_info['name'],
                        maxResults=1,
                        orderBy='startTime',
                        singleEvents=True
                    ).execute()
                    if events.get('items'):
                        result = events['items'][0]
                        print(f"✅ Event verified as created (found by search)")
                    else:
                        raise ssl_err
                except:
                    raise ssl_err
            else:
                raise ssl_err
        event_id = result.get('id')

        # 8️⃣ LƯU EXTRA DATA
        add_extra(
            event_id,
            class_info.get('meeting_id', ''),
            class_info.get('passcode', ''),
            class_info.get('zoom_link', ''),
            class_info.get('classname', ''),
            calendar_id
        )

        print(f"✅ Event created in {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'} calendar")

        # 9️⃣ TỰ ĐỘNG MOVE NẾU MÚI GIỜ THAY ĐỔI → GIỐNG FOLLOWING MODE
        try:
            new_dt_vn = datetime.fromisoformat(start_iso.replace('Z', '+00:00')).astimezone(pytz.timezone('Asia/Ho_Chi_Minh'))
            new_hour_vn = new_dt_vn.hour
            new_calendar_id = CALENDARS['even'] if new_hour_vn % 2 == 0 else CALENDARS['odd']

            if new_calendar_id != calendar_id:
                print(f"🔄 Timezone change detected → moving event to new calendar")
                moved = calendar_service.events().move(
                    calendarId=calendar_id,
                    eventId=event_id,
                    destination=new_calendar_id
                ).execute()
                calendar_id = new_calendar_id
                print(f"✅ Event moved to {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'} calendar")
        except Exception as e:
            print(f"⚠️ Could not auto-move event: {e}")

        return result

    except Exception as e:
        # Xử lý SSL errors riêng biệt
        if isinstance(e, ssl.SSLError) and ("LENGTH_MISMATCH" in str(e) or "internal error" in str(e)):
            print(f"⚠️  SSL warning (non-critical): {e}")
            print(f"💡 This is a known issue with Python 3.13 + Cloudflare tunnel")
        else:
            print(f"❌ Error in create_event: {e}")
        import traceback
        traceback.print_exc()
        raise

# ========== GOOGLE CALENDAR UPDATE FUNCTIONS ==========

def update_this_instance(instance_id, master_event_id, calendar_id, class_info):
    """
    ✅ Google Calendar 'this' mode (Only this instance)
       - Cập nhật instance riêng lẻ trong chuỗi lặp.
       - Ngắt instance khỏi chuỗi gốc (thêm EXDATE vào master).
       - Tạo event độc lập (no recurrence).
       - Giữ nguyên giờ local, đổi UTC offset nếu đổi timezone.
       - Tự động di chuyển sang calendar chẵn/lẻ nếu giờ thay đổi.
    """
    try:
        from datetime import datetime
        import pytz
        from googleapiclient.errors import HttpError

        print(f"🎯 [GOOGLE] 'this' mode - Creating exception")

        # 1️⃣ Lấy instance và master
        instance = calendar_service.events().get(
            calendarId=calendar_id, eventId=instance_id
        ).execute()

        master_event = calendar_service.events().get(
            calendarId=calendar_id, eventId=master_event_id
        ).execute()

        instance_start = instance.get("start", {}).get("dateTime")
        if not instance_start:
            raise ValueError("⚠️ No instance start time found")

        # 2️⃣ Thêm EXDATE vào master để loại instance ra khỏi chuỗi
        print(f"🔄 Adding EXDATE to master (remove instance from series)")
        from recurrence_utils import add_exdate_to_master

        updated_recurrence = add_exdate_to_master(master_event, instance_start)

        if updated_recurrence:
            master_event["recurrence"] = updated_recurrence
            calendar_service.events().update(
                calendarId=calendar_id,
                eventId=master_event_id,
                body=master_event
            ).execute()
            print(f"✅ Master updated with EXDATE")

        # 3️⃣ Xóa instance cũ khỏi calendar
        print(f"🗑️ Deleting old instance from series")
        calendar_service.events().delete(
            calendarId=calendar_id, eventId=instance_id
        ).execute()
        remove_extra(instance_id)

        # 4️⃣ Tạo event mới độc lập
        print(f"🆕 Creating new independent event (detached from series)")

        timezone = validate_timezone(class_info.get("timezone", "Asia/Ho_Chi_Minh"))
        tz = pytz.timezone(timezone)

        # 🕐 Giữ nguyên giờ local, đổi UTC offset tương ứng
        start_normalized = normalize_datetime_with_timezone(
            class_info["start"], timezone
        )
        end_normalized = normalize_datetime_with_timezone(
            class_info["end"], timezone
        )

        new_event = {
            "summary": class_info.get("name", master_event.get("summary", "")),
            "description": build_event_description(class_info) + "\n(Single event exception)",
            "location": class_info.get("zoom_link", master_event.get("location", "")),
            "start": {"dateTime": start_normalized, "timeZone": timezone},
            "end": {"dateTime": end_normalized, "timeZone": timezone},
        }

        # 🔒 Không recurrence
        if "recurrence" in new_event:
            del new_event["recurrence"]

        result = calendar_service.events().insert(
            calendarId=calendar_id, body=new_event, sendUpdates="all"
        ).execute()

        new_event_id = result.get("id")
        print(f"✅ Created independent event: {new_event_id}")

        # 5️⃣ Ghi metadata bổ sung
        update_extra(
            new_event_id,
            class_info.get("meeting_id", ""),
            class_info.get("passcode", ""),
            class_info.get("zoom_link", ""),
            class_info.get("classname", ""),
            calendar_id,
        )

        print(f"✅ Metadata updated for {new_event_id}")
        print(f"   Timezone: {timezone}")
        print(f"   Start: {start_normalized}")

        # ==========================================================
        # 🟢 PHẦN MỚI: Tự động di chuyển instance sang calendar chẵn / lẻ
        # ==========================================================
        try:
            new_calendar_id = determine_calendar_by_hour(start_normalized)
            if new_calendar_id != calendar_id:
                print(f"🎯 THIS MODE: Hour changed → moving instance to new calendar")
                print(f"   From: {calendar_id}")
                print(f"   To:   {new_calendar_id}")

                moved = calendar_service.events().move(
                    calendarId=calendar_id,
                    eventId=new_event_id,
                    destination=new_calendar_id
                ).execute()

                print(f"✅ Instance moved successfully to new calendar")
                calendar_id = new_calendar_id
        except Exception as e:
            print(f"⚠️ Could not move instance to new calendar: {e}")

        return result

    except Exception as e:
        print(f"❌ Error in 'this' mode: {e}")
        import traceback
        traceback.print_exc()
        raise



def update_single_event(event_id, calendar_id, class_info):
    """
    ✅ Update non-recurring event (giữ UTC datetime, chỉ đổi timezone để Google Calendar hiển thị đúng ± giờ)
    """
    try:
        print(f"🎯 [GOOGLE] Updating single event")

        # 🟢 Lấy event hiện tại từ Google Calendar
        event = calendar_service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()

        # 🧭 Chuẩn hóa timezone
        timezone = validate_timezone(class_info.get('timezone', 'Asia/Ho_Chi_Minh'))

        # ⚙️ Giữ nguyên UTC datetime (ISO dạng ...Z)
        start_utc = class_info['start']   # ví dụ: "2025-12-18T07:00:00Z"
        end_utc = class_info['end']       # ví dụ: "2025-12-18T08:00:00Z"

        # 🕓 Xác định xem người dùng có đổi timezone thực sự không
        original_timezone = event.get("start", {}).get("timeZone", "Asia/Ho_Chi_Minh")
        timezone_changed = original_timezone != timezone

        print(f"🕐 Original timezone: {original_timezone}")
        print(f"🕐 New timezone: {timezone}")
        print(f"🔍 Timezone changed? {timezone_changed}")

        # Nếu người dùng đổi timezone thật sự (VD: GMT+8 → GMT+7)
        if timezone_changed:
            # Chuyển giờ local giữ nguyên, tính lại UTC tương ứng
            local_tz = pytz.timezone(timezone)
            start_local = datetime.fromisoformat(class_info["start"].replace("Z", "+00:00")).astimezone(local_tz)
            end_local = datetime.fromisoformat(class_info["end"].replace("Z", "+00:00")).astimezone(local_tz)
            start_iso = start_local.isoformat()
            end_iso = end_local.isoformat()
            print(f"🧭 Converted to new timezone: {start_iso} → {end_iso}")
        else:
            # Chỉ đổi hiển thị, giữ nguyên UTC
            start_iso = class_info["start"]
            end_iso = class_info["end"]

        # 🔄 Cập nhật nội dung event
        event['summary'] = class_info.get('name', event.get('summary'))
        event['description'] = build_event_description(class_info)
        event['location'] = class_info.get('zoom_link', '')

        # 🕐 Cập nhật start/end: giữ nguyên UTC, chỉ đổi timezone metadata
        event['start'] = {
            'dateTime': start_iso,
            'timeZone': timezone
        }
        event['end'] = {
            'dateTime': end_iso,
            'timeZone': timezone
        }

        # 🧹 Xóa recurrence nếu là single event
        if 'recurrence' in event:
            del event['recurrence']

        # 🌏 Force timezone update (nếu user đổi múi giờ)
        if event['start'].get('timeZone') != timezone:
            print(f"🌏 Updating start timezone → {timezone}")
            event['start']['timeZone'] = timezone
        if event['end'].get('timeZone') != timezone:
            print(f"🌏 Updating end timezone → {timezone}")
            event['end']['timeZone'] = timezone

        # 💾 Gửi lên Google Calendar — phải có sendUpdates='all' để refresh grid view
        result = calendar_service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
            sendUpdates='all'
        ).execute()

        # 🧩 Cập nhật dữ liệu mở rộng
        update_extra(
            event_id,
            class_info.get('meeting_id', ''),
            class_info.get('passcode', ''),
            class_info.get('zoom_link', ''),
            class_info.get('classname', ''),
            calendar_id
        )

        print(f"✅ Event updated successfully with timezone {timezone}")
        print(f"   Start: {start_utc}")
        print(f"   End:   {end_utc}")
        print(f"   timeZone: {timezone}")

        return result

    except Exception as e:
        print(f"❌ Error updating single event: {e}")
        import traceback
        traceback.print_exc()
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
        # 🔍 Xác định master_event_id sớm
        master_event_id = None

        # Nếu frontend đã gửi
        if class_info.get("master_event_id"):
            master_event_id = class_info["master_event_id"]
            print(f"👑 Using master_event_id from frontend: {master_event_id}")

        # Nếu là instance (có recurringEventId)
        elif current_event.get("recurringEventId"):
            master_event_id = current_event["recurringEventId"]
            print(f"👑 This is INSTANCE, master ID: {master_event_id}")

        # Nếu chính nó là master
        elif current_event.get("recurrence"):
            master_event_id = event_id
            print(f"👑 This is MASTER event: {master_event_id}")
        
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
            print(f"🎯 CALENDAR CHANGE DETECTED! ({current_calendar_id} → {new_calendar_id})")

            # ⚠️ Nếu đang ở chế độ 'following' → KHÔNG di chuyển calendar, chỉ update master recurrence
            if edit_mode == "following":
                print("⚠️ Edit mode = 'following' → Bỏ qua di chuyển calendar, chỉ cập nhật recurrence")
                return update_following_events(
                    event_id, master_event_id, current_calendar_id, class_info
                )
            
            # 🧩 Ngược lại: cho phép di chuyển
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
def stop_recurrence_at_instance(master_event, instance_start_iso):
    """
    ✅ Dừng chuỗi lặp hiện tại (master) trước instance được chọn.
    Sử dụng UNTIL= theo định dạng RFC5545: YYYYMMDDTHHMMSSZ
    """
    import re
    import pytz

    if not master_event.get("recurrence"):
        return master_event

    rrule_str = master_event["recurrence"][0].replace("RRULE:", "")
    rrule_parts = rrule_str.split(";")

    new_parts = []
    for part in rrule_parts:
        if not part.startswith("COUNT=") and not part.startswith("UNTIL="):
            new_parts.append(part)

    # ⚙️ Chuẩn hóa UNTIL (RFC5545)
    dt = datetime.fromisoformat(instance_start_iso.replace("Z", "+00:00"))
    until_str = dt.astimezone(pytz.utc).strftime("%Y%m%dT%H%M%SZ")  # ✅ dạng hợp lệ
    new_rrule = "RRULE:" + ";".join(new_parts + [f"UNTIL={until_str}"])

    master_event["recurrence"] = [new_rrule]
    print(f"🧩 stop_recurrence_at_instance → New RRULE: {new_rrule}")
    return master_event


def update_following_events(instance_id, master_event_id, calendar_id, class_info):
    """
    ✅ Google Calendar 'following' mode (chuẩn hành vi gốc)
       - Giữ nguyên chuỗi cũ (trước instance).
       - Dừng master tại instance này (bằng UNTIL).
       - Tạo chuỗi mới bắt đầu từ instance hiện tại.
       - Giữ nguyên giờ local, đổi UTC offset nếu đổi timezone.
       - Tự động move sang calendar chẵn/lẻ nếu cần.
    """
    try:
        from datetime import datetime
        import pytz, re
        from googleapiclient.errors import HttpError

        print("🎯 [FOLLOWING MODE - SPLIT SERIES] Starting...")

        # 1️⃣ Lấy instance và master
        instance = calendar_service.events().get(
            calendarId=calendar_id, eventId=instance_id
        ).execute()
        master = calendar_service.events().get(
            calendarId=calendar_id, eventId=master_event_id
        ).execute()

        if not instance or not master:
            raise ValueError("❌ Không tìm thấy instance hoặc master event")

        # 2️⃣ Timezone hiện tại
        original_tz = master.get("start", {}).get("timeZone", "Asia/Ho_Chi_Minh")
        timezone = validate_timezone(class_info.get("timezone", original_tz))
        tz = pytz.timezone(timezone)
        print(f"🌏 Timezone: {original_tz} → {timezone}")

        # 3️⃣ Lấy thông tin recurrence từ master
        master_recurrence = master.get("recurrence", [])
        rrule_freq = "DAILY"
        for rule in master_recurrence:
            if "RRULE:" in rule:
                rule_str = rule.replace("RRULE:", "")
                freq_match = re.search(r"FREQ=(\w+)", rule_str)
                if freq_match:
                    rrule_freq = freq_match.group(1).upper()
                break

        instance_start = instance.get("start", {}).get("dateTime")
        master_start = master.get("start", {}).get("dateTime")
        if not instance_start or not master_start:
            raise ValueError("⚠️ Missing start time")

        instance_dt = datetime.fromisoformat(instance_start.replace("Z", "+00:00"))
        master_dt = datetime.fromisoformat(master_start.replace("Z", "+00:00"))

        # 4️⃣ Dừng chuỗi cũ tại instance
        print(f"🧩 Stopping old series at {instance_start}")
        updated_master = stop_recurrence_at_instance(master, instance_start)
        calendar_service.events().update(
            calendarId=calendar_id,
            eventId=master_event_id,
            body=updated_master,
        ).execute()
        print("✅ Old series updated (stopped before instance)")

        # 5️⃣ Tạo chuỗi mới bắt đầu từ instance này
        start_local = datetime.fromisoformat(class_info["start"].replace("Z", "+00:00")).astimezone(tz)
        end_local = datetime.fromisoformat(class_info["end"].replace("Z", "+00:00")).astimezone(tz)
        start_iso = start_local.isoformat()
        end_iso = end_local.isoformat()

        new_count = class_info.get("repeat_count", 1)
        new_rrule = [f"RRULE:FREQ={rrule_freq};COUNT={new_count};INTERVAL=1"]

        if class_info.get("byday") and rrule_freq == "WEEKLY":
            new_rrule = [
                f"RRULE:FREQ=WEEKLY;COUNT={new_count};BYDAY={','.join(class_info['byday'])}"
            ]
        elif class_info.get("bymonthday") and rrule_freq == "MONTHLY":
            new_rrule = [
                f"RRULE:FREQ=MONTHLY;COUNT={new_count};BYMONTHDAY={','.join(map(str, class_info['bymonthday']))}"
            ]

        new_event = {
            "summary": class_info.get("name", master.get("summary", "")),
            "description": build_event_description(class_info) + "\n(New following series)",
            "location": class_info.get("zoom_link", master.get("location", "")),
            "start": {"dateTime": start_iso, "timeZone": timezone},
            "end": {"dateTime": end_iso, "timeZone": timezone},
            "recurrence": new_rrule,
        }

        print(f"🆕 Creating new series from instance {instance_start}")
        result = calendar_service.events().insert(
            calendarId=calendar_id, body=new_event, sendUpdates="all"
        ).execute()

        new_event_id = result.get("id")
        print(f"✅ Created new master for following series: {new_event_id}")

        # 6️⃣ Xóa instance cũ vì đã tách ra thành chuỗi mới
        try:
            print(f"🗑️ Deleting old instance {instance_id} (now part of new series)")
            calendar_service.events().delete(
                calendarId=calendar_id,
                eventId=instance_id
            ).execute()
            print(f"✅ Old instance {instance_id} deleted successfully")
            remove_extra(instance_id)
        except Exception as e:
            print(f"⚠️ Could not delete old instance {instance_id}: {e}")

        # 6️⃣ Cập nhật extra data
        update_extra(
            new_event_id,
            class_info.get("meeting_id", ""),
            class_info.get("passcode", ""),
            class_info.get("zoom_link", ""),
            class_info.get("classname", ""),
            calendar_id,
        )

        # ==========================================================
        # 7️⃣ Tự động move master mới sang calendar chẵn/lẻ nếu cần
        # ==========================================================
        try:
            new_calendar_id = determine_calendar_by_hour(start_iso)
            if new_calendar_id != calendar_id:
                print(f"🎯 FOLLOWING MODE: Hour changed → moving new master to new calendar")
                moved = calendar_service.events().move(
                    calendarId=calendar_id,
                    eventId=new_event_id,
                    destination=new_calendar_id,
                ).execute()
                print(f"✅ New master moved to new calendar: {new_calendar_id}")
                calendar_id = new_calendar_id
        except Exception as e:
            print(f"⚠️ Could not move new master event to new calendar: {e}")

        print("🎉 FOLLOWING MODE completed successfully!")
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

def delete_following_instances(master_event_id, calendar_id, stop_before_instance_start):
    """
    Xóa thực sự các instances sau instance hiện tại
    """
    try:
        print(f"🗑️ Deleting ALL instances after: {stop_before_instance_start}")
        
        # 1. Lấy tất cả instances của master này
        events_result = calendar_service.events().list(
            calendarId=calendar_id,
            timeMin=stop_before_instance_start,  # Lấy từ instance này trở đi
            maxResults=2500,
            singleEvents=True,  # QUAN TRỌNG: lấy instances
            orderBy='startTime'
        ).execute()
        
        all_events = events_result.get('items', [])
        
        # 2. Lọc chỉ các instances của master này mà SAU thời điểm xóa
        instances_to_delete = []
        for event in all_events:
            if event.get('recurringEventId') == master_event_id:
                event_start = event.get('start', {}).get('dateTime')
                if event_start and event_start > stop_before_instance_start:
                    instances_to_delete.append(event)
        
        print(f"📊 Found {len(instances_to_delete)} instances to delete")
        
        # 3. Xóa từng instance
        for instance in instances_to_delete:
            try:
                print(f"🗑️ Deleting instance: {instance.get('id')} - {instance.get('start', {}).get('dateTime')}")
                calendar_service.events().delete(
                    calendarId=calendar_id,
                    eventId=instance.get('id')
                ).execute()
                
                # Xóa extra data
                remove_extra(instance.get('id'))
                
            except Exception as e:
                print(f"⚠️ Failed to delete instance {instance.get('id')}: {e}")
        
        return len(instances_to_delete)
        
    except Exception as e:
        print(f"❌ Error deleting following instances: {e}")
        return 0

def delete_following_instances_google_native(master_event_id, calendar_id, instance_start):
    """
    Dùng Google Calendar instances API để xóa các instances sau
    """
    try:
        print(f"🗑️ Using Google Calendar instances API")
        
        # 1. Lấy tất cả instances của master
        instances_response = calendar_service.events().instances(
            calendarId=calendar_id,
            eventId=master_event_id,
            timeMin=instance_start,  # Lấy từ instance này trở đi
            showDeleted=False,
            maxResults=2500
        ).execute()
        
        instances = instances_response.get('items', [])
        print(f"📊 Found {len(instances)} instances from Google Calendar API")
        
        # 2. Xóa từng instance (bắt đầu từ instance hiện tại)
        deleted_count = 0
        for instance in instances:
            instance_id = instance.get('id')
            try:
                calendar_service.events().delete(
                    calendarId=calendar_id,
                    eventId=instance_id,
                    sendUpdates='all'
                ).execute()
                
                remove_extra(instance_id)
                deleted_count += 1
                print(f"✅ Deleted instance: {instance_id}")
                
            except Exception as e:
                print(f"⚠️ Failed to delete instance {instance_id}: {e}")
        
        print(f"🎯 Total {deleted_count} instances deleted via Google Calendar API")
        return deleted_count
        
    except Exception as e:
        print(f"❌ Google Calendar instances API error: {e}")
        return 0
# ----------------- DELETE -----------------
def delete_event(event_id, delete_mode="this"):
    """
    Xóa event trong Google Calendar với các mode:
      - this: xóa 1 event
      - following: xóa event hiện tại và tất cả event sau đó
      - all: xóa toàn bộ chuỗi recurring
    Có fallback khi đổi múi giờ hoặc khi Google trả về lỗi 410 (Resource has been deleted).
    """

    try:
        if not event_id or event_id == "undefined":
            raise ValueError("Invalid event ID")

        print(f"🗑️ Deleting event: {event_id}, mode: {delete_mode}")

        deleted_from = "unknown"
        current_event = None
        current_calendar_id = None

        # ==========================================================
        # 🔍 PHÁT HIỆN MASTER / INSTANCE ID AN TOÀN
        # ==========================================================
        is_instance = "_" in event_id
        master_event_id = None

        if is_instance:
            try:
                parts = event_id.split("_")
                if len(parts) >= 2:
                    master_event_id = "_".join(parts[:-1])
                else:
                    master_event_id = event_id.split("_")[0]
                print(f"🔍 Instance detected, master ID: {master_event_id}")
            except Exception:
                master_event_id = event_id.split("_")[0]
        else:
            master_event_id = event_id

        # ==========================================================
        # 🔍 TÌM EVENT THỰC TẾ TRÊN GOOGLE CALENDAR
        # ==========================================================
        for calendar_id in [CALENDARS["odd"], CALENDARS["even"]]:
            try:
                event = calendar_service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
                current_event = event
                current_calendar_id = calendar_id
                break
            except HttpError as e:
                if e.resp.status in [404, 410]:
                    # ✅ Google báo "Resource deleted" → ta tự dựng thông tin từ ID
                    current_calendar_id = calendar_id
                    try:
                        parts = event_id.split("_")
                        time_part = parts[-1].replace("Z", "")
                        target_dt = datetime.strptime(time_part, "%Y%m%dT%H%M%S").astimezone(timezone.utc)
                        print(f"🕐 Reconstructed target_dt from ID: {target_dt}")
                    except Exception:
                        target_dt = None

                    # 🔎 Dò xem còn event nào có recurringEventId hoặc id tương tự
                    try:
                        print(f"🔎 Searching manually for {event_id} in {calendar_id} ...")
                        resp = calendar_service.events().list(
                            calendarId=calendar_id,
                            showDeleted=False,
                            maxResults=2500
                        ).execute()
                        items = resp.get("items", [])
                        for ev in items:
                            rid = ev.get("recurringEventId", "")
                            eid = ev.get("id", "")
                            if master_event_id in rid or master_event_id in eid:
                                current_event = ev
                                print(f"✅ Found similar recurring event: {eid}")
                                break
                        if current_event:
                            break
                    except Exception as scan_err:
                        print(f"⚠️ Manual search failed: {scan_err}")
                    continue
                else:
                    raise

        if not current_calendar_id:
            current_calendar_id = CALENDARS["odd"]

        deleted_from = "EVEN" if current_calendar_id == CALENDARS["even"] else "ODD"

        summary = (current_event or {}).get("summary", "")
        start_str = (current_event or {}).get("start", {}).get("dateTime")
        target_dt = None
        if start_str:
            try:
                target_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                target_dt = None

        # Nếu summary trống nhưng current_event có recurrence → lấy tiêu đề từ ID fallback
        if not summary:
            summary = f"(recurring event {event_id[:10]})"
            print(f"⚙️ Using fallback summary: {summary}")

        # Nếu target_dt vẫn None → thử dựng lại từ event_id
        if "_" in event_id:
            try:
                time_part = event_id.split("_")[-1].replace("Z", "")
                parsed_dt = datetime.strptime(time_part, "%Y%m%dT%H%M%S")
                target_dt = parsed_dt.replace(tzinfo=timezone.utc)
                print(f"🕐 Final reconstructed target_dt: {target_dt}")
            except Exception as parse_err:
                print(f"⚠️ Cannot reconstruct target_dt: {parse_err}")
                if not target_dt:
                    target_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
        else:
            if not target_dt:
                target_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
                print(f"⚙️ Using default target_dt fallback: {target_dt}")

        # ==========================================================
        # MODE: ALL — Xóa toàn bộ chuỗi recurring
        # ==========================================================
        if delete_mode == "all" and master_event_id:
            print(f"🗑️ Delete mode 'all': removing entire series for master {master_event_id}")
            try:
                calendar_service.events().delete(
                    calendarId=current_calendar_id,
                    eventId=master_event_id
                ).execute()
                print(f"✅ Deleted master series from {deleted_from}")
                remove_extra(master_event_id)
                remove_extra(event_id)
                return {"status": "deleted", "delete_mode": "all", "from_calendar": deleted_from}

            except HttpError as e:
                if e.resp.status == 410:
                    print("⚠️ Master already deleted → fallback to instance search")
                    return _fallback_delete_instance(master_event_id, event_id, summary, target_dt, current_calendar_id)
                else:
                    raise

        # ==========================================================
        # MODE: FOLLOWING — Xóa event này và toàn bộ event sau đó
        # ==========================================================
        elif delete_mode == "following" and master_event_id:
            print(f"🗑️ Delete mode 'following': deleting current and following instances")

            try:
                if not target_dt:
                    raise ValueError("Cannot determine instance start time")

                instances_resp = calendar_service.events().instances(
                    calendarId=current_calendar_id,
                    eventId=master_event_id,
                    showDeleted=False,
                    maxResults=2500
                ).execute()
                instances = instances_resp.get("items", [])
                print(f"📊 Found {len(instances)} instances under master {master_event_id}")

                deleted_count = 0
                for inst in instances:
                    inst_start = inst.get("start", {}).get("dateTime")
                    if not inst_start:
                        continue

                    inst_dt = datetime.fromisoformat(inst_start.replace("Z", "+00:00")).astimezone(timezone.utc)
                    if inst_dt >= target_dt:
                        inst_id = inst["id"]
                        calendar_service.events().delete(
                            calendarId=current_calendar_id,
                            eventId=inst_id
                        ).execute()
                        remove_extra(inst_id)
                        deleted_count += 1
                        print(f"✅ Deleted instance {inst_id}")

                print(f"✅ Deleted {deleted_count} instances (following mode)")
                return {
                    "status": "deleted",
                    "delete_mode": "following",
                    "deleted_count": deleted_count,
                    "from_calendar": deleted_from
                }

            except HttpError as e:
                if e.resp.status == 410:
                    print("⚠️ 410 Gone in following mode → fallback to instance search")
                    return _fallback_delete_instance(master_event_id, event_id, summary, target_dt, current_calendar_id)
                else:
                    raise

        # ==========================================================
        # MODE: THIS — Xóa 1 event đơn lẻ
        # ==========================================================
        else:
            try:
                calendar_service.events().delete(
                    calendarId=current_calendar_id,
                    eventId=event_id
                ).execute()
                print(f"✅ Deleted single event from {deleted_from}")
                remove_extra(event_id)
                return {"status": "deleted", "delete_mode": "this", "from_calendar": deleted_from}

            except HttpError as e:
                if e.resp.status == 410:
                    print(f"⚠️ Event {event_id} (410 Gone) → try fallback instance search")
                    return _fallback_delete_instance(master_event_id, event_id, summary, target_dt, current_calendar_id)
                else:
                    raise

    except Exception as e:
        print(f"❌ Error in delete_event: {e}")
        raise


# ==========================================================
# 🔧 Fallback nâng cao (xóa triệt để sau khi timezone đổi)
# ==========================================================
def _fallback_delete_instance(master_id, old_event_id, summary, target_dt, calendar_id):
    """
    Fallback nâng cao (final version):
    - Nếu master_id còn → dò instance theo recurringEventId / id tương tự
    - Nếu không còn → dò theo event_id substring (phần master)
    - Nếu vẫn không thấy → dò tất cả recurringEventId trùng master_id
    """
    try:
        print(f"🔄 Fallback delete triggered | master_id={master_id}, target_dt={target_dt}, summary='{summary}'")

        deleted_count = 0

        # ====== 1️⃣ Nếu có master_id → dò instance mới từ master_id trong toàn bộ calendar ======
        if master_id:
            print(f"🔎 Searching for recurringEventId or id contains '{master_id}' across calendars...")
            for cid in [CALENDARS["odd"], CALENDARS["even"]]:
                try:
                    resp = calendar_service.events().list(
                        calendarId=cid,
                        showDeleted=False,
                        singleEvents=False,
                        maxResults=2500
                    ).execute()
                    items = resp.get("items", [])
                    for ev in items:
                        rid = ev.get("recurringEventId", "")
                        eid = ev.get("id", "")
                        if master_id in rid or master_id in eid:
                            print(f"✅ Found recurring match: {eid}")
                            try:
                                calendar_service.events().delete(
                                    calendarId=cid,
                                    eventId=eid
                                ).execute()
                                remove_extra(eid)
                                deleted_count += 1
                                print(f"🗑️ Deleted {eid}")
                            except Exception as del_err:
                                print(f"⚠️ Could not delete {eid}: {del_err}")
                    if deleted_count > 0:
                        return {
                            "status": "force_deleted",
                            "note": f"Deleted {deleted_count} events matching recurring id",
                            "deleted_count": deleted_count
                        }
                except Exception as e1:
                    print(f"⚠️ Error scanning {cid}: {e1}")

        # ====== 2️⃣ Dò thêm theo event_id substring (phòng khi master_id None) ======
        print(f"🔍 Scanning all events for id fragment: {old_event_id[:10]} ...")
        for cid in [CALENDARS["odd"], CALENDARS["even"]]:
            try:
                resp = calendar_service.events().list(
                    calendarId=cid,
                    showDeleted=False,
                    singleEvents=True,
                    maxResults=2500
                ).execute()
                items = resp.get("items", [])
                for ev in items:
                    eid = ev.get("id", "")
                    if old_event_id[:10] in eid:
                        print(f"✅ Found partial id match: {eid}")
                        calendar_service.events().delete(
                            calendarId=cid,
                            eventId=eid
                        ).execute()
                        remove_extra(eid)
                        deleted_count += 1
                        print(f"🗑️ Deleted event by partial id: {eid}")
                if deleted_count > 0:
                    return {
                        "status": "force_deleted",
                        "note": f"Deleted {deleted_count} events by id fragment",
                        "deleted_count": deleted_count
                    }
            except Exception as e2:
                print(f"⚠️ Error scanning {cid}: {e2}")

        # ====== 3️⃣ Nếu vẫn không thấy → thử lại bằng summary gần đúng ======
        if target_dt:
            print(f"🔎 Last attempt: search by time ±2h and summary substring...")
            for cid in [CALENDARS["odd"], CALENDARS["even"]]:
                try:
                    resp = calendar_service.events().list(
                        calendarId=cid,
                        showDeleted=False,
                        singleEvents=True,
                        maxResults=2500
                    ).execute()
                    events = resp.get("items", [])
                    for ev in events:
                        eid = ev.get("id")
                        ev_sum = ev.get("summary", "")
                        ev_start = ev.get("start", {}).get("dateTime")
                        if not ev_start:
                            continue
                        ev_dt = datetime.fromisoformat(ev_start.replace("Z", "+00:00")).astimezone(timezone.utc)
                        # chỉ cần trùng 1 phần tên và thời gian gần nhau
                        if ev_sum and summary.split()[-1] in ev_sum and abs((ev_dt - target_dt).total_seconds()) <= 7200:
                            print(f"✅ Found near time/name match: {eid}")
                            calendar_service.events().delete(
                                calendarId=cid,
                                eventId=eid
                            ).execute()
                            remove_extra(eid)
                            deleted_count += 1
                            print(f"🗑️ Deleted event {eid}")
                    if deleted_count > 0:
                        return {
                            "status": "force_deleted",
                            "note": f"Deleted {deleted_count} near-matching events",
                            "deleted_count": deleted_count
                        }
                except Exception as e3:
                    print(f"⚠️ Error scanning {cid}: {e3}")

        # ====== Nếu vẫn không tìm thấy ======
        raise ValueError("⚠️ No matching instance found after full calendar scan")

    except Exception as e:
        print(f"❌ Fallback delete error: {e}")
        raise