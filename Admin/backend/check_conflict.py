from datetime import datetime, timezone
from log_config import make_print

print = make_print(__name__)


def normalize_teacher_name(teacher_name):
    """Chuẩn hóa tên giáo viên để so sánh"""
    if not teacher_name:
        return ""
    return ' '.join(teacher_name.strip().lower().split())

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
