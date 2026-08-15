from google_calendar import calendar_service, CALENDARS, create_calendar_http
from googleapiclient.errors import HttpError
import json
import hashlib
import socket
import ssl
import uuid
from pathlib import Path
from recurrence_helper import build_recurrence_rule
from datetime import datetime, timedelta, timezone
import pytz
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from log_config import make_print

print = make_print(__name__)

EXTRA_FILE = Path("data/classes_extra.json")

# ========== IN-MEMORY CACHE ==========
_events_cache = {}
_calendar_sync_state = {}
_cache_lock = threading.RLock()
_refresh_lock = threading.Lock()
CACHE_TTL = 60  # seconds — đủ để tránh duplicate requests, không quá stale
MAX_SYNC_STATE_KEYS = 32  # FIX M5: chặn _calendar_sync_state phình vô hạn theo ngày

EVENT_LIST_FIELDS = (
    "nextPageToken,nextSyncToken,"
    "items(id,status,summary,description,location,start,end,recurrence,"
    "recurringEventId,originalStartTime)"
)

GOOGLE_WRITE_TIMEOUT = 30
GOOGLE_WRITE_ATTEMPTS = 2
GOOGLE_BATCH_SIZE = 100


def _wr_http():
    """
    FIX H1: Trả về một transport (httplib2.Http) riêng cho MỖI lời gọi API.

    `calendar_service` dùng chung một httplib2.Http mặc định — KHÔNG thread-safe.
    FastAPI chạy các handler `def` trong threadpool nên nhiều request ghi/đọc
    chạy song song trên các thread khác nhau; nếu cùng dùng transport mặc định
    chúng có thể interleave trên cùng socket → response hỏng/treo/lỗi auth.
    Mỗi `.execute()` ở đường ghi/get phải truyền `http=_wr_http()` để có transport
    độc lập (đường đọc `list_events` đã làm điều này qua `create_calendar_http`).
    """
    return create_calendar_http(timeout=GOOGLE_WRITE_TIMEOUT)


class IdempotencyConflictError(Exception):
    """The same idempotency key was reused with a different create payload."""


def _event_payload_hash(event):
    payload = json.dumps(event, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _get_event_for_idempotency(calendar_id, event_id):
    """Return an existing event by deterministic ID, or None when it is absent."""
    try:
        return calendar_service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute(
            http=create_calendar_http(timeout=GOOGLE_WRITE_TIMEOUT),
            num_retries=1
        )
    except HttpError as error:
        if getattr(error.resp, 'status', None) == 404:
            return None
        raise


def _validate_idempotent_event(existing_event, payload_hash):
    private = existing_event.get('extendedProperties', {}).get('private', {})
    existing_hash = private.get('zencityPayloadHash')
    if existing_hash != payload_hash:
        raise IdempotencyConflictError(
            "The idempotency key has already been used with different event data"
        )
    return existing_event


def _insert_event_idempotently(calendar_id, event, idempotency_key=None):
    """Insert once even when clients retry or the Google response is lost."""
    request_key = idempotency_key or uuid.uuid4().hex
    event_id = hashlib.sha256(request_key.encode('utf-8')).hexdigest()[:32]
    payload_hash = _event_payload_hash(event)
    event = dict(event)
    event['id'] = event_id
    event['extendedProperties'] = {
        **event.get('extendedProperties', {}),
        'private': {
            **event.get('extendedProperties', {}).get('private', {}),
            'zencityPayloadHash': payload_hash
        }
    }

    last_error = None
    for attempt in range(1, GOOGLE_WRITE_ATTEMPTS + 1):
        try:
            return calendar_service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute(
                http=create_calendar_http(timeout=GOOGLE_WRITE_TIMEOUT),
                num_retries=1
            )
        except HttpError as error:
            status = getattr(error.resp, 'status', None)
            if status == 409:
                existing = _get_event_for_idempotency(calendar_id, event_id)
                if existing:
                    print(f"♻️ Reusing event for idempotency key: {event_id}")
                    return _validate_idempotent_event(existing, payload_hash)
            last_error = error
            if status not in (429, 500, 502, 503, 504) or attempt == GOOGLE_WRITE_ATTEMPTS:
                raise
        except (TimeoutError, socket.timeout, ssl.SSLError, ConnectionError) as error:
            last_error = error
            try:
                existing = _get_event_for_idempotency(calendar_id, event_id)
                if existing:
                    print(f"✅ Event existed after a lost/timeout response: {event_id}")
                    return _validate_idempotent_event(existing, payload_hash)
            except (TimeoutError, socket.timeout, ssl.SSLError, ConnectionError, HttpError) as verify_error:
                print(f"⚠️ Could not verify timed-out insert: {verify_error}")
            if attempt == GOOGLE_WRITE_ATTEMPTS:
                raise

        time.sleep(0.25 * attempt)

    raise last_error

def _get_cache(key):
    with _cache_lock:
        entry = _events_cache.get(key)
        if entry and time.time() - entry['ts'] < CACHE_TTL:
            return entry['data']
    return None

def _set_cache(key, data):
    with _cache_lock:
        _events_cache[key] = {'data': data, 'ts': time.time()}

def invalidate_cache():
    """Gọi khi có thay đổi (create/update/delete) để cache không stale.

    Chỉ xóa kết quả đã cache (_events_cache). GIỮ LẠI _calendar_sync_state để lần
    load kế tiếp dùng incremental sync (chỉ tải phần thay đổi nhờ syncToken +
    showDeleted=True) thay vì full sync toàn bộ cửa sổ thời gian → nhanh hơn nhiều.
    """
    with _cache_lock:
        _events_cache.clear()


def _prune_sync_state_locked():
    """FIX M5: giới hạn số state của incremental sync.

    _calendar_sync_state key theo (calendar_id, time_min, time_max); cửa sổ thời gian
    mặc định neo theo 'hôm nay' nên mỗi ngày sinh key mới, các key cũ không bao giờ
    được truy cập lại → phình bộ nhớ. Chỉ giữ lại MAX_SYNC_STATE_KEYS state mới nhất.
    Phải gọi khi ĐANG giữ _cache_lock. Loại state cũ chỉ khiến lần load kế của cửa sổ
    đó chạy full sync (kết quả không đổi) → KHÔNG thay đổi hành vi.
    """
    if len(_calendar_sync_state) <= MAX_SYNC_STATE_KEYS:
        return
    ordered = sorted(
        _calendar_sync_state.items(),
        key=lambda kv: kv[1].get('ts', 0),
        reverse=True
    )
    for key, _ in ordered[MAX_SYNC_STATE_KEYS:]:
        _calendar_sync_state.pop(key, None)

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
# FIX M7: serialize read-modify-write để nhiều request (threadpool) không ghi đè/hỏng file.
_extra_file_lock = threading.Lock()

def load_extra():
    if EXTRA_FILE.exists():
        try:
            with open(EXTRA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # File hỏng/không đọc được → trả rỗng thay vì làm sập cả endpoint
            print(f"⚠️ Could not read {EXTRA_FILE}, using empty: {e}")
            return {}
    return {}

def save_extra(data):
    # FIX M7: ghi atomic (temp file + replace) để không hỏng file khi ghi dở
    EXTRA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = EXTRA_FILE.with_name(EXTRA_FILE.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(EXTRA_FILE)

def add_extra(event_id, meeting_id, passcode, zoom_link="", classname="", calendar_id=""):
    with _extra_file_lock:
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
    with _extra_file_lock:
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
    remove_extras([event_id])


def remove_extras(event_ids):
    """Remove multiple metadata entries with one atomic file rewrite."""
    event_ids = {event_id for event_id in event_ids if event_id}
    if not event_ids:
        return
    with _extra_file_lock:
        extra = load_extra()
        changed = False
        for event_id in event_ids:
            if event_id in extra:
                del extra[event_id]
                changed = True
        if changed:
            save_extra(extra)


def _delete_events_in_batches(calendar_id, event_ids):
    """Delete concrete event IDs using Google batch requests.

    Batch callbacks report per-item failures instead of raising them from
    ``execute``. Ignore already-gone items and retry other failures once as
    ordinary requests so callers retain the previous all-or-error behavior.
    """
    event_ids = list(dict.fromkeys(event_id for event_id in event_ids if event_id))
    deleted_ids = []
    retry_ids = []

    for offset in range(0, len(event_ids), GOOGLE_BATCH_SIZE):
        chunk = event_ids[offset:offset + GOOGLE_BATCH_SIZE]
        request_ids = {str(index): event_id for index, event_id in enumerate(chunk)}

        def callback(request_id, _response, exception):
            event_id = request_ids[request_id]
            status = getattr(getattr(exception, 'resp', None), 'status', None)
            if exception is None or status in (404, 410):
                deleted_ids.append(event_id)
            else:
                retry_ids.append(event_id)

        batch = calendar_service.new_batch_http_request()
        for request_id, event_id in request_ids.items():
            batch.add(
                calendar_service.events().delete(
                    calendarId=calendar_id,
                    eventId=event_id
                ),
                request_id=request_id,
                callback=callback
            )
        try:
            batch.execute(http=_wr_http())
        except Exception as batch_error:
            # A transport-level batch failure may happen before callbacks run.
            # Fall back to the proven single-delete path for every unresolved ID.
            print(f"⚠️ Batch delete failed; retrying items individually: {batch_error}")
            resolved = set(deleted_ids) | set(retry_ids)
            retry_ids.extend(event_id for event_id in chunk if event_id not in resolved)

    for event_id in dict.fromkeys(retry_ids):
        try:
            calendar_service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute(http=_wr_http())
            deleted_ids.append(event_id)
        except HttpError as error:
            if getattr(error.resp, 'status', None) in (404, 410):
                deleted_ids.append(event_id)
            else:
                raise

    remove_extras(deleted_ids)
    return len(deleted_ids)

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

def _master_id_from_instance(event_id):
    """Suy ra id master từ id instance dạng 'MASTER_YYYYMMDDTHHMMSSZ'.

    Trả về None nếu event_id không phải instance (không chứa '_').
    """
    if not event_id or '_' not in event_id:
        return None
    parts = event_id.split('_')
    return '_'.join(parts[:-1]) or parts[0]


def _resolve_calendar_order(event_id):
    """Thứ tự calendar nên thử khi định vị 1 event.

    Ưu tiên calendar_id đã lưu trong classes_extra.json (nếu có) để tránh phải
    dò cả 2 calendar bằng 2 round-trip. Luôn giữ đủ 2 calendar làm fallback nên
    không ảnh hưởng tính đúng đắn — chỉ giảm số lần gọi API ở trường hợp phổ biến.

    FIX (mục 3): instance của chuỗi lặp (id dạng 'MASTER_YYYYMMDDTHHMMSSZ') KHÔNG
    được lưu calendar_id riêng, nhưng luôn nằm CÙNG calendar với master. Nếu không
    tìm thấy calendar_id cho chính event_id, thử dùng calendar_id của master làm gợi ý
    → thao tác trên instance (sửa/xóa 'this'/'following') thường chỉ cần đoán 1 lần.
    """
    default_order = [CALENDARS['odd'], CALENDARS['even']]
    saved = _saved_calendar_hint(event_id)
    if saved:
        return [saved] + [calendar_id for calendar_id in default_order if calendar_id != saved]
    return default_order


def _saved_calendar_hint(event_id):
    """Return the persisted calendar for an event or its recurring master."""
    valid_calendars = (CALENDARS['odd'], CALENDARS['even'])
    if not event_id:
        return None
    try:
        extra = load_extra()
    except Exception:
        return None

    saved = extra.get(event_id, {}).get('calendar_id')
    if saved not in valid_calendars:
        master_id = _master_id_from_instance(event_id)
        saved = extra.get(master_id, {}).get('calendar_id') if master_id else None
    return saved if saved in valid_calendars else None


def _probe_event_on_calendars(event_id, calendar_order=None):
    """Locate an event while avoiding a redundant Google request when possible.

    When ``classes_extra.json`` identifies the calendar, query that calendar
    first and only use the other one after a 404/410. Without a reliable hint,
    retain the parallel lookup so an event on EVEN does not pay two sequential
    network round-trips.

    Trả về (order, results) với:
      - order: danh sách calendar_id theo đúng thứ tự ưu tiên (giữ nguyên như cũ)
      - results: dict {calendar_id: event_dict | Exception} — mỗi transport độc lập
                 (_wr_http) nên an toàn khi chạy đa luồng.
    """
    hint = None if calendar_order else _saved_calendar_hint(event_id)
    if calendar_order:
        order = list(calendar_order)
    else:
        default_order = [CALENDARS['odd'], CALENDARS['even']]
        order = (
            [hint] + [calendar_id for calendar_id in default_order if calendar_id != hint]
            if hint else default_order
        )

    def _get(calendar_id):
        return calendar_service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute(http=_wr_http())

    results = {}
    if hint in order:
        try:
            results[hint] = _get(hint)
            return order, results
        except HttpError as error:
            results[hint] = error
            if getattr(error.resp, 'status', None) not in (404, 410):
                return order, results
        except Exception as error:
            results[hint] = error
            return order, results

        fallback_order = [calendar_id for calendar_id in order if calendar_id != hint]
        for calendar_id in fallback_order:
            try:
                results[calendar_id] = _get(calendar_id)
            except Exception as error:
                results[calendar_id] = error
        return order, results

    with ThreadPoolExecutor(max_workers=len(order)) as executor:
        futures = {executor.submit(_get, calendar_id): calendar_id for calendar_id in order}
        for future in as_completed(futures):
            calendar_id = futures[future]
            try:
                results[calendar_id] = future.result()
            except Exception as e:  # giữ nguyên exception để caller phân loại 404/410/khác
                results[calendar_id] = e
    return order, results


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
        
        # 1. TÁCH KHỎI CALENDAR CŨ
        #    ⚠️ FIX C2: TUYỆT ĐỐI không xóa master của chuỗi lặp (sẽ mất toàn bộ chuỗi).
        #    - Master           → loại occurrence đang chuyển bằng EXDATE, giữ nguyên
        #                         chuỗi ở calendar cũ.
        #    - Instance / single → xóa an toàn (chỉ hủy occurrence đó / xóa event đơn).
        try:
            if is_master_event:
                from recurrence_utils import add_exdate_to_master
                occurrence_start = (current_event.get('start') or {}).get('dateTime')
                updated_recurrence = (
                    add_exdate_to_master(current_event, occurrence_start)
                    if occurrence_start else None
                )
                if updated_recurrence:
                    master_body = dict(current_event)
                    master_body['recurrence'] = updated_recurrence
                    calendar_service.events().update(
                        calendarId=old_calendar_id,
                        eventId=event_id,
                        body=master_body
                    ).execute(http=_wr_http())
                    print(f"✅ Master giữ nguyên; đã EXDATE occurrence {occurrence_start}")
                else:
                    print("⚠️ Không dựng được EXDATE cho master → bỏ qua xóa để không phá chuỗi")
            else:
                calendar_service.events().delete(
                    calendarId=old_calendar_id,
                    eventId=event_id
                ).execute(http=_wr_http())
                print(f"✅ Deleted from old calendar")
                # Xóa extra data cũ
                remove_extra(event_id)

        except Exception as delete_error:
            print(f"⚠️ Detach/delete error (might be already moved): {delete_error}")
        
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
        ).execute(http=_wr_http())
        
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
def _normalize_event_window(time_min=None, time_max=None):
    """Return a bounded RFC3339 window used by Google and cache keys."""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def parse(value, fallback):
        if value is None:
            return fallback
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace('Z', '+00:00')
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    start = parse(time_min, today - timedelta(days=1))
    end = parse(time_max, today + timedelta(days=61))
    if end <= start:
        raise ValueError("time_max must be later than time_min")
    if end - start > timedelta(days=120):
        raise ValueError("The requested calendar window cannot exceed 120 days")

    return (
        start.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        end.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    )


def _execute_event_pages(calendar_id, http, request_params):
    """Fetch all result pages and preserve the final incremental sync token."""
    items = []
    page_token = None
    next_sync_token = None
    while True:
        params = dict(request_params)
        if page_token:
            params['pageToken'] = page_token
        response = calendar_service.events().list(
            calendarId=calendar_id,
            **params
        ).execute(http=http)
        items.extend(response.get('items', []))
        page_token = response.get('nextPageToken')
        next_sync_token = response.get('nextSyncToken') or next_sync_token
        if not page_token:
            return items, next_sync_token


def _decorate_events(events, calendar_id, calendar_type_name, extra):
    """Attach application metadata without mutating the cached Google objects."""
    results = []
    for raw_event in events:
        if raw_event.get('status') == 'cancelled':
            continue
        event = dict(raw_event)
        recurring_event_id = event.get('recurringEventId')
        if event.get('recurrence') and not recurring_event_id:
            continue
        event['_calendar_source'] = calendar_type_name
        event['_calendar_id'] = calendar_id
        event['_is_instance'] = bool(recurring_event_id)
        event['_is_master'] = False
        if recurring_event_id:
            event['_master_event_id'] = recurring_event_id
        event_id = event.get('id')
        if event_id in extra:
            event.update({
                'zoom_link': extra[event_id].get('zoom_link', ''),
                'meeting_id': extra[event_id].get('meeting_id', ''),
                'passcode': extra[event_id].get('passcode', ''),
                'classname': extra[event_id].get('classname', '')
            })
        results.append(event)
    return results


def _fetch_single_calendar(calendar_id, time_min, time_max, extra):
    """Fetch one calendar with incremental sync and a thread-local transport."""
    calendar_type_name = get_calendar_type_by_id(calendar_id)
    state_key = (calendar_id, time_min, time_max)
    http = create_calendar_http()
    with _cache_lock:
        state = _calendar_sync_state.get(state_key)

    event_map = None
    sync_token = None
    if state and state.get('sync_token'):
        try:
            changes, sync_token = _execute_event_pages(calendar_id, http, {
                'syncToken': state['sync_token'],
                'maxResults': 500,
                'singleEvents': True,
                'showDeleted': True,
                'fields': EVENT_LIST_FIELDS
            })
            event_map = dict(state['events'])
            for event in changes:
                event_id = event.get('id')
                if not event_id:
                    continue
                if event.get('status') == 'cancelled':
                    event_map.pop(event_id, None)
                else:
                    event_map[event_id] = event
            print(f"  ⚡ {calendar_type_name}: {len(changes)} incremental changes")
        except HttpError as error:
            if getattr(error.resp, 'status', None) != 410:
                print(f"⚠️ Incremental sync failed for {calendar_type_name}; serving stale cache: {error}")
                return _decorate_events(state['events'].values(), calendar_id, calendar_type_name, extra)
            print(f"🔄 Sync token expired for {calendar_type_name}; rebuilding window")

    if event_map is None:
        try:
            events, sync_token = _execute_event_pages(calendar_id, http, {
                'timeMin': time_min,
                'timeMax': time_max,
                'maxResults': 500,
                'singleEvents': True,
                'showDeleted': True,
                'fields': EVENT_LIST_FIELDS
            })
        except Exception:
            if state:
                return _decorate_events(state['events'].values(), calendar_id, calendar_type_name, extra)
            raise
        event_map = {
            event['id']: event for event in events
            if event.get('id') and event.get('status') != 'cancelled'
        }
        print(f"  📅 {calendar_type_name}: {len(event_map)} events (full sync)")

    with _cache_lock:
        _calendar_sync_state[state_key] = {
            'events': event_map,
            'sync_token': sync_token,
            'ts': time.time()
        }
        _prune_sync_state_locked()
    return _decorate_events(event_map.values(), calendar_id, calendar_type_name, extra)


def list_events(calendar_type='both', time_min=None, time_max=None):
    """Load a bounded event window from one or both calendars."""
    if calendar_type not in ('odd', 'even', 'both'):
        raise ValueError("calendar_type must be one of: odd, even, both")

    time_min, time_max = _normalize_event_window(time_min, time_max)
    cache_key = (calendar_type, time_min, time_max)
    cached = _get_cache(cache_key)
    if cached is not None:
        print(f"⚡ Cache hit for '{calendar_type}': {len(cached)} events")
        return cached

    # Only one request refreshes the process cache; other requests reuse its result.
    with _refresh_lock:
        cached = _get_cache(cache_key)
        if cached is not None:
            return cached

        extra = load_extra()
        calendar_ids = []
        if calendar_type in ('odd', 'both'):
            calendar_ids.append(CALENDARS['odd'])
        if calendar_type in ('even', 'both'):
            calendar_ids.append(CALENDARS['even'])

        print(f"🔄 Fetching events from {len(calendar_ids)} calendar(s): {calendar_type}")
        all_events = []
        if len(calendar_ids) > 1:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(_fetch_single_calendar, calendar_id, time_min, time_max, extra): calendar_id
                    for calendar_id in calendar_ids
                }
                for future in as_completed(futures):
                    all_events.extend(future.result())
        else:
            all_events.extend(_fetch_single_calendar(calendar_ids[0], time_min, time_max, extra))

        def get_start_time(event):
            start = event.get('start', {})
            value = start.get('dateTime') or start.get('date')
            if not value:
                return datetime.max.replace(tzinfo=timezone.utc)
            try:
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                return datetime.max.replace(tzinfo=timezone.utc)

        all_events.sort(key=get_start_time)
        print(f"📅 Total: {len(all_events)} events (cache {CACHE_TTL}s)")
        _set_cache(cache_key, all_events)
        return all_events

# ✅ THÊM HÀM MỚI: Lấy single event bằng ID
def get_event(event_id):
    """
    Tìm event trên cả 2 calendars
    """
    try:
        if not event_id or event_id == "undefined":
            raise ValueError("Invalid event ID")
            
        print(f"🔍 Fetching single event: {event_id}")
        
        # Thử tìm trên cả 2 calendars (dò SONG SONG — mục 2)
        found_event = None
        found_calendar = None

        order, results = _probe_event_on_calendars(event_id)
        for calendar_id in order:
            res = results.get(calendar_id)
            cal_type = get_calendar_type_by_id(calendar_id)
            if isinstance(res, HttpError):
                if res.resp.status == 404:
                    continue  # Không tìm thấy trong calendar này, thử calendar khác
                raise res  # Lỗi khác, raise lên
            if isinstance(res, Exception):
                raise res
            event = res
            found_event = event
            found_calendar = calendar_id
            event['_calendar_source'] = cal_type
            event['_calendar_id'] = calendar_id
            print(f"✅ Found event in {cal_type.upper()} calendar")
            break

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
def create_event(class_info, idempotency_key=None):
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

        print(f"🎯 ========== CREATE EVENT ==========")
        # FIX M10: không log full class_info (chứa passcode/zoom_link)
        print(f"📥 Received class_info: name={class_info.get('name')} program={class_info.get('program')}")

        # 1️⃣ XÁC ĐỊNH TIMEZONE NGƯỜI DÙNG
        timezone = validate_timezone(class_info.get('timezone', 'Asia/Ho_Chi_Minh'))
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

        # 7️⃣ GỬI LÊN GOOGLE CALENDAR (idempotent across retries/double-clicks)
        result = _insert_event_idempotently(
            calendar_id,
            event,
            idempotency_key=idempotency_key
        )
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

        return result

    except Exception as e:
        print(f"❌ Error in create_event: {e}")
        import traceback
        traceback.print_exc()
        raise

# ========== GOOGLE CALENDAR UPDATE FUNCTIONS ==========


def _instance_start_from_id(instance_id):
    """Recover an occurrence's UTC start from Google's generated instance ID."""
    try:
        suffix = (instance_id or "").rsplit("_", 1)[1]
        parsed = datetime.strptime(suffix, "%Y%m%dT%H%M%SZ")
        return parsed.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    except (IndexError, TypeError, ValueError):
        return None


def update_this_instance(
    instance_id,
    master_event_id,
    calendar_id,
    class_info,
    current_event=None
):
    """Detach and update one occurrence while preserving the original behavior.

    EXDATE already removes the occurrence from its series. The old flow then
    tried to DELETE that cancelled occurrence, which Google rejects with HTTP
    400. Keep the existing detach-and-insert behavior, but omit that redundant
    DELETE request.
    """
    try:
        print("🎯 [GOOGLE] 'this' mode - Detaching one recurring instance")
        instance = current_event
        if instance is None:
            instance = calendar_service.events().get(
                calendarId=calendar_id, eventId=instance_id
            ).execute(http=_wr_http())

        instance_start = (
            (instance.get("originalStartTime") or instance.get("start") or {}).get("dateTime")
            or _instance_start_from_id(instance_id)
        )
        if not instance_start:
            raise ValueError("No recurring instance start time found")

        if not master_event_id:
            raise ValueError("Recurring occurrence is missing its master event ID")
        if instance_id == master_event_id and instance.get("recurrence"):
            master_event = dict(instance)
        else:
            master_event = calendar_service.events().get(
                calendarId=calendar_id, eventId=master_event_id
            ).execute(http=_wr_http())

        from recurrence_utils import add_exdate_to_master
        updated_recurrence = add_exdate_to_master(master_event, instance_start)
        if not updated_recurrence:
            raise ValueError("Master event has no recurrence rule")

        # A retry after the previous HTTP 400 sees the EXDATE already present.
        # In that case continue directly to INSERT the detached event.
        if updated_recurrence != master_event.get("recurrence", []):
            master_body = dict(master_event)
            master_body["recurrence"] = updated_recurrence
            calendar_service.events().update(
                calendarId=calendar_id,
                eventId=master_event_id,
                body=master_body
            ).execute(http=_wr_http())
            print(f"✅ Added EXDATE for occurrence {instance_id}")
        else:
            print(f"ℹ️ EXDATE already exists for occurrence {instance_id}; continuing retry")

        timezone = validate_timezone(class_info.get("timezone", "Asia/Ho_Chi_Minh"))
        start_normalized = normalize_datetime_with_timezone(
            class_info["start"], timezone
        )
        end_normalized = normalize_datetime_with_timezone(
            class_info["end"], timezone
        )

        detached_event = {
            "summary": class_info.get("name", master_event.get("summary", "")),
            "description": build_event_description(class_info) + "\n(Single event exception)",
            "location": class_info.get("zoom_link", master_event.get("location", "")),
            "start": {"dateTime": start_normalized, "timeZone": timezone},
            "end": {"dateTime": end_normalized, "timeZone": timezone},
        }

        # Do not DELETE here: EXDATE has already cancelled the occurrence.
        if instance_id != master_event_id:
            remove_extra(instance_id)
        result = calendar_service.events().insert(
            calendarId=calendar_id,
            body=detached_event,
            sendUpdates="all"
        ).execute(http=_wr_http())

        new_event_id = result.get("id")
        update_extra(
            new_event_id,
            class_info.get("meeting_id", ""),
            class_info.get("passcode", ""),
            class_info.get("zoom_link", ""),
            class_info.get("classname", ""),
            calendar_id,
        )
        print(f"✅ Detached recurring instance as event: {new_event_id}")
        return result

    except Exception as e:
        print(f"❌ Error in 'this' mode: {e}")
        import traceback
        traceback.print_exc()
        raise



def update_single_event(event_id, calendar_id, class_info, current_event=None):
    """
    ✅ Update non-recurring event (giữ UTC datetime, chỉ đổi timezone để Google Calendar hiển thị đúng ± giờ)
    """
    try:
        print(f"🎯 [GOOGLE] Updating single event")

        # update_event đã tải event để xác định calendar; tái sử dụng kết quả đó
        # thay vì trả thêm một events.get() giống hệt tới Google.
        event = dict(current_event) if current_event is not None else calendar_service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute(http=_wr_http())

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

        # 💾 Giữ nguyên semantics cũ: Google gửi update cho attendee.
        result = calendar_service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
            sendUpdates='all'
        ).execute(http=_wr_http())

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
        
        # Find which calendar has this event (dò SONG SONG — mục 2)
        current_event = None
        current_calendar_id = None

        order, results = _probe_event_on_calendars(event_id)
        for calendar_id in order:
            res = results.get(calendar_id)
            if isinstance(res, HttpError):
                if res.resp.status == 404:
                    continue
                raise res
            if isinstance(res, Exception):
                raise res
            current_event = res
            current_calendar_id = calendar_id
            print(f"✅ Found in {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'} calendar")
            break

        # **THỬ TÌM BẰNG MASTER ID NẾU KHÔNG TÌM THẤY** (dò SONG SONG — mục 2)
        if not current_event and class_info.get('master_event_id'):
            print(f"🔄 Event {event_id} not found, trying master ID: {class_info['master_event_id']}")
            master_order, master_results = _probe_event_on_calendars(class_info['master_event_id'])
            for calendar_id in master_order:
                res = master_results.get(calendar_id)
                if isinstance(res, HttpError):
                    if res.resp.status == 404:
                        continue
                    raise res
                if isinstance(res, Exception):
                    raise res
                current_event = res
                current_calendar_id = calendar_id
                event_id = class_info['master_event_id']  # Update to master ID
                print(f"✅ Found MASTER in {'EVEN' if calendar_id == CALENDARS['even'] else 'ODD'} calendar")
                break

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
                    event_id,
                    master_event_id,
                    current_calendar_id,
                    class_info,
                    current_event=current_event
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
            return update_following_events(
                event_id,
                master_event_id,
                current_calendar_id,
                class_info,
                current_event=current_event
            )
        
        elif master_event_id and edit_mode == 'this':
            print(f"🎯 Mode 'this'")
            return update_this_instance(
                event_id,
                master_event_id,
                current_calendar_id,
                class_info,
                current_event=current_event
            )
        
        else:
            # Non-recurring event
            print(f"🎯 Non-recurring event update")
            return update_single_event(
                event_id,
                current_calendar_id,
                class_info,
                current_event=current_event
            )
            
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
        ).execute(http=_wr_http())
        
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
    import pytz

    recurrence = master_event.get("recurrence")
    if not recurrence:
        return master_event

    # ⚙️ Chuẩn hóa UNTIL (RFC5545)
    dt = datetime.fromisoformat(instance_start_iso.replace("Z", "+00:00"))
    until_str = dt.astimezone(pytz.utc).strftime("%Y%m%dT%H%M%SZ")  # ✅ dạng hợp lệ

    # ⚠️ FIX M2: tìm ĐÚNG dòng RRULE (không giả định index 0) và GIỮ LẠI các dòng
    #    khác (EXDATE/RDATE) — trước đây ghi đè recurrence = [new_rrule] làm mất hết
    #    EXDATE nên các buổi đã loại trừ của chuỗi cũ xuất hiện lại sau khi split.
    updated = []
    rrule_found = False
    for rule in recurrence:
        if rule.startswith("RRULE:"):
            rrule_found = True
            rrule_parts = rule.replace("RRULE:", "").split(";")
            new_parts = [
                p for p in rrule_parts
                if p and not p.startswith("COUNT=") and not p.startswith("UNTIL=")
            ]
            updated.append("RRULE:" + ";".join(new_parts + [f"UNTIL={until_str}"]))
        else:
            updated.append(rule)

    if not rrule_found:
        # Không tìm thấy RRULE (bất thường) → giữ nguyên để không phá dữ liệu
        print("⚠️ stop_recurrence_at_instance: master không có RRULE, giữ nguyên")
        return master_event

    master_event["recurrence"] = updated
    print(f"🧩 stop_recurrence_at_instance → recurrence: {updated}")
    return master_event


def update_following_events(
    instance_id,
    master_event_id,
    calendar_id,
    class_info,
    current_event=None
):
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

        print("🎯 [FOLLOWING MODE - SPLIT SERIES] Starting...")

        # 1️⃣ Tái sử dụng target mà update_event đã tải. Master chỉ cần GET khi
        # target là một instance khác master.
        instance = current_event
        if instance is None:
            instance = calendar_service.events().get(
                calendarId=calendar_id, eventId=instance_id
            ).execute(http=_wr_http())
        if master_event_id == instance_id:
            master = instance
        else:
            master = calendar_service.events().get(
                calendarId=calendar_id, eventId=master_event_id
            ).execute(http=_wr_http())

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

        # 4️⃣ Dừng chuỗi cũ tại instance
        print(f"🧩 Stopping old series at {instance_start}")
        updated_master = stop_recurrence_at_instance(master, instance_start)
        calendar_service.events().update(
            calendarId=calendar_id,
            eventId=master_event_id,
            body=updated_master,
        ).execute(http=_wr_http())
        print("✅ Old series updated (stopped before instance)")

        # 5️⃣ Tạo chuỗi mới bắt đầu từ instance này
        # Frontend datetime-local values intentionally have no UTC offset. Treat
        # those values as wall-clock time in the selected timezone; calling
        # astimezone() directly on a naive datetime makes Python assume the
        # server timezone (UTC on Render) and shifts the event by seven hours.
        start_normalized = normalize_datetime_with_timezone(class_info["start"], timezone)
        end_normalized = normalize_datetime_with_timezone(class_info["end"], timezone)
        start_local = datetime.fromisoformat(start_normalized.replace("Z", "+00:00")).astimezone(tz)
        end_local = datetime.fromisoformat(end_normalized.replace("Z", "+00:00")).astimezone(tz)
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
        ).execute(http=_wr_http())

        new_event_id = result.get("id")
        print(f"✅ Created new master for following series: {new_event_id}")

        # 6️⃣ Xóa instance cũ vì đã tách ra thành chuỗi mới
        try:
            print(f"🗑️ Deleting old instance {instance_id} (now part of new series)")
            calendar_service.events().delete(
                calendarId=calendar_id,
                eventId=instance_id
            ).execute(http=_wr_http())
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
                calendar_service.events().move(
                    calendarId=calendar_id,
                    eventId=new_event_id,
                    destination=new_calendar_id,
                ).execute(http=_wr_http())
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
        # 🔍 TÌM EVENT THỰC TẾ TRÊN GOOGLE CALENDAR (dò SONG SONG — mục 2)
        # ==========================================================
        order, results = _probe_event_on_calendars(event_id)
        for calendar_id in order:
            res = results.get(calendar_id)
            # Trường hợp thường: tìm thấy event trực tiếp
            if not isinstance(res, Exception):
                current_event = res
                current_calendar_id = calendar_id
                break

            e = res
            if isinstance(e, HttpError) and e.resp.status in [404, 410]:
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
                        maxResults=2500,
                        fields="nextPageToken,items(id,recurringEventId,summary,start)"
                    ).execute(http=_wr_http())
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
                raise e

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
                ).execute(http=_wr_http())
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
                    maxResults=2500,
                    fields="nextPageToken,items(id,start)"
                ).execute(http=_wr_http())
                instances = instances_resp.get("items", [])
                print(f"📊 Found {len(instances)} instances under master {master_event_id}")

                instance_ids = []
                for inst in instances:
                    inst_start = inst.get("start", {}).get("dateTime")
                    if not inst_start:
                        continue

                    inst_dt = datetime.fromisoformat(inst_start.replace("Z", "+00:00")).astimezone(timezone.utc)
                    if inst_dt >= target_dt:
                        instance_ids.append(inst["id"])

                deleted_count = _delete_events_in_batches(
                    current_calendar_id,
                    instance_ids
                )

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
                ).execute(http=_wr_http())
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
                        maxResults=2500,
                        fields="nextPageToken,items(id,recurringEventId,summary,start)"
                    ).execute(http=_wr_http())
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
                                ).execute(http=_wr_http())
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
                    maxResults=2500,
                    fields="nextPageToken,items(id,recurringEventId,summary,start)"
                ).execute(http=_wr_http())
                items = resp.get("items", [])
                for ev in items:
                    eid = ev.get("id", "")
                    if old_event_id[:10] in eid:
                        print(f"✅ Found partial id match: {eid}")
                        calendar_service.events().delete(
                            calendarId=cid,
                            eventId=eid
                        ).execute(http=_wr_http())
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
                        maxResults=2500,
                        fields="nextPageToken,items(id,recurringEventId,summary,start)"
                    ).execute(http=_wr_http())
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
                            ).execute(http=_wr_http())
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
