# main.py
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
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
from check_conflict import (
    find_conflicts,
    group_occurrences_into_windows,
    window_bounds,
)
from googleapiclient.errors import HttpError
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional, List
from recurrence_helper import build_recurrence_rule
from ai_agent import get_schedule_suggestion
from recurrence_helper import build_recurrence_description, expand_occurrences
from log_config import make_print
from auth import (
    clear_attempts,
    create_access_token,
    is_rate_limited,
    record_failed_attempt,
    resolve_client_key,
    validate_access_token,
    verify_passcode,
)
import os

print = make_print(__name__)

app = FastAPI(title="ZenCity Smart Calendar API")

# CORS - Allow frontend domain
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Local development
    "http://localhost:3001",  # Local frontend
    "http://localhost:4173",  # Local production preview
    "http://127.0.0.1:4173",  # Local production preview
    "http://localhost:8000",  # Local development
    "https://zencity-smartcalendar.pages.dev",  # Cloudflare Pages production
]
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", ",".join(DEFAULT_ALLOWED_ORIGINS)).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

PUBLIC_PATHS = {"/health", "/auth/login"}

# Trần số xung đột trả về cho client. conflict_count vẫn phản ánh tổng thật.
MAX_REPORTED_CONFLICTS = 50


def calendar_http_error_detail(error):
    """Translate Google Calendar failures into safe, actionable API errors."""
    upstream_status = getattr(error.resp, "status", None)
    if upstream_status in (403, 404):
        return {
            "code": "CALENDAR_NOT_ACCESSIBLE",
            "title": "Không thể kết nối lịch học",
            "message": "Google Calendar chưa cấp quyền truy cập cho hệ thống.",
            "action": (
                "Vui lòng kiểm tra Calendar ID, chia sẻ cả hai lịch cho "
                "tài khoản dịch vụ, sau đó bấm Làm mới."
            ),
        }
    if upstream_status == 429:
        return {
            "code": "CALENDAR_RATE_LIMITED",
            "title": "Google Calendar đang bận",
            "message": "Hệ thống đã tạm thời vượt giới hạn truy cập lịch.",
            "action": "Vui lòng đợi ít phút rồi bấm Làm mới.",
        }
    return {
        "code": "CALENDAR_SERVICE_UNAVAILABLE",
        "title": "Chưa thể tải lịch học",
        "message": "Kết nối với Google Calendar đang tạm thời gián đoạn.",
        "action": "Vui lòng thử lại sau.",
    }


@app.middleware("http")
async def require_admin_session(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not validate_access_token(token):
        return JSONResponse(
            status_code=401,
            content={"detail": "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."},
        )
    return await call_next(request)

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
    # Chỉ truyền khi thao tác lưu thay thế CẢ chuỗi lặp (edit mode 'following'/'all'),
    # để các buổi khác của chính chuỗi đó không bị báo là trùng với nhau.
    exclude_master_event_id: Optional[str] = None
    # Luật lặp — nếu có, TẤT CẢ các buổi trong chuỗi đều được kiểm tra.
    # `str` chứ không phải `Optional[str]`: gửi null là lỗi client (422) chứ không được
    # rơi vào nhánh xử lý mập mờ. ge=1 chặn repeat_count=0 — khi đó build_recurrence_rule
    # bỏ COUNT và sinh ra luật lặp vô hạn.
    recurrence: str = ""
    repeat_count: int = Field(default=1, ge=1)
    byday: List[str] = []
    bymonthday: List[int] = []
    bymonth: List[int] = []
    timezone: str = "Asia/Ho_Chi_Minh"


class LoginRequest(BaseModel):
    passcode: str


@app.post("/auth/login")
def login(request: LoginRequest, http_request: Request):
    # ⚠️ Không tự tách X-Forwarded-For ở đây. resolve_client_key mới biết phần nào của
    #    header là do proxy của mình ghi (đáng tin) và phần nào do client tự khai.
    client_key = resolve_client_key(
        http_request.headers.get("x-forwarded-for", ""),
        http_request.client.host if http_request.client else ""
    )
    if is_rate_limited(client_key):
        raise HTTPException(status_code=429, detail="Bạn đã thử quá nhiều lần. Vui lòng thử lại sau 5 phút.")
    if not verify_passcode(request.passcode):
        record_failed_attempt(client_key)
        raise HTTPException(status_code=401, detail="Passcode không chính xác")
    clear_attempts(client_key)
    token, expires_at = create_access_token()
    return {"access_token": token, "token_type": "bearer", "expires_at": expires_at}


@app.get("/auth/session")
def auth_session():
    return {"authenticated": True}

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
    except HttpError as e:
        # Google intentionally returns 404 both when a calendar does not exist and
        # when the caller cannot access it. Never expose the upstream URL, calendar
        # ID, or raw Google exception to the browser.
        upstream_status = getattr(e.resp, "status", None)
        print(f"❌ Google Calendar error in get_classes (status={upstream_status}): {e}")
        raise HTTPException(status_code=503, detail=calendar_http_error_detail(e))
    except Exception as e:
        print(f"❌ Error in get_classes: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CLASSES_LOAD_FAILED",
                "title": "Chưa thể tải lịch học",
                "message": "Hệ thống gặp lỗi khi tải dữ liệu lịch.",
                "action": "Vui lòng thử lại hoặc liên hệ quản trị viên.",
            },
        )

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
        print(f"📦 Recurrence rule prepared: {bool(data.get('rrule'))}")

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
    except HttpError as e:
        print(f"❌ Google Calendar error in add_class: {e}")
        raise HTTPException(status_code=503, detail=calendar_http_error_detail(e))
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
    """API endpoint kiểm tra xung đột - CHỈ DÙNG TRADITIONAL CHECK.

    ⚠️ FAIL-CLOSED: khi không kiểm tra được PHẢI trả HTTP lỗi.
    Trước đây endpoint nuốt exception và trả 200 kèm has_conflict=False, nên client
    không phân biệt được "đã kiểm tra, không trùng" với "chưa kiểm tra được" và vẫn
    cho tạo sự kiện trùng.
    """
    try:
        print(f"🔄 Traditional conflict check for: {request.teacher}")

        # 1️⃣ Bung luật lặp thành từng buổi cụ thể. Sự kiện đơn → đúng 1 buổi.
        occurrences, truncated = expand_occurrences(request.start, request.end, request.model_dump())

        # 2️⃣ Chuỗi lặp dài có thể vượt trần cửa sổ của list_events → nạp theo từng cụm,
        #    nếu không các buổi cuối chuỗi sẽ không có dữ liệu đối chiếu.
        conflicts = []
        checked_occurrences = 0
        for window in group_occurrences_into_windows(occurrences):
            window_start, window_end = window_bounds(window)
            existing_classes = list_events(
                'both',
                time_min=window_start.isoformat().replace('+00:00', 'Z'),
                time_max=window_end.isoformat().replace('+00:00', 'Z')
            )
            window_result = find_conflicts(
                existing_classes=existing_classes,
                teacher=request.teacher,
                occurrences=window,
                exclude_event_id=request.exclude_event_id,
                exclude_master_event_id=request.exclude_master_event_id
            )
            conflicts.extend(window_result['conflicts'])
            checked_occurrences += window_result['checked_occurrences']

        result = {
            'has_conflict': len(conflicts) > 0,
            # Giới hạn kích thước payload; conflict_count vẫn là tổng thật.
            'conflicts': conflicts[:MAX_REPORTED_CONFLICTS],
            'conflict_count': len(conflicts),
            'checked_occurrences': checked_occurrences,
            'occurrences_truncated': truncated,
        }

        if result['has_conflict']:
            result['message'] = (
                f"⚠️ Giáo viên {request.teacher} bị trùng {len(conflicts)} lượt "
                f"trên {checked_occurrences} buổi đã kiểm tra"
            )
        else:
            result['message'] = (
                f"✅ Không có xung đột với giáo viên {request.teacher} "
                f"({checked_occurrences} buổi đã kiểm tra)"
            )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HttpError as e:
        print(f"❌ Google Calendar error in conflict check: {e}")
        raise HTTPException(status_code=503, detail=calendar_http_error_detail(e))
    except Exception as e:
        print(f"❌ Conflict check error: {e}")
        raise HTTPException(
            status_code=502,
            detail={
                "code": "CONFLICT_CHECK_FAILED",
                "title": "Không thể kiểm tra trùng lịch",
                "message": "Hệ thống chưa thể kiểm tra lịch hiện có.",
                "action": "Sự kiện chưa được lưu. Vui lòng thử lại.",
            },
        )

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
