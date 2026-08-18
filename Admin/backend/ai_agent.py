import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
from log_config import make_print

print = make_print(__name__)

load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Warning: GEMINI_API_KEY not found")


def suggest_schedule(existing_classes, teacher=None, duration_hours=1):
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
def get_schedule_suggestion(existing_classes, teacher=None, duration_hours=1):
    """
    Main function với fallback mechanism
    """
    result = suggest_schedule(existing_classes, teacher, duration_hours)

    if 'error' in result:
        print(f"Gemini failed: {result['error']}, using fallback")
        return suggest_schedule_fallback(existing_classes, teacher, duration_hours)

    return result
