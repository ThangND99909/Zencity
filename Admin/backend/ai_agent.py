import google.generativeai as genai
import json
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Warning: GEMINI_API_KEY not found")

# ====== THÊM HÀM HELPER ĐỂ FIX CONFLICT CHECK ======
def normalize_teacher_name(teacher_name):
    """Chuẩn hóa tên giáo viên để so sánh"""
    if not teacher_name:
        return ""
    return ' '.join(teacher_name.strip().lower().split())

def parse_iso_datetime_flexible(dt_str):
    """Parse datetime linh hoạt, xử lý cả với và không có timezone"""
    if not dt_str:
        return None
    
    try:
        # Xử lý string có Z
        if dt_str.endswith('Z'):
            dt_str = dt_str.replace('Z', '+00:00')
        
        # Nếu không có timezone, thêm timezone mặc định (Vietnam)
        if 'T' in dt_str and '+' not in dt_str and '-' not in dt_str.split('T')[1]:
            dt_str = dt_str + '+07:00'
        
        return datetime.fromisoformat(dt_str)
    except ValueError as e:
        print(f"❌ Error parsing datetime {dt_str}: {e}")
        return None

def extract_teacher_from_event(cls):
    """Trích xuất teacher từ event - ưu tiên field teacher trước"""
    # Ưu tiên field teacher
    cls_teacher = cls.get('teacher', '')
    if cls_teacher:
        return cls_teacher
    
    # Fallback: extract từ summary
    summary = cls.get('summary', '')
    if ' - ' in summary:
        parts = summary.split(' - ')
        if len(parts) >= 2:
            return parts[1].strip()
    
    return ""

# ====== GIỮ NGUYÊN CÁC HÀM CŨ ======
def suggest_schedule(existing_classes, teacher=None, duration_hours=1, preferred_times=None):
    """
    Gợi ý lịch học với Google Gemini
    """
    if not GEMINI_API_KEY:
        return {"error": "Gemini API key not configured"}
    
    try:
        # Chuyển lịch hiện tại thành text
        schedule_text = ""
        for c in existing_classes:
            summary = c.get('summary', 'No title')
            description = c.get('description', '')
            start = c.get('start', {}).get('dateTime', 'Unknown')
            end = c.get('end', {}).get('dateTime', 'Unknown')
            schedule_text += f"- {summary}: {start} to {end}\n"
            if description:
                schedule_text += f"  Details: {description}\n"

        # Build prompt cho Gemini
        prompt = f"""
Bạn là trợ lý AI sắp xếp lịch học. Hãy phân tích lịch hiện tại và gợi ý khung giờ trống.

LỊCH HIỆN TẠI:
{schedule_text}

YÊU CẦU:
- Tìm khung giờ trống cho lớp học kéo dài {duration_hours} giờ
- {'Tránh trùng lịch của giáo viên: ' + teacher if teacher else 'Không có ràng buộc giáo viên cụ thể'}
- Ưu tiên giờ hành chính (8h-18h) các ngày trong tuần
- Trả về kết quả DUY NHẤT dạng JSON: {{"start": "YYYY-MM-DDTHH:MM:SS", "end": "YYYY-MM-DDTHH:MM:SS"}}
- Sử dụng múi giờ Asia/Ho_Chi_Minh (UTC+7)

Hãy phân tích kỹ và đề xuất khung giờ hợp lý, tránh xung đột.
"""

        # Initialize Gemini model
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        response = model.generate_content(prompt)
        
        # Extract text from response
        text = response.text.strip()
        
        # Clean response - remove markdown code blocks if any
        text = text.replace('```json', '').replace('```', '').strip()
        
        try:
            result = json.loads(text)
            
            # Validate result
            if 'start' in result and 'end' in result:
                return result
            else:
                return {"error": "Gemini response missing required fields", "raw_response": text}
                
        except json.JSONDecodeError as e:
            print(f"Gemini JSON parse error: {e}")
            print(f"Raw response: {text}")
            return {"error": f"Failed to parse Gemini response: {str(e)}", "raw_response": text}
            
    except Exception as e:
        print(f"Gemini API error: {e}")
        return {"error": f"Gemini service error: {str(e)}"}

def suggest_schedule_fallback(existing_classes, teacher=None, duration_hours=1):
    """
    Fallback logic khi Gemini không hoạt động
    """
    try:
        # Tìm slot trống đơn giản: ngày mai 9:00 AM
        from datetime import datetime, timedelta
        
        tomorrow = datetime.now() + timedelta(days=1)
        start_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=duration_hours)
        
        return {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "note": "Using fallback scheduling"
        }
    except Exception as e:
        return {"error": f"Fallback failed: {str(e)}"}

