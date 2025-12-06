# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from calendar_crud import list_events, create_event, update_event, delete_event, get_event
from fastapi.middleware.cors import CORSMiddleware
from ai_agent import get_schedule_suggestion
from datetime import datetime
from typing import Optional, List
from recurrence_helper import build_recurrence_rule
from ai_agent import get_schedule_suggestion, ai_check_schedule_conflict
import pytz
from recurrence_helper import build_recurrence_description

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ---------------- Pydantic Model ----------------
class ClassInfo(BaseModel):
    name: str
    classname: Optional[str] = ""
    teacher: str
    zoom_link: str
    program: str
    start: str  # ISO string
    end: str
    meeting_id: str = ""
    passcode: str = ""
    recurrence: Optional[str] = ""       # Loại lặp: DAILY, WEEKLY, MONTHLY, YEARLY
    repeat_count: int = 1                # Số lần lặp
    byday: List[str] = []                # Các ngày trong tuần (WEEKLY)
    bymonthday: List[int] = []           # Các ngày trong tháng (MONTHLY/YEARLY)
    bymonth: List[int] = []              # Các tháng (YEARLY)
    timezone: str = "Asia/Ho_Chi_Minh"

# ✅ THÊM VALIDATOR MỚI
@validator('start', 'end')
def validate_iso_format(cls, v, values):
    try:
        from datetime import datetime
        import pytz
        
        # Lấy timezone từ request, không ép thành Vietnam
        timezone_str = values.get('timezone', 'Asia/Ho_Chi_Minh')
        
        # CHỈ validate format, KHÔNG thêm timezone vào string
        if not v.endswith('Z') and '+' not in v and '-' not in v.split('T')[1]:
            # Chỉ kiểm tra định dạng ISO, không thêm timezone
            datetime.fromisoformat(v)
            print(f"✅ Valid ISO format (no timezone), will use timeZone field: {timezone_str}")
        
        return v  # Giữ nguyên string không có timezone
    except ValueError:
        raise ValueError(f"Invalid ISO datetime format: {v}")
        
class ConflictCheckRequest(BaseModel):
    teacher: str
    start: str
    end: str
    exclude_event_id: Optional[str] = None

