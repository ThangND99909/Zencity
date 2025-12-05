import sys
import os

# Thêm thư mục hiện tại vào path để import
sys.path.append(os.path.dirname(__file__))

from ai_agent import traditional_conflict_check

# Thêm vào test_conflict.py
def test_with_real_data():
    print("\n🧪 TEST WITH REAL CALENDAR DATA")
    
    from calendar_crud import list_events
    
    # Lấy events thực tế từ Google Calendar
    real_events = list_events()
    print(f"📅 Found {len(real_events)} real events")
    
    if len(real_events) > 0:
        # Lấy event đầu tiên có teacher
        sample_event = None
        for event in real_events:
            if event.get('teacher'):
                sample_event = event
                break
        
        if sample_event:
            print(f"🔍 Testing with real event: {sample_event.get('summary')}")
            print(f"   Teacher: {sample_event.get('teacher')}")
            print(f"   Time: {sample_event.get('start', {}).get('dateTime')}")
            
            result = traditional_conflict_check(
                [sample_event], 
                sample_event.get('teacher'),
                sample_event.get('start', {}).get('dateTime'),
                sample_event.get('end', {}).get('dateTime')
            )
            
            print(f"🎯 Result: {result['has_conflict']} (should be True)")
        else:
            print("❌ No events with teacher field found")
    else:
        print("❌ No events found in calendar")

if __name__ == "__main__":
   
    test_with_real_data()  # Thêm dòng này