# Function chính với fallback
def get_schedule_suggestion(existing_classes, teacher=None, duration_hours=1, preferred_times=None):
    """
    Main function với fallback mechanism
    """
    result = suggest_schedule(existing_classes, teacher, duration_hours, preferred_times)
    
    if 'error' in result:
        print(f"Gemini failed: {result['error']}, using fallback")
        return suggest_schedule_fallback(existing_classes, teacher, duration_hours)
    
    return result

# ====== AI-POWERED CONFLICT CHECK - ĐÃ SỬA LỖI ======

def ai_check_schedule_conflict(existing_classes, teacher, new_start, new_end, exclude_event_id=None):
    """
    Sử dụng AI để kiểm tra xung đột lịch THÔNG MINH
    """
    if not GEMINI_API_KEY:
        return {"error": "Gemini API key not configured"}
    
    try:
        print(f"🤖 AI đang phân tích xung đột cho giáo viên: {teacher}")
        
        # Format lịch hiện tại cho AI
        schedule_text = ""
        teacher_events_count = 0
        
        for cls in existing_classes:
            # Bỏ qua event hiện tại nếu đang edit
            if exclude_event_id and cls.get('id') == exclude_event_id:
                continue
                
            summary = cls.get('summary', 'No title')
            start = cls.get('start', {}).get('dateTime', 'Unknown')
            end = cls.get('end', {}).get('dateTime', 'Unknown')
            
            # Parse teacher từ event - DÙNG HÀM MỚI
            cls_teacher = extract_teacher_from_event(cls)
            
            schedule_text += f"- {summary} (GV: {cls_teacher}): {start} to {end}\n"
            
            # Đếm số event của giáo viên này - DÙNG SO SÁNH CHUẨN HÓA
            if cls_teacher and normalize_teacher_name(teacher) == normalize_teacher_name(cls_teacher):
                teacher_events_count += 1

        # Tính thời lượng - DÙNG HÀM PARSE MỚI
        new_start_dt = parse_iso_datetime_flexible(new_start)
        new_end_dt = parse_iso_datetime_flexible(new_end)
        duration_hours = (new_end_dt - new_start_dt).total_seconds() / 3600 if new_start_dt and new_end_dt else 0

        # Build prompt cho AI
        prompt = f"""
Bạn là trợ lý AI kiểm tra xung đột lịch học THÔNG MINH.

THÔNG TIN KIỂM TRA:
- Giáo viên: {teacher}
- Thời gian muốn tạo: {new_start} to {new_end} 
- Thời lượng: {duration_hours:.1f} giờ
- Giáo viên này hiện có {teacher_events_count} sự kiện

LỊCH HIỆN TẠI:
{schedule_text}

HÃY PHÂN TÍCH VÀ TRẢ LỜI:
1. Liệt kê tất cả xung đột trực tiếp với giáo viên {teacher}
2. Đề xuất 2 khung giờ thay thế tốt nhất trong 3 ngày tới
3. Phân tích ngắn gọn

TRẢ VỀ ĐỊNH DẠNG JSON SAU:
{{
    "has_conflict": true/false,
    "conflicts": [
        {{
            "event_summary": "tên sự kiện",
            "event_teacher": "tên giáo viên", 
            "event_start": "thời gian bắt đầu",
            "event_end": "thời gian kết thúc",
            "conflict_type": "teacher_schedule_conflict"
        }}
    ],
    "suggestions": [
        {{
            "start": "YYYY-MM-DDTHH:MM:SS",
            "end": "YYYY-MM-DDTHH:MM:SS",
            "description": "mô tả ngắn"
        }}
    ],
    "ai_analysis": "phân tích ngắn gọn từ AI"
}}

Chú ý: Chỉ kiểm tra xung đột trực tiếp, đề xuất thời gian hợp lý.
"""

        # Gọi Gemini
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        text = response.text.strip()
        text = text.replace('```json', '').replace('```', '').strip()
        
        print(f"🤖 AI Response: {text}")
        
        try:
            result = json.loads(text)
            print(f"✅ AI Conflict check completed: {result.get('has_conflict')}")
            return result
            
        except json.JSONDecodeError as e:
            print(f"❌ AI JSON parse error: {e}")
            # Fallback về logic thông thường
            return traditional_conflict_check(existing_classes, teacher, new_start, new_end, exclude_event_id)
            
    except Exception as e:
        print(f"❌ AI conflict check error: {e}")
        # Fallback về logic thông thường
        return traditional_conflict_check(existing_classes, teacher, new_start, new_end, exclude_event_id)