# ---------------- Routes ----------------
@app.get("/classes")
def get_classes(calendar_type: str = "both"):
    """
    Lấy classes từ các calendar
    calendar_type: odd, even, both
    """
    try:
        events = list_events(calendar_type)
        print(f"📊 Returning {len(events)} events from calendar: {calendar_type}")
        
        # ✅ THÊM DEBUG ĐỂ KIỂM TRA RECURRENCE DATA
        recurring_events = [e for e in events if e.get('recurrence')]
        recurring_instances = [e for e in events if e.get('recurringEventId')]
        
        print(f"🔄 Recurrence Stats: {len(recurring_events)} master events, {len(recurring_instances)} instances")
        
        if recurring_events:
            sample_event = recurring_events[0]
            print(f"🔍 Sample recurring event: {sample_event.get('id')} - {sample_event.get('recurrence')}")
        
        return events
    except Exception as e:
        print(f"❌ Error in get_classes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ THÊM ENDPOINT MỚI: Lấy single event bằng ID
@app.get("/classes/{event_id}")
def get_single_event(event_id: str):
    try:
        if not event_id or event_id == "undefined":
            raise HTTPException(status_code=400, detail="Invalid event ID")
            
        print(f"🔍 Fetching single event: {event_id}")
        event = get_event(event_id)
        
        if event:
            print(f"✅ Found event: {event.get('summary')}")
            print(f"🔄 Event recurrence: {event.get('recurrence')}")
            return event
        else:
            raise HTTPException(status_code=404, detail="Event not found")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_single_event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/classes")
def add_class(class_info: ClassInfo):
    try:
        # 🔍 DEBUG REQUEST BODY RAW
        import json
        from fastapi.encoders import jsonable_encoder
        
        print(f"🎯 RAW REQUEST BODY: {jsonable_encoder(class_info)}")
        
        print(f"📥 Adding class: {class_info.classname}")
        print(f"📥 RAW class_info: {class_info}")
        
        # 🔍 DEBUG CHI TIẾT RECURRENCE DATA
        print(f"🔍 RECURRENCE DEBUG:")
        print(f"  - recurrence: '{class_info.recurrence}'")
        print(f"  - repeat_count: {class_info.repeat_count}")
        print(f"  - byday: {class_info.byday}")
        print(f"  - bymonthday: {class_info.bymonthday}")
        print(f"  - bymonth: {class_info.bymonth}")
        
        data = class_info.dict()
        
        # 🔍 DEBUG TRƯỚC KHI GỌI build_recurrence_rule
        print(f"🔄 Before build_recurrence_rule:")
        print(f"  - data['recurrence']: '{data.get('recurrence')}'")
        print(f"  - data['repeat_count']: {data.get('repeat_count')}")
        
        # 🔍 DEBUG TIMEZONE TRƯỚC KHI TẠO RECURRENCE
        print(f"🕐 DEBUG TIMEZONE IN add_class:")
        print(f"  - class_info.timezone: '{class_info.timezone}'")
        print(f"  - data['timezone']: '{data.get('timezone')}'")
        
        # Gọi hàm build recurrence
        recurrence_rule = build_recurrence_rule(data)
        
        print(f"📆 Result from build_recurrence_rule: {recurrence_rule}")
        
        # CHUYỂN TỪ STRING SANG LIST CHO GOOGLE CALENDAR
        data["rrule"] = [recurrence_rule] if recurrence_rule else None
        print(f"📦 Final data with rrule: {data}")

        # Gọi hàm build recurrence description
        recurrence_description = build_recurrence_description(data)
        
        if recurrence_rule:
            data["rrule"] = [recurrence_rule]
            data["recurrence_description"] = recurrence_description
            print(f"📦 Final data with rrule: {data['rrule']}")
            print(f"📝 Recurrence description: {data['recurrence_description']}")
        
        return create_event(data)
    except Exception as e:
        print(f"❌ Error in add_class: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/classes/{event_id}")
def edit_class(event_id: str, class_info: ClassInfo):
    try:
        if not event_id or event_id == "undefined":
            raise HTTPException(status_code=400, detail="Invalid event ID")
        print(f"📝 Editing class ID: {event_id}")
        data = class_info.dict()
        
        # 🔍 DEBUG TIMEZONE
        print(f"🕐 DEBUG TIMEZONE IN edit_class:")
        print(f"  - class_info.timezone: '{class_info.timezone}'")
        print(f"  - data['timezone']: '{data.get('timezone')}'")
        print(f"  - class_info.dict()['timezone']: '{class_info.dict().get('timezone')}'")
        
        # DÙNG HÀM MỚI - THÊM DEBUG
        print("🔄 Building recurrence rule for update...")
        print(f"🕐 DEBUG BEFORE build_recurrence_description:")
        print(f"  - data['timezone']: '{data.get('timezone')}'")
        print(f"  - data keys: {list(data.keys())}")
        
        recurrence_rule = build_recurrence_rule(data)
        recurrence_description = build_recurrence_description(data)
        print(f"📆 Final RRULE for Google: {recurrence_rule}")
        print(f"📝 Final recurrence description: {recurrence_description}")
        
        # CHUYỂN TỪ STRING SANG LIST CHO GOOGLE CALENDAR
        data["rrule"] = [recurrence_rule] if recurrence_rule else None
        data["recurrence_description"] = recurrence_description
        
        return update_event(event_id, data)
    except Exception as e:
        print(f"❌ Error in edit_class: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/classes/{event_id}")
def remove_class(event_id: str):
    try:
        if not event_id or event_id == "undefined":
            raise HTTPException(status_code=400, detail="Invalid event ID")
        print(f"🗑️ Deleting class ID: {event_id}")
        return delete_event(event_id)
    except Exception as e:
        print(f"❌ Error in remove_class: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ai/suggest")
def ai_suggest(teacher: str = None, duration_hours: int = 1):
    try:
        classes = list_events('both')  # Lấy từ cả 2 calendars
        return get_schedule_suggestion(classes, teacher, duration_hours)
    except Exception as e:
        print(f"❌ Error in ai_suggest: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/check-conflict")
def api_check_conflict(request: ConflictCheckRequest):
    """API endpoint kiểm tra xung đột - DÙNG AI CHỈ KHI CẦN"""
    try:
        print(f"🔄 Smart conflict check for: {request.teacher}")
        
        # Lấy tất cả classes hiện có từ cả 2 calendars
        all_classes = list_events('both')
        
        # 1. TRADITIONAL CHECK NHANH TRƯỚC
        from ai_agent import traditional_conflict_check
        traditional_result = traditional_conflict_check(
            existing_classes=all_classes,
            teacher=request.teacher,
            new_start=request.start,
            new_end=request.end,
            exclude_event_id=request.exclude_event_id
        )
        
        # 2. CHỈ GỌI AI KHI CÓ CONFLICT (để có suggestions)
        if traditional_result.get('has_conflict') and traditional_result.get('conflicts'):
            print(f"🤖 Conflict detected - calling AI for smart suggestions...")
            
            from ai_agent import ai_check_schedule_conflict
            ai_result = ai_check_schedule_conflict(
                existing_classes=all_classes,
                teacher=request.teacher,
                new_start=request.start,
                new_end=request.end,
                exclude_event_id=request.exclude_event_id
            )
            
            # Kết hợp kết quả: conflicts từ traditional + suggestions từ AI
            result = {
                'has_conflict': True,
                'conflicts': traditional_result['conflicts'],
                'suggestions': ai_result.get('suggestions', []),
                'ai_analysis': ai_result.get('ai_analysis', 'AI đề xuất thời gian thay thế'),
                'check_type': 'ai_suggestions'
            }
            
        else:
            # KHÔNG CÓ CONFLICT - chỉ dùng traditional (siêu nhanh)
            print(f"✅ No conflict - traditional check only")
            traditional_result['check_type'] = 'traditional_fast'
            result = traditional_result
        
        print(f"✅ Smart check result: {result.get('has_conflict')} | Type: {result.get('check_type')}")
        return result
        
    except Exception as e:
        print(f"❌ Smart conflict check error: {e}")
        # Fallback về traditional
        from ai_agent import traditional_conflict_check
        return traditional_conflict_check(
            list_events('both'),
            request.teacher, 
            request.start, 
            request.end
        )

@app.get("/timezones")
def get_timezones():
    """API lấy danh sách múi giờ hỗ trợ"""
    return {
        "timezones": [
            {"value": "Asia/Ho_Chi_Minh", "label": "🇻🇳 Giờ Việt Nam (UTC+7)"},
            {"value": "Asia/Bangkok", "label": "🇹🇭 Giờ Thái Lan (UTC+7)"},
            {"value": "Asia/Singapore", "label": "🇸🇬 Giờ Singapore (UTC+8)"},
            {"value": "Asia/Tokyo", "label": "🇯🇵 Giờ Nhật Bản (UTC+9)"},
            {"value": "Asia/Seoul", "label": "🇰🇷 Giờ Hàn Quốc (UTC+9)"},
            {"value": "Asia/Shanghai", "label": "🇨🇳 Giờ Trung Quốc (UTC+8)"},
            {"value": "America/New_York", "label": "🇺🇸 Giờ Miền Đông (UTC-5/-4)"},
            {"value": "America/Chicago", "label": "🇺🇸 Giờ Miền Trung (UTC-6/-5)"},
            {"value": "America/Denver", "label": "🇺🇸 Giờ Miền Núi (UTC-7/-6)"},
            {"value": "America/Los_Angeles", "label": "🇺🇸 Giờ Miền Tây (UTC-8/-7)"},
            {"value": "Europe/London", "label": "🇬🇧 Giờ London (UTC+0/+1)"},
            {"value": "Europe/Paris", "label": "🇫🇷 Giờ Paris (UTC+1/+2)"},
            {"value": "Europe/Berlin", "label": "🇩🇪 Giờ Berlin (UTC+1/+2)"},
            {"value": "Australia/Sydney", "label": "🇦🇺 Giờ Sydney (UTC+10/+11)"},
            {"value": "Pacific/Auckland", "label": "🇳🇿 Giờ New Zealand (UTC+12/+13)"},
            {"value": "UTC", "label": "🌐 Giờ UTC"}
        ]
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "ZenAI Tutor Admin API",
        "calendars": {
            "odd": "configured",
            "even": "configured"
        }
    }