# backend/recurrence_utils.py
"""
Utility functions for handling Google Calendar recurrence rules
"""
import re
from datetime import datetime, timedelta
import pytz

def parse_rrule_string(rrule_str):
    """
    Parse RRULE string into components
    """
    result = {
        'freq': None,
        'count': None,
        'until': None,
        'interval': 1,
        'byday': [],
        'bymonthday': [],
        'bymonth': []
    }
    
    try:
        # Parse FREQ
        freq_match = re.search(r'FREQ=(\w+)', rrule_str, re.IGNORECASE)
        if freq_match:
            result['freq'] = freq_match.group(1).upper()
        
        # Parse COUNT
        count_match = re.search(r'COUNT=(\d+)', rrule_str, re.IGNORECASE)
        if count_match:
            result['count'] = int(count_match.group(1))
        
        # Parse UNTIL
        until_match = re.search(r'UNTIL=([\dTZ]+)', rrule_str, re.IGNORECASE)
        if until_match:
            result['until'] = until_match.group(1)
        
        # Parse INTERVAL
        interval_match = re.search(r'INTERVAL=(\d+)', rrule_str, re.IGNORECASE)
        if interval_match:
            result['interval'] = int(interval_match.group(1))
        
        # Parse BYDAY
        byday_match = re.search(r'BYDAY=([A-Z,]+)', rrule_str, re.IGNORECASE)
        if byday_match:
            result['byday'] = byday_match.group(1).split(',')
        
        # Parse BYMONTHDAY
        bymonthday_match = re.search(r'BYMONTHDAY=([\d,-]+)', rrule_str, re.IGNORECASE)
        if bymonthday_match:
            result['bymonthday'] = [int(x) for x in bymonthday_match.group(1).split(',')]
        
        # Parse BYMONTH
        bymonth_match = re.search(r'BYMONTH=([\d,]+)', rrule_str, re.IGNORECASE)
        if bymonth_match:
            result['bymonth'] = [int(x) for x in bymonth_match.group(1).split(',')]
            
    except Exception as e:
        print(f"⚠️ Error parsing RRULE: {e}")
    
    return result

def build_rrule_string(components):
    """
    Build RRULE string from components
    """
    parts = []
    
    if components.get('freq'):
        parts.append(f"FREQ={components['freq']}")
    
    if components.get('interval') and components['interval'] > 1:
        parts.append(f"INTERVAL={components['interval']}")
    
    if components.get('count'):
        parts.append(f"COUNT={components['count']}")
    
    if components.get('until'):
        parts.append(f"UNTIL={components['until']}")
    
    if components.get('byday'):
        parts.append(f"BYDAY={','.join(components['byday'])}")
    
    if components.get('bymonthday'):
        parts.append(f"BYMONTHDAY={','.join(map(str, components['bymonthday']))}")
    
    if components.get('bymonth'):
        parts.append(f"BYMONTH={','.join(map(str, components['bymonth']))}")
    
    return ';'.join(parts)