def traditional_conflict_check(existing_classes, teacher, new_start, new_end, exclude_event_id=None):
    """
    Traditional check TỐI ƯU - ĐÃ SỬA LỖI TIMEZONE
    """
    try:
        print(f"⚡ FAST traditional check for: {teacher}")
        print(f"📅 New event: {new_start} to {new_end}")
        
        # DÙNG HÀM PARSE MỚI - linh hoạt timezone
        new_start_dt = parse_iso_datetime_flexible(new_start)
        new_end_dt = parse_iso_datetime_flexible(new_end)
        
        if not new_start_dt or not new_end_dt:
            print(f"❌ Invalid datetime: new_start={new_start}, new_end={new_end}")
            return {'has_conflict': False, 'error': 'Invalid datetime format'}
        
        # ✅ CHUYỂN TẤT CẢ VỀ UTC ĐỂ SO SÁNH CHUẨN
        new_start_utc = new_start_dt.astimezone(timezone.utc)
        new_end_utc = new_end_dt.astimezone(timezone.utc)
        
        print(f"🌍 UTC Time: {new_start_utc} to {new_end_utc}")
        
        conflicts = []
        normalized_teacher = normalize_teacher_name(teacher)
        
        print(f"🔍 Checking {len(existing_classes)} events for teacher: '{teacher}'")
        
        teacher_match_count = 0
        
        for cls in existing_classes:
            # Bỏ qua event hiện tại nếu đang edit
            if exclude_event_id and cls.get('id') == exclude_event_id:
                continue
            
            # DÙNG HÀM EXTRACT MỚI - ưu tiên field teacher
            cls_teacher = extract_teacher_from_event(cls)
            
            if not cls_teacher:
                continue
                
            # SO SÁNH CHUẨN HÓA - chính xác hơn
            cls_normalized = normalize_teacher_name(cls_teacher)
            teacher_match = (cls_normalized == normalized_teacher)
            
            if teacher_match:
                teacher_match_count += 1
                
                cls_start_str = cls.get('start', {}).get('dateTime', '')
                cls_end_str = cls.get('end', {}).get('dateTime', '')
                
                if cls_start_str and cls_end_str:
                    # DÙNG HÀM PARSE MỚI
                    cls_start = parse_iso_datetime_flexible(cls_start_str)
                    cls_end = parse_iso_datetime_flexible(cls_end_str)
                    
                    if cls_start and cls_end:
                        # ✅ CHUYỂN SANG UTC ĐỂ SO SÁNH
                        cls_start_utc = cls_start.astimezone(timezone.utc)
                        cls_end_utc = cls_end.astimezone(timezone.utc)
                        
                        print(f"  🔍 Comparing with: {cls.get('summary')}")
                        print(f"     Local: {cls_start} to {cls_end}")
                        print(f"     UTC: {cls_start_utc} to {cls_end_utc}")
                        
                        # Kiểm tra overlap TRONG UTC
                        time_conflict = (new_start_utc < cls_end_utc) and (new_end_utc > cls_start_utc)
                        
                        if time_conflict:
                            conflicts.append({
                                'event_summary': cls.get('summary', 'No title'),
                                'event_teacher': cls_teacher,
                                'event_start': cls_start_str,
                                'event_end': cls_end_str,
                                'conflict_type': 'teacher_schedule_conflict',
                                'timezone_note': f"Conflict detected in UTC time (same actual time)"
                            })
                            print(f"     🚨 CONFLICT DETECTED - Same actual time!")
                        else:
                            print(f"     ✅ No conflict - Different timezones")
        
        print(f"📊 Checked {teacher_match_count} events with teacher '{teacher}', found {len(conflicts)} conflicts")
        
        return {
            'has_conflict': len(conflicts) > 0,
            'conflicts': conflicts,
            'conflict_count': len(conflicts),
            'ai_analysis': f'Kiểm tra nhanh: {len(conflicts)} xung đột' if conflicts else 'Không có xung đột'
        }
        
    except Exception as e:
        print(f"❌ Traditional conflict check error: {e}")
        return {'has_conflict': False, 'error': str(e)}