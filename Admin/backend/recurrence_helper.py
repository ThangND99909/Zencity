def build_recurrence_rule(class_info):
    """
    Build recurrence rule cho Google Calendar - CHỈ TRẢ VỀ RRULE STRING
    """
    print(f"🔧 build_recurrence_rule called with:")
    print(f"   class_info['recurrence']: '{class_info.get('recurrence')}'")
    print(f"   class_info['timezone']: '{class_info.get('timezone')}'")
    
    freq = class_info.get("recurrence", "").upper().strip()
    print(f"   Extracted freq: '{freq}'")
    
    if not freq:
        print("🔁 No recurrence specified, returning None")
        return None

    rrule_parts = [f"FREQ={freq}"]
    print(f"   Initial rules: {rrule_parts}")

    # COUNT - số lần lặp
    repeat_count = class_info.get("repeat_count", 1)
    print(f"   repeat_count: {repeat_count}")
    if repeat_count > 0:
        rrule_parts.append(f"COUNT={repeat_count}")
        print(f"   Added COUNT: {rrule_parts}")

    # BYDAY cho WEEKLY
    if freq == "WEEKLY" and class_info.get("byday"):
        byday_str = ','.join(class_info['byday'])
        rrule_parts.append(f"BYDAY={byday_str}")
        print(f"   Added BYDAY: {rrule_parts}")

    # BYMONTHDAY cho MONTHLY
    if freq == "MONTHLY" and class_info.get("bymonthday"):
        bymonthday_str = ','.join(map(str, class_info['bymonthday']))
        rrule_parts.append(f"BYMONTHDAY={bymonthday_str}")
        print(f"   Added BYMONTHDAY: {rrule_parts}")

    # BYMONTH và BYMONTHDAY cho YEARLY
    if freq == "YEARLY":
        if class_info.get("bymonth"):
            bymonth_str = ','.join(map(str, class_info['bymonth']))
            rrule_parts.append(f"BYMONTH={bymonth_str}")
            print(f"   Added BYMONTH: {rrule_parts}")
        if class_info.get("bymonthday"):
            bymonthday_str = ','.join(map(str, class_info['bymonthday']))
            rrule_parts.append(f"BYMONTHDAY={bymonthday_str}")
            print(f"   Added BYMONTHDAY: {rrule_parts}")

    # INTERVAL mặc định là 1
    rrule_parts.append("INTERVAL=1")
    print(f"   Added INTERVAL: {rrule_parts}")

    rrule = "RRULE:" + ";".join(rrule_parts)
    print(f"📆 Generated RRULE: {rrule}")
    
    # ✅ CHỈ TRẢ VỀ RRULE STRING, KHÔNG PHẢI OBJECT
    return rrule

# ✅ THÊM HÀM RIÊNG ĐỂ TẠO RECURRENCE DESCRIPTION
def build_recurrence_description(class_info):
    """
    Xây dựng mô tả recurrence có timezone cho hiển thị
    """
    freq = class_info.get("recurrence", "").upper().strip()
    timezone = class_info.get('timezone', 'Asia/Ho_Chi_Minh')
    
    # Map timezone sang tên hiển thị
    timezone_display_map = {
        'Asia/Ho_Chi_Minh': 'Giờ Việt Nam',
        'America/Chicago': 'Giờ Miền Trung - Chicago', 
        'America/New_York': 'Giờ Miền Đông - New York',
        'America/Los_Angeles': 'Giờ Miền Tây - Los Angeles',
        'America/Denver': 'Giờ Miền Núi - Denver',
        'Europe/London': 'Giờ London',
        'Europe/Paris': 'Giờ Paris',
        'Asia/Tokyo': 'Giờ Nhật Bản - Tokyo',
        'Asia/Seoul': 'Giờ Hàn Quốc - Seoul',
        'Asia/Singapore': 'Giờ Singapore',
        'Australia/Sydney': 'Giờ Sydney',
        'Pacific/Auckland': 'Giờ New Zealand - Auckland',
        'UTC': 'Giờ UTC'
    }
    
    timezone_display = timezone_display_map.get(timezone, timezone)
    
    if freq == "WEEKLY":
        days_map = {
            'MO': 'thứ hai', 'TU': 'thứ ba', 'WE': 'thứ tư',
            'TH': 'thứ năm', 'FR': 'thứ sáu', 'SA': 'thứ bảy', 'SU': 'chủ nhật'
        }
        days = [days_map.get(day, day) for day in class_info.get('byday', [])]
        days_str = ', '.join(days)
        return f"Hàng tuần vào {days_str} ({timezone_display})"
    
    elif freq == "DAILY":
        return f"Hàng ngày ({timezone_display})"
    
    elif freq == "MONTHLY":
        days = class_info.get('bymonthday', [])
        days_str = ', '.join(map(str, days))
        return f"Hàng tháng vào ngày {days_str} ({timezone_display})"
    
    elif freq == "YEARLY":
        months_map = {
            1: 'tháng 1', 2: 'tháng 2', 3: 'tháng 3', 4: 'tháng 4',
            5: 'tháng 5', 6: 'tháng 6', 7: 'tháng 7', 8: 'tháng 8', 
            9: 'tháng 9', 10: 'tháng 10', 11: 'tháng 11', 12: 'tháng 12'
        }
        months = [months_map.get(month, f"tháng {month}") for month in class_info.get('bymonth', [])]
        months_str = ', '.join(months)
        days = class_info.get('bymonthday', [])
        days_str = ', '.join(map(str, days))
        return f"Hàng năm vào ngày {days_str} {months_str} ({timezone_display})"
    
    else:
        return f"Lặp lại ({timezone_display})"