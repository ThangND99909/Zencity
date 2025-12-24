from datetime import datetime, timezone
from googleapiclient.errors import HttpError


# ==========================================================
# 🔹 Đồng bộ toàn bộ sự kiện từ Google Calendar
# ==========================================================
def refresh_events(calendar_service, CALENDARS, max_results=2500):
    """
    Lấy toàn bộ danh sách sự kiện từ cả hai calendar (odd/even).
    Giúp cập nhật lại ID mới sau khi đổi múi giờ hoặc reset chuỗi recurring.
    """
    all_events = []
    total = 0

    for calendar_id in [CALENDARS["odd"], CALENDARS["even"]]:
        try:
            print(f"🔄 Fetching events from calendar: {calendar_id}")
            page_token = None

            while True:
                response = calendar_service.events().list(
                    calendarId=calendar_id,
                    showDeleted=False,
                    singleEvents=False,
                    maxResults=max_results,
                    pageToken=page_token
                ).execute()

                events = response.get("items", [])
                for ev in events:
                    all_events.append({
                        "id": ev.get("id"),
                        "summary": ev.get("summary", ""),
                        "start": ev.get("start", {}).get("dateTime"),
                        "recurringEventId": ev.get("recurringEventId"),
                        "recurrence": ev.get("recurrence"),
                        "calendar": "EVEN" if calendar_id == CALENDARS["even"] else "ODD",
                        "timeZone": ev.get("start", {}).get("timeZone", "UTC")
                    })
                total += len(events)

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            print(f"✅ Synced {len(all_events)} events from {calendar_id}")

        except HttpError as e:
            print(f"❌ Error fetching from {calendar_id}: {e}")

    print(f"📦 Total events fetched: {total}")
    return {"total_events": total, "events": all_events}


# ==========================================================
# 🔹 Xóa cứng theo tiêu đề và thời gian gần (±2h)
# ==========================================================
def force_delete_event_by_summary_and_time(calendar_service, summary, start_dt, calendar_id, remove_extra):
    """
    Khi Google trả về lỗi 410 hoặc ID đổi sau khi đổi timezone:
    → Dò theo tiêu đề (summary) và thời gian gần với start_dt (±2h)
    → Xóa tất cả event trùng khớp
    """
    print(f"🔎 Force searching for events near {start_dt} with title '{summary}'")

    try:
        events_resp = calendar_service.events().list(
            calendarId=calendar_id,
            showDeleted=False,
            singleEvents=True,
            maxResults=2500
        ).execute()
    except Exception as e:
        print(f"❌ Error fetching events for force delete: {e}")
        return 0

    deleted_count = 0

    for ev in events_resp.get("items", []):
        ev_summary = ev.get("summary", "")
        ev_start = ev.get("start", {}).get("dateTime")
        if not ev_start:
            continue

        try:
            ev_dt = datetime.fromisoformat(ev_start.replace("Z", "+00:00")).astimezone(timezone.utc)

            # So khớp theo tên + thời gian gần nhau
            if ev_summary.strip() == summary.strip() and abs((ev_dt - start_dt).total_seconds()) <= 7200:
                ev_id = ev.get("id")
                try:
                    calendar_service.events().delete(
                        calendarId=calendar_id,
                        eventId=ev_id
                    ).execute()
                    remove_extra(ev_id)
                    deleted_count += 1
                    print(f"✅ Force-deleted event: {ev_id}")
                except Exception as del_error:
                    print(f"⚠️ Could not delete {ev_id}: {del_error}")

        except Exception as parse_error:
            print(f"⚠️ Date parse error for {ev_start}: {parse_error}")
            continue

    print(f"🧹 Force-deleted {deleted_count} events by summary/time match")
    return deleted_count
