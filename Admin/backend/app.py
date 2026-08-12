# main.py
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, field_validator
from calendar_crud import (
    IdempotencyConflictError,
    list_events,
    create_event,
    update_event,
    delete_event,
    get_event,
    invalidate_cache,
)
from program_crud import get_all_programs, create_program, update_program, delete_program
from googleapiclient.errors import HttpError
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional, List
from recurrence_helper import build_recurrence_rule
from ai_agent import get_schedule_suggestion
from recurrence_helper import build_recurrence_description
from log_config import make_print

print = make_print(__name__)

app = FastAPI()

# CORS - Allow frontend domain
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Local development
    "http://localhost:8000",  # Local development
    "https://zencity-smartcalendar.pages.dev",  # Cloudflare Pages production
    "*"  # Allow all (for testing, restrict in production)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
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
    week_count: Optional[int] = None     # Số tuần lặp (chỉ cho WEEKLY) - THÊM
    month_count: Optional[int] = None    # Số tháng lặp (chỉ cho MONTHLY) - THÊM
    year_count: Optional[int] = None 
    byday: List[str] = []                # Các ngày trong tuần (WEEKLY)
    bymonthday: List[int] = []           # Các ngày trong tháng (MONTHLY/YEARLY)
    bymonth: List[int] = []              # Các tháng (YEARLY)
    timezone: str = "Asia/Ho_Chi_Minh"
    request_id: Optional[str] = None

    @field_validator('start', 'end')
    @classmethod
    def validate_iso_format(cls, v: str) -> str:
        """Đảm bảo start/end là chuỗi ISO 8601 hợp lệ (chấp nhận 'Z', offset, hoặc naive).

        Chỉ validate định dạng và giữ nguyên chuỗi gốc — việc gắn/chuẩn hóa timezone
        do lớp normalize_datetime_with_timezone xử lý sau.
        """
        if not v or not v.strip():
            raise ValueError("Datetime string must not be empty")
        try:
            # Chấp nhận cả 'Z' (UTC) lẫn offset lẫn naive datetime trên mọi phiên bản Python
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Invalid ISO datetime format: {v}")
        return v


class ConflictCheckRequest(BaseModel):
    teacher: str
    start: str
    end: str
    exclude_event_id: Optional[str] = None

# ---------------- Routes ----------------
@app.get("/classes")
def get_classes(
    calendar_type: str = "both",
    time_min: Optional[str] = None,
    time_max: Optional[str] = None
):
    """
    Lấy classes từ các calendar
    calendar_type: odd, even, both
    """
    try:
        events = list_events(calendar_type, time_min, time_max)
        print(f"📊 Returning {len(events)} events from calendar: {calendar_type}")
        
        # ✅ THÊM DEBUG ĐỂ KIỂM TRA RECURRENCE DATA
        recurring_events = [e for e in events if e.get('recurrence')]
        recurring_instances = [e for e in events if e.get('recurringEventId')]
        
        print(f"🔄 Recurrence Stats: {len(recurring_events)} master events, {len(recurring_instances)} instances")
        
        if recurring_events:
            sample_event = recurring_events[0]
            print(f"🔍 Sample recurring event: {sample_event.get('id')} - {sample_event.get('recurrence')}")
        
        return events
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    except HttpError as e:
        status = getattr(e.resp, 'status', None)
        if status == 404:
            raise HTTPException(status_code=404, detail="Event not found")
        print(f"❌ Google API error in get_single_event: {e}")
        raise HTTPException(status_code=502, detail="Upstream calendar error")
    except Exception as e:
        print(f"❌ Error in get_single_event: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/classes")
def add_class(
    class_info: ClassInfo,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")
):
    try:
        # ⚠️ FIX M10: KHÔNG log toàn bộ payload (chứa passcode/zoom_link) và tránh
        #    encode nặng mỗi request. Chỉ log các field không nhạy cảm.
        print(f"📥 Adding class: {class_info.classname} | program={class_info.program}")

        # 🔍 DEBUG CHI TIẾT RECURRENCE DATA
        print(f"🔍 RECURRENCE DEBUG:")
        print(f"  - recurrence: '{class_info.recurrence}'")
        print(f"  - repeat_count: {class_info.repeat_count}")
        print(f"  - byday: {class_info.byday}")
        print(f"  - bymonthday: {class_info.bymonthday}")
        print(f"  - bymonth: {class_info.bymonth}")
        
        request_key = (idempotency_key or class_info.request_id or "").strip() or None
        if request_key and len(request_key) > 200:
            raise HTTPException(status_code=400, detail="Idempotency key is too long")

        data = class_info.dict(exclude={"request_id"})
        
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
        
        result = create_event(data, idempotency_key=request_key)
        invalidate_cache()  # xóa cache sau khi tạo mới
        return result
    except HTTPException:
        raise
    except IdempotencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Google Calendar timed out: {e}")
    except Exception as e:
        print(f"❌ Error in add_class: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/classes/{event_id}")
def edit_class(event_id: str, class_info: ClassInfo, edit_mode: str = 'this'):
    try:
        if not event_id or event_id == "undefined":
            raise HTTPException(status_code=400, detail="Invalid event ID")
        data = class_info.dict()
        data["edit_mode"] = edit_mode       

        
        recurrence_rule = build_recurrence_rule(data)
        recurrence_description = build_recurrence_description(data)
        
        # CHUYỂN TỪ STRING SANG LIST CHO GOOGLE CALENDAR
        data["rrule"] = [recurrence_rule] if recurrence_rule else None
        data["recurrence_description"] = recurrence_description
        
        result = update_event(event_id, data)
        invalidate_cache()  # xóa cache sau khi cập nhật
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in edit_class: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/classes/{event_id}")
def remove_class(event_id: str, delete_mode: str = 'this'):
    try:
        if not event_id or event_id == "undefined":
            raise HTTPException(status_code=400, detail="Invalid event ID")
        print(f"🗑️ Deleting class ID: {event_id}, mode: {delete_mode}")
        result = delete_event(event_id, delete_mode)
        invalidate_cache()  # xóa cache sau khi xóa
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in remove_class: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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
    """API endpoint kiểm tra xung đột - CHỈ DÙNG TRADITIONAL CHECK"""
    try:
        print(f"🔄 Traditional conflict check for: {request.teacher}")
        
        # Lấy tất cả classes hiện có
        all_classes = list_events('both')
        
        from check_conflict import traditional_conflict_check
        
        result = traditional_conflict_check(
            existing_classes=all_classes,
            teacher=request.teacher,
            new_start=request.start,
            new_end=request.end,
            exclude_event_id=request.exclude_event_id
        )
        
        # THÊM MESSAGE ĐƠN GIẢN
        if result.get('has_conflict'):
            result['message'] = f"⚠️ Giáo viên {request.teacher} có {len(result.get('conflicts', []))} xung đột lịch"
        else:
            result['message'] = f"✅ Không có xung đột với giáo viên {request.teacher}"
        
        return result
        
    except Exception as e:
        print(f"❌ Conflict check error: {e}")
        return {'has_conflict': False, 'error': str(e), 'message': 'Lỗi kiểm tra xung đột'}

@app.get("/timezones")
def get_timezones():
    """API lấy danh sách múi giờ hỗ trợ"""
    return {
        "timezones": [
            {"value": "Asia/Ho_Chi_Minh", "label": "🇻🇳 Giờ Việt Nam (UTC+7)"},
            {"value": "America/Chicago", "label": "🇺🇸 Giờ Miền Trung (UTC-6/-5)"}
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


# ============================================================
# ================= PROGRAM MANAGEMENT API ==================
# ============================================================

class ProgramRequest(BaseModel):
    name: str


@app.get("/programs")
def get_programs():
    """Lấy danh sách tất cả chương trình"""
    try:
        programs = get_all_programs()
        return {
            "success": True,
            "data": programs,
            "count": len(programs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching programs: {str(e)}")


@app.post("/programs")
def create_new_program(request: ProgramRequest):
    """Tạo chương trình mới"""
    try:
        if not request.name or not request.name.strip():
            raise HTTPException(status_code=400, detail="Program name is required")
        
        program = create_program(request.name)
        if program is None:
            raise HTTPException(status_code=400, detail="Program name already exists or invalid")
        
        return {
            "success": True,
            "message": "Program created successfully",
            "data": program
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating program: {str(e)}")


@app.put("/programs/{program_id}")
def update_existing_program(program_id: str, request: ProgramRequest):
    """Cập nhật chương trình"""
    try:
        if not request.name or not request.name.strip():
            raise HTTPException(status_code=400, detail="Program name is required")
        
        program = update_program(program_id, request.name)
        if program is None:
            raise HTTPException(status_code=404, detail="Program not found or name already exists")
        
        return {
            "success": True,
            "message": "Program updated successfully",
            "data": program
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating program: {str(e)}")


@app.delete("/programs/{program_id}")
def delete_existing_program(program_id: str):
    """Xóa chương trình"""
    try:
        success = delete_program(program_id)
        if not success:
            raise HTTPException(status_code=404, detail="Program not found")
        
        return {
            "success": True,
            "message": "Program deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting program: {str(e)}")