def update_recurrence_for_following_delete(master_event, delete_instance_start):
    """
    Update recurrence rules to delete this and following events
    Returns updated recurrence rules list
    """
    try:
        recurrence = master_event.get('recurrence', [])
        if not recurrence:
            return recurrence
        
        # Parse delete instance time
        delete_dt = datetime.fromisoformat(delete_instance_start.replace('Z', '+00:00'))
        
        # Get master start time
        master_start_str = master_event.get('start', {}).get('dateTime')
        if not master_start_str:
            print("⚠️ No master start time found")
            return recurrence
        
        master_start = datetime.fromisoformat(master_start_str.replace('Z', '+00:00'))
        
        # Process each rule
        updated_rules = []
        
        for rule in recurrence:
            if 'RRULE:' not in rule:
                # Not an RRULE, keep as is
                updated_rules.append(rule)
                continue
            
            rrule_str = rule.replace('RRULE:', '')
            components = parse_rrule_string(rrule_str)
            
            if not components['freq']:
                # Invalid RRULE, skip
                updated_rules.append(rule)
                continue
            
            # Calculate events before delete date
            try:
                from dateutil import rrule
                
                # Create rrule object
                rr = rrule.rrulestr(rrule_str, dtstart=master_start)
                
                # Get all occurrences before delete date
                events_before = list(rr.before(delete_dt, inc=True))
                
                if not events_before:
                    # No events before delete date - delete entire series
                    print("⚠️ No events before delete date, removing rule")
                    continue
                
                # Check if delete date is the first occurrence
                if len(events_before) == 1 and events_before[0] == master_start:
                    # Deleting first occurrence - remove entire series
                    print("⚠️ Deleting first occurrence, removing rule")
                    continue
                
                # Update COUNT or add UNTIL
                if components['count']:
                    # Update COUNT to number of events before delete
                    components['count'] = len(events_before)
                else:
                    # Add UNTIL to stop at last event before delete
                    last_event = events_before[-1]
                    # Format as Google Calendar expects: YYYYMMDDTHHMMSSZ
                    until_str = last_event.strftime('%Y%m%dT%H%M%SZ')
                    components['until'] = until_str
                
                # Rebuild RRULE
                new_rrule_str = build_rrule_string(components)
                updated_rules.append(f'RRULE:{new_rrule_str}')
                
            except ImportError:
                # dateutil not available, use simple logic
                print("⚠️ dateutil not available, using simple logic")
                
                if components['count']:
                    # Simple: reduce count by half (fallback)
                    components['count'] = max(1, components['count'] // 2)
                    new_rrule_str = build_rrule_string(components)
                    updated_rules.append(f'RRULE:{new_rrule_str}')
                else:
                    # Add UNTIL at delete date - 1 day
                    until_dt = delete_dt - timedelta(days=1)
                    until_str = until_dt.strftime('%Y%m%dT%H%M%SZ')
                    components['until'] = until_str
                    new_rrule_str = build_rrule_string(components)
                    updated_rules.append(f'RRULE:{new_rrule_str}')
            
            except Exception as e:
                print(f"⚠️ Error processing RRULE: {e}")
                # Keep original rule as fallback
                updated_rules.append(rule)
        
        return updated_rules
        
    except Exception as e:
        print(f"❌ Error in update_recurrence_for_following_delete: {e}")
        return master_event.get('recurrence', [])

def is_first_recurring_instance(master_event, instance_start):
    """
    Check if this instance is the first in the recurring series
    """
    try:
        master_start_str = master_event.get('start', {}).get('dateTime')
        if not master_start_str or not instance_start:
            return False
        
        master_start = datetime.fromisoformat(master_start_str.replace('Z', '+00:00'))
        instance_dt = datetime.fromisoformat(instance_start.replace('Z', '+00:00'))
        
        # Allow small difference for timezone issues
        time_diff = abs((instance_dt - master_start).total_seconds())
        return time_diff < 60  # Within 1 minute
        
    except Exception as e:
        print(f"⚠️ Error checking first instance: {e}")
        return False

def calculate_remaining_events(rrule_str, master_start, delete_dt):
    """
    Calculate number of events remaining before delete date
    """
    try:
        from dateutil import rrule
        
        rr = rrule.rrulestr(rrule_str, dtstart=master_start)
        events_before = list(rr.before(delete_dt, inc=True))
        return len(events_before)
        
    except Exception:
        # Fallback estimation
        components = parse_rrule_string(rrule_str)
        
        if components['freq'] == 'DAILY':
            days_diff = (delete_dt - master_start).days
            if components.get('interval'):
                return max(1, days_diff // components['interval'])
            return max(1, days_diff)
        
        elif components['freq'] == 'WEEKLY':
            weeks_diff = (delete_dt - master_start).days // 7
            if components.get('interval'):
                return max(1, weeks_diff // components['interval'])
            return max(1, weeks_diff)
        
        elif components['freq'] == 'MONTHLY':
            months_diff = (delete_dt.year - master_start.year) * 12 + (delete_dt.month - master_start.month)
            if components.get('interval'):
                return max(1, months_diff // components['interval'])
            return max(1, months_diff)
        
        else:
            # Default fallback
            return 1
        
def stop_recurrence_at_instance(master_event, instance_start_str):
    """
    Google Calendar 'following' mode: Thêm UNTIL để dừng series TRƯỚC instance
    """
    try:
        from datetime import datetime, timedelta
        import re
        
        print(f"🎯 [GOOGLE] Adding UNTIL for 'following' mode")
        
        # Parse instance time
        instance_dt = datetime.fromisoformat(instance_start_str.replace('Z', '+00:00'))
        
        # Stop 1 second BEFORE instance
        until_dt = instance_dt - timedelta(seconds=1)
        until_str = until_dt.strftime('%Y%m%dT%H%M%SZ')
        
        recurrence = master_event.get('recurrence', [])
        updated_recurrence = []
        
        for rule in recurrence:
            if 'RRULE:' in rule:
                rrule_str = rule.replace('RRULE:', '')
                
                # Remove existing UNTIL and COUNT
                rrule_str = re.sub(r'UNTIL=[\dTZ]+', '', rrule_str)
                rrule_str = re.sub(r'COUNT=\d+', '', rrule_str)
                
                # Clean up
                rrule_str = re.sub(r';;', ';', rrule_str)
                rrule_str = rrule_str.strip(';')
                
                # Add UNTIL
                if rrule_str:
                    new_rrule = f'{rrule_str};UNTIL={until_str}'
                else:
                    new_rrule = f'UNTIL={until_str}'
                
                updated_recurrence.append(f'RRULE:{new_rrule}')
                print(f"✅ Added UNTIL={until_str}")
                
            elif rule.startswith('EXDATE:'):
                # Keep existing EXDATEs
                updated_recurrence.append(rule)
            else:
                updated_recurrence.append(rule)
        
        return updated_recurrence
        
    except Exception as e:
        print(f"❌ Error adding UNTIL: {e}")
        return master_event.get('recurrence', [])
    
def parse_and_update_recurrence_rule(rrule_str, stop_before_date_str):
    """
    Parse RRULE and update it to stop before a specific date
    """
    try:
        from datetime import datetime, timedelta
        import re
        
        # Parse stop date
        stop_dt = datetime.fromisoformat(stop_before_date_str.replace('Z', '+00:00'))
        until_str = (stop_dt - timedelta(seconds=1)).strftime('%Y%m%dT%H%M%SZ')
        
        # Remove existing COUNT and UNTIL
        rrule_str = re.sub(r'COUNT=\d+', '', rrule_str)
        rrule_str = re.sub(r'UNTIL=[\dTZ]+', '', rrule_str)
        
        # Clean up
        rrule_str = re.sub(r';;', ';', rrule_str)
        rrule_str = rrule_str.strip(';')
        
        # Add UNTIL
        if rrule_str:
            return f'{rrule_str};UNTIL={until_str}'
        else:
            return f'UNTIL={until_str}'
        
    except Exception as e:
        print(f"❌ Error parsing RRULE: {e}")
        return rrule_str  # Return original on error
    
def calculate_remaining_count(rrule_str, master_start, stop_before):
    """
    Tính COUNT còn lại khi dừng tại thời điểm cụ thể
    """
    try:
        from dateutil import rrule
        from datetime import datetime
        
        rr = rrule.rrulestr(rrule_str, dtstart=master_start)
        occurrences = list(rr.before(datetime.fromisoformat(stop_before.replace('Z', '+00:00')), inc=True))
        return len(occurrences)
    except:
        # Fallback logic
        return 1
    
def calculate_remaining_occurrences(master_event, stop_before_instance_start):
    """
    Tính số events còn lại trong series từ instance này trở đi
    """
    try:
        from dateutil import rrule
        from datetime import datetime
        
        recurrence = master_event.get('recurrence', [])
        if not recurrence:
            return 0
            
        # Tìm RRULE
        rrule_str = None
        for rule in recurrence:
            if 'RRULE:' in rule:
                rrule_str = rule.replace('RRULE:', '')
                break
                
        if not rrule_str:
            return 0
            
        # Parse master start
        master_start_str = master_event.get('start', {}).get('dateTime')
        if not master_start_str:
            return 0
            
        master_start = datetime.fromisoformat(master_start_str.replace('Z', '+00:00'))
        stop_before = datetime.fromisoformat(stop_before_instance_start.replace('Z', '+00:00'))
        
        # Tạo rrule object
        rr = rrule.rrulestr(rrule_str, dtstart=master_start)
        
        # Đếm events từ instance này trở đi
        occurrences = list(rr)
        remaining = 0
        for occ in occurrences:
            if occ >= stop_before:
                remaining += 1
                
        return remaining
        
    except Exception as e:
        print(f"⚠️ Error calculating remaining occurrences: {e}")
        # Fallback: trả về COUNT từ RRULE nếu có
        import re
        count_match = re.search(r'COUNT=(\d+)', rrule_str)
        if count_match:
            total = int(count_match.group(1))
            # Ước tính: giả sử instance này là thứ 2 trong series
            return max(1, total - 1)
        return 1
    
# Thêm vào recurrence_utils.py
def add_exdate_to_master(master_event, instance_start_str):
    """
    Google Calendar 'this' mode: Thêm EXDATE để loại trừ instance
    FIX: Luôn dùng UTC format cho EXDATE
    """
    try:
        from datetime import datetime
        
        print(f"🎯 [GOOGLE] Adding EXDATE for 'this' mode")
        print(f"🕐 Instance to exclude: {instance_start_str}")
        
        # Parse instance time
        instance_dt = datetime.fromisoformat(instance_start_str.replace('Z', '+00:00'))
        
        # ⚠️ FIX: LUÔN DÙNG UTC FORMAT (YYYYMMDDTHHMMSSZ)
        exdate_str = instance_dt.strftime('%Y%m%dT%H%M%SZ')
        print(f"✅ EXDATE (UTC format): {exdate_str}")
        
        recurrence = master_event.get('recurrence', [])
        if not recurrence:
            print("⚠️ Master has no recurrence rules")
            return []
        
        updated_recurrence = []
        exdate_added = False
        
        for rule in recurrence:
            if rule.startswith('EXDATE;'):
                # ⚠️ FIX: Remove TZID và chuyển sang UTC format
                # Tách phần sau EXDATE;
                if 'TZID=' in rule:
                    # Format: EXDATE;TZID=Asia/Ho_Chi_Minh:20251209T150000
                    parts = rule.split(':')
                    if len(parts) >= 2:
                        old_exdate = parts[-1]
                        # Chuyển sang UTC nếu cần
                        print(f"🔄 Converting TZID EXDATE to UTC: {old_exdate}")
                else:
                    # Đã là UTC format
                    existing = rule.replace('EXDATE;', '').strip()
                    existing_dates = [d.strip() for d in existing.split(',') if d.strip()]
                    
                    if exdate_str not in existing_dates:
                        existing_dates.append(exdate_str)
                        new_rule = f'EXDATE:{",".join(existing_dates)}'
                        updated_recurrence.append(new_rule)
                        print(f"✅ Added to EXDATE: {exdate_str}")
                    else:
                        updated_recurrence.append(rule)
                        print(f"ℹ️ EXDATE already exists")
                    exdate_added = True
            elif rule.startswith('EXDATE:'):
                # UTC format đúng
                existing = rule.replace('EXDATE:', '').strip()
                existing_dates = [d.strip() for d in existing.split(',') if d.strip()]
                
                if exdate_str not in existing_dates:
                    existing_dates.append(exdate_str)
                    new_rule = f'EXDATE:{",".join(existing_dates)}'
                    updated_recurrence.append(new_rule)
                    print(f"✅ Added to EXDATE: {exdate_str}")
                else:
                    updated_recurrence.append(rule)
                    print(f"ℹ️ EXDATE already exists")
                exdate_added = True
            elif 'RRULE:' in rule:
                updated_recurrence.append(rule)
            else:
                updated_recurrence.append(rule)
        
        # Nếu không có EXDATE rule, thêm mới với UTC format
        if not exdate_added:
            updated_recurrence.append(f'EXDATE:{exdate_str}')
            print(f"✅ Created new EXDATE (UTC): {exdate_str}")
        
        # ⚠️ QUAN TRỌNG: Đảm bảo RRULE vẫn ở đó
        if not any('RRULE:' in r for r in updated_recurrence):
            # Thêm lại RRULE nếu bị mất
            for rule in recurrence:
                if 'RRULE:' in rule:
                    updated_recurrence.append(rule)
                    print(f"🔄 Added back RRULE")
                    break
        
        print(f"📋 Updated recurrence: {updated_recurrence}")
        return updated_recurrence
        
    except Exception as e:
        print(f"❌ Error adding EXDATE: {e}")
        import traceback
        traceback.print_exc()
        return master_event.get('recurrence', [])
    
def calculate_new_count(master_event, instance_start_str):
    """
    Calculate new COUNT for 'following' mode
    """
    try:
        from datetime import datetime
        import re
        
        master_start_str = master_event.get('start', {}).get('dateTime')
        if not master_start_str:
            return 1
        
        master_start = datetime.fromisoformat(master_start_str.replace('Z', '+00:00'))
        instance_start = datetime.fromisoformat(instance_start_str.replace('Z', '+00:00'))
        
        days_diff = (instance_start - master_start).days
        
        recurrence = master_event.get('recurrence', [])
        for rule in recurrence:
            if 'RRULE:' in rule:
                rrule = rule.replace('RRULE:', '')
                
                # Get frequency
                freq_match = re.search(r'FREQ=(\w+)', rrule, re.IGNORECASE)
                if not freq_match:
                    return 1
                
                freq = freq_match.group(1).upper()
                
                # Get current COUNT
                count_match = re.search(r'COUNT=(\d+)', rrule, re.IGNORECASE)
                if count_match:
                    total = int(count_match.group(1))
                    
                    # Estimate remaining events
                    if freq == 'DAILY':
                        remaining = max(1, total - days_diff)
                    elif freq == 'WEEKLY':
                        remaining = max(1, total - (days_diff // 7))
                    elif freq == 'MONTHLY':
                        remaining = max(1, total - (days_diff // 30))
                    else:
                        remaining = max(1, total - 1)
                    
                    print(f"📊 New COUNT: {remaining} (from {total})")
                    return remaining
        
        return 1
        
    except Exception as e:
        print(f"⚠️ Error calculating count: {e}")
        return 1