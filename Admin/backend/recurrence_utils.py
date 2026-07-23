# backend/recurrence_utils.py
"""
Utility functions for handling Google Calendar recurrence rules
"""

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
