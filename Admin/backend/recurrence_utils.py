# backend/recurrence_utils.py
"""
Utility functions for handling Google Calendar recurrence rules
"""
from log_config import make_print

print = make_print(__name__)


def _exdate_token_to_utc(token, tz=None):
    """
    Chuẩn hóa một token ngày của EXDATE về UTC 'YYYYMMDDTHHMMSSZ'.
    - token đã có hậu tố 'Z'         → coi như UTC, giữ nguyên.
    - token dạng 'YYYYMMDDTHHMMSS'   → nếu có tz thì localize→UTC, không thì coi là UTC.
    - token không parse được (vd date-only) → trả về nguyên trạng để không mất dữ liệu.
    """
    from datetime import datetime
    import pytz

    token = (token or "").strip()
    if not token:
        return None
    if token.endswith('Z'):
        return token
    if 'T' in token:
        try:
            naive = datetime.strptime(token, '%Y%m%dT%H%M%S')
        except ValueError:
            return token
        if tz is not None:
            return tz.localize(naive).astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')
        return naive.strftime('%Y%m%dT%H%M%SZ')
    # Không xác định được định dạng (vd VALUE=DATE) → giữ nguyên
    return token


def add_exdate_to_master(master_event, instance_start_str):
    """
    Google Calendar 'this' mode: Thêm EXDATE để loại trừ một occurrence khỏi chuỗi.

    Chuẩn hóa MỌI EXDATE hiện có (kể cả dạng `EXDATE;TZID=...:...`) về UTC
    ('YYYYMMDDTHHMMSSZ'), gộp thành một dòng `EXDATE:` duy nhất và luôn giữ RRULE.

    FIX M1: trước đây các EXDATE dạng TZID chỉ được in log rồi bị loại bỏ khỏi
    `updated_recurrence`; do `exdate_added` vẫn False nên hàm ghi đè bằng một EXDATE
    mới chỉ chứa occurrence hiện tại → mọi buổi đã loại trừ trước đó xuất hiện lại.
    Nay chúng được convert sang UTC và giữ lại đầy đủ.
    """
    try:
        from datetime import datetime
        import pytz

        print(f"🎯 [GOOGLE] Adding EXDATE for 'this' mode")
        print(f"🕐 Instance to exclude: {instance_start_str}")

        # Occurrence mới cần loại trừ → UTC thực sự (đổi offset nếu input có timezone)
        instance_dt = datetime.fromisoformat(instance_start_str.replace('Z', '+00:00'))
        if instance_dt.tzinfo is not None:
            new_exdate = instance_dt.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')
        else:
            new_exdate = instance_dt.strftime('%Y%m%dT%H%M%SZ')
        print(f"✅ New EXDATE (UTC): {new_exdate}")

        recurrence = master_event.get('recurrence', [])
        if not recurrence:
            print("⚠️ Master has no recurrence rules")
            return []

        rrule_lines = []
        other_lines = []
        exdates_utc = []

        for rule in recurrence:
            if rule.startswith('RRULE'):
                rrule_lines.append(rule)
            elif rule.startswith('EXDATE'):
                try:
                    header, _, value = rule.rpartition(':')
                    tz = None
                    if 'TZID=' in header:
                        tzid = header.split('TZID=')[-1].strip()
                        tz = pytz.timezone(tzid)
                        print(f"🔄 Converting TZID EXDATE ({tzid}) → UTC")
                    for token in value.split(','):
                        utc_token = _exdate_token_to_utc(token, tz)
                        if utc_token and utc_token not in exdates_utc:
                            exdates_utc.append(utc_token)
                except Exception as conv_err:
                    # Không parse được → giữ nguyên rule gốc để không mất exclusion
                    print(f"⚠️ Could not convert EXDATE '{rule}', keeping original: {conv_err}")
                    other_lines.append(rule)
            else:
                other_lines.append(rule)

        # Thêm occurrence mới (nếu chưa có)
        if new_exdate not in exdates_utc:
            exdates_utc.append(new_exdate)
            print(f"✅ Added to EXDATE: {new_exdate}")
        else:
            print(f"ℹ️ EXDATE already exists: {new_exdate}")

        updated_recurrence = list(rrule_lines)
        if exdates_utc:
            updated_recurrence.append(f'EXDATE:{",".join(exdates_utc)}')
        updated_recurrence.extend(other_lines)

        # An toàn: đảm bảo RRULE vẫn còn
        if not any(r.startswith('RRULE') for r in updated_recurrence):
            for rule in recurrence:
                if rule.startswith('RRULE'):
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
