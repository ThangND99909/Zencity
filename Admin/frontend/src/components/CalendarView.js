// frontend/src/components/CalendarView.js
import React, { useState, useEffect, useRef } from "react";
import styles from "./CalendarView.module.css";
import { parseZoomInfo } from "../utils/sanitizeDescription";
import { getEvent } from "../services/api";
import { checkScheduleConflict } from "../services/api";
import { getTimezones } from "../services/api";
import DeleteConfirmationModal from "./DeleteConfirmationModal";
import EventContextMenu from "./EventContextMenu";
import EditRecurringModal from "./EditRecurringModal";

export default function CalendarView({ events, onEventClick, onDateSelect, onCreateEvent, onDeleteEvent, calendarFilter }) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [showPopup, setShowPopup] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [showDetailPopup, setShowDetailPopup] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [newEvent, setNewEvent] = useState(null);
  const popupRef = useRef(null);
  const eventsRef = useRef(null);
  const today = new Date();

  // ✅ Thêm các state mới cho context menu và delete modal
  const [contextMenu, setContextMenu] = useState({
    visible: false,
    position: { x: 0, y: 0 },
    event: null,
    isRecurring: false
  });

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [eventToDelete, setEventToDelete] = useState(null);
  const [showEditRecurringModal, setShowEditRecurringModal] = useState(false);
  const [editRecurringOptions, setEditRecurringOptions] = useState({
    event: null,
    originalEvent: null,
    editMode: 'this'
  });


  const [myCalendars, setMyCalendars] = useState([
    { id: 1, name: "Calendar Lẻ (Giờ lẻ)", color: "#1a73e8", checked: true },
    { id: 2, name: "Calendar Chẵn (Giờ chẵn)", color: "#34a853", checked: true },
    { id: 3, name: "Other", color: "#fbbc04", checked: true },
  ]);

  const [timezoneOptions, setTimezoneOptions] = useState([
    { value: "Asia/Ho_Chi_Minh", label: "🇻🇳 Giờ Việt Nam (UTC+7)" },
    { value: "America/Chicago", label: "🇺🇸 Giờ miền Trung - Chicago (UTC-6/-5)" },
    { value: "America/New_York", label: "🇺🇸 Giờ miền Đông - New York (UTC-5/-4)" },
    { value: "America/Denver", label: "🇺🇸 Giờ miền Núi - Denver (UTC-7/-6)" },
    { value: "America/Los_Angeles", label: "🇺🇸 Giờ miền Tây - Los Angeles (UTC-8/-7)" },
    { value: "Europe/London", label: "🇬🇧 Giờ London (UTC+0/+1)" },
    { value: "Europe/Paris", label: "🇫🇷 Giờ Paris (UTC+1/+2)" },
    { value: "Europe/Berlin", label: "🇩🇪 Giờ Berlin (UTC+1/+2)" },
    { value: "Asia/Tokyo", label: "🇯🇵 Giờ Tokyo (UTC+9)" },
    { value: "Asia/Seoul", label: "🇰🇷 Giờ Seoul (UTC+9)" },
    { value: "Asia/Singapore", label: "🇸🇬 Giờ Singapore (UTC+8)" },
    { value: "Australia/Sydney", label: "🇦🇺 Giờ Sydney (UTC+10/+11)" },
    { value: "Pacific/Auckland", label: "🇳🇿 Giờ New Zealand (UTC+12/+13)" },
    { value: "UTC", label: "🌐 Giờ UTC" }
  ]);

  const [programOptions] = useState([
    { value: "", label: "-- Chọn chương trình --" },
    { value: "toán", label: "📐 Toán học" },
    { value: "vật_lý", label: "⚛️ Vật lý" },
    { value: "hóa_học", label: "🧪 Hóa học" },
    { value: "sinh_học", label: "🧬 Sinh học" },
    { value: "tiếng_anh", label: "🇬🇧 Tiếng Anh" },
    { value: "ngữ_văn", label: "📖 Ngữ văn" },
    { value: "lịch_sử", label: "🏛️ Lịch sử" },
    { value: "địa_lý", label: "🗺️ Địa lý" },
    { value: "gdcd", label: "⚖️ Giáo dục công dân" },
    { value: "tin_học", label: "💻 Tin học" },
    { value: "công_nghệ", label: "🔧 Công nghệ" },
    { value: "ielts", label: "🎯 IELTS" },
    { value: "toefl", label: "📝 TOEFL" },
    { value: "programming", label: "👨‍💻 Lập trình" },
    { value: "stem", label: "🔬 STEM" },
    { value: "khác", label: "📌 Khác" },
  ]);

  const timeSlots = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, "0")}:00`);

  // ✅ HÀM XỬ LÝ CLICK CHUỘT PHẢI - THÊM VÀO ĐÂY
  const handleEventRightClick = (event, normalizedEvent, ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    
    console.log("🖱️ Right-click on event:", normalizedEvent);
    
    // Kiểm tra xem event có lặp lại không
    const isRecurring = normalizedEvent.recurrence || 
                       normalizedEvent.recurringEventId || 
                       (normalizedEvent.recurrence && 
                       Array.isArray(normalizedEvent.recurrence) && 
                       normalizedEvent.recurrence.length > 0);
    
    setContextMenu({
      visible: true,
      position: { x: ev.clientX, y: ev.clientY },
      event: normalizedEvent,
      isRecurring: isRecurring
    });
  };

  // ✅ HÀM ĐÓNG CONTEXT MENU
  const handleCloseContextMenu = () => {
    setContextMenu({
      visible: false,
      position: { x: 0, y: 0 },
      event: null,
      isRecurring: false
    });
  };

  // ✅ HÀM XỬ LÝ DELETE TỪ CONTEXT MENU
  const handleDeleteFromContextMenu = (event) => {
    console.log("🖱️ DELETE FROM CONTEXT MENU:", {
      eventId: event.id,
      eventName: event.name,
      hasRecurrence: event.recurrence,
      hasRecurringEventId: event.recurringEventId,
      isRecurring: event.recurrence || event.recurringEventId
    });
    
    // **THAY ĐỔI: Truyền object thay vì chỉ event**
    setEventToDelete({
      ...event,
      _deleteMode: 'this'  // Mặc định, sẽ được update bởi modal
    });
    setShowDeleteModal(true);
    handleCloseContextMenu();
  };

  // Và sửa handleConfirmDelete:

  const handleConfirmDelete = async (deleteMode = 'this') => {
    if (!eventToDelete || !eventToDelete.id) {
      alert("Không thể xóa: thiếu ID sự kiện");
      setShowDeleteModal(false);
      return;
    }
    
    try {
      // **THAY ĐỔI: Tạo object delete request với mode**
      const deleteRequest = {
        ...eventToDelete,
        deleteMode: deleteMode  // Thêm deleteMode vào object
      };
      
      console.log("📦 FINAL DELETE REQUEST OBJECT:", deleteRequest);
      
      // Gọi hàm xóa từ props
      await onDeleteEvent?.(deleteRequest);
      
      setShowDeleteModal(false);
      setEventToDelete(null);
      
      alert("✅ Đã xóa sự kiện thành công!");
      
    } catch (error) {
      console.error("❌ Error deleting event:", error);
      alert("❌ Lỗi khi xóa sự kiện: " + error.message);
      setShowDeleteModal(false);
    }
  };

  const handleEditEvent = async (event) => {
    if (!event.id) {
      alert("Không thể chỉnh sửa: thiếu ID sự kiện");
      return;
    }
    
    try {
      
      
      const recurrenceData = await parseRecurrenceFromEvent(event);
      
      console.log("📈 Parsed recurrence data:", recurrenceData);
      
      let instanceIndex = 1;
      let adjustedRepeatCount = recurrenceData.repeatCount;
      
      // ✅ TÍNH INSTANCE INDEX NẾU LÀ INSTANCE
      if (event._is_instance || event.recurringEventId) {
        console.log("🔄 Calculating for INSTANCE");
        
        const masterEventId = event._master_event_id || event.recurringEventId;
        
        // **LẤY MASTER EVENT TỪ CACHE HOẶC FETCH**
        let masterEvent = masterEventsCache[masterEventId];
        if (!masterEvent) {
          try {
            masterEvent = await getEvent(masterEventId);
            if (masterEvent) {
              setMasterEventsCache(prev => ({
                ...prev,
                [masterEventId]: masterEvent
              }));
            }
          } catch (error) {
            console.error("❌ Failed to fetch master event:", error);
          }
        }
        
        if (masterEvent && recurrenceData.recurrenceType) {
          // **TÍNH INSTANCE INDEX CHÍNH XÁC**
          instanceIndex = calculateInstanceIndex(event, masterEvent, recurrenceData.recurrenceType);
          
          
          if (instanceIndex === 1) {
            console.warn("⚠️ Instance index calculated as 1 - might be incorrect");
            console.log("   Let's manually check dates...");
            
            // Manual calculation cho DAILY
            const instanceStart = new Date(event.start?.dateTime || event.start);
            const masterStart = new Date(masterEvent.start?.dateTime || masterEvent.start);
            
            console.log("   - Master start:", masterStart.toISOString());
            console.log("   - Instance start:", instanceStart.toISOString());
            
            const dayDiff = Math.floor((instanceStart - masterStart) / (1000 * 60 * 60 * 24));
            console.log("   - Day difference:", dayDiff);
            
            // Nếu là DAILY và cách nhau 2 ngày → instance thứ 3
            if (recurrenceData.recurrenceType === 'DAILY' && dayDiff === 2) {
              instanceIndex = 3;
              console.log("   ✅ Corrected instance index to 3");
            }
          }
          
          // ✅ CÔNG THỨC QUAN TRỌNG:
          // Số events còn lại = tổng - (instanceIndex - 1)
          adjustedRepeatCount = Math.max(1, recurrenceData.repeatCount - (instanceIndex - 1));
          
          
        } else {
          console.warn("⚠️ Could not find master event or recurrence type");
          // **FALLBACK: Nếu không tìm được master, ước tính dựa trên ID**
          // Instance ID thường có format: masterId_YYYYMMDDTHHMMSSZ
          // Nếu edit instance thứ 3 trong chuỗi 4, còn lại 2 events
          adjustedRepeatCount = 2; // Giả sử instance thứ 3 → còn 2 events
          instanceIndex = 3; // Giả sử là instance thứ 3
          console.log(`⚠️ Using fallback values: index=${instanceIndex}, remaining=${adjustedRepeatCount}`);
        }
      } else {
        console.log("📌 Editing MASTER or REGULAR event");
      }
      
      const editEventData = {
        id: event.id,
        title: event.name,
        class_name: event.class_name || event.classname || "",
        teacher: event.teacher,
        program: event.program,
        zoom_link: event.zoom,
        meeting_id: event.meeting_id || "",
        passcode: event.passcode || "",
        recurrence: recurrenceData.recurrenceType,
        repeat_count: adjustedRepeatCount, // ✅ DÙNG SỐ ĐÃ ĐIỀU CHỈNH
        byday: recurrenceData.byday,
        bymonthday: recurrenceData.bymonthday,
        bymonth: recurrenceData.bymonth,
        start: formatForInput(event.start?.dateTime || event.start),
        end: formatForInput(event.end?.dateTime || event.end),
        timezone: event.timezone || "Asia/Ho_Chi_Minh",
        recurrence_description: event.recurrence_description || "",
        calendar_source: event.calendar_source,
        is_recurring: event.recurrence || event.recurringEventId,
        recurring_event_id: event.recurringEventId,
        // ✅ THÊM THÔNG TIN QUAN TRỌNG CHO BACKEND
        _is_instance: event._is_instance || !!event.recurringEventId,
        _instance_index: instanceIndex,
        _remaining_count: adjustedRepeatCount,
        _estimated_instance_position: instanceIndex // Cho backend biết đây là instance thứ mấy
      };
      
      
      
      // Nếu là sự kiện lặp lại, hiển thị modal chọn edit mode
      if (event.recurrence || event.recurringEventId) {
        console.log("🔄 Recurring event edit detected, showing mode selector");
        setEditRecurringOptions({
          event: editEventData,
          originalEvent: event,
          editMode: 'this'
        });
        setShowEditRecurringModal(true);
      } else {
        // Non-recurring event
        setNewEvent(editEventData);
        setEditingEvent(event);
        setShowDetailPopup(false);
        setShowPopup(true);
      }
      
    } catch (error) {
      console.error("❌ Error preparing edit:", error);
      alert("Không thể chuẩn bị dữ liệu chỉnh sửa: " + error.message);
    }
  };

  

  const handleConfirmEditMode = (editMode) => {
    
    const { event, originalEvent } = editRecurringOptions;
    
    if (!event) {
      alert("Không có dữ liệu sự kiện để chỉnh sửa");
      return;
    }

    // 1. TÍNH TOÁN ĐÚNG repeat_count CHO TỪNG MODE
    let finalRepeatCount = event.repeat_count || 1;
    
    
    if (editMode === 'following' && originalEvent?.recurringEventId) {
      // MODE "FOLLOWING": DÙNG remaining_count
      finalRepeatCount = event._remaining_count || event.repeat_count || 1;
      console.log("🎯 Mode 'following' - Using remaining count:", finalRepeatCount);
    } else {
      finalRepeatCount = 1;
      console.log("📌 Mode '" + editMode + "' - Keeping original repeat_count:", finalRepeatCount);
    }

    const eventTimezone = event.timezone || "Asia/Ho_Chi_Minh";

    // 2. TẠO EVENT DATA VỚI METADATA ĐÚNG
    const eventWithEditMode = {
      ...event,
      editMode: editMode,
      repeat_count: finalRepeatCount,
      timezone: eventTimezone,
      _editModeConfirmed: true,
      is_recurring_instance: !!originalEvent?.recurringEventId,
      master_event_id: originalEvent?.recurringEventId || originalEvent?.id,
      
      // METADATA QUAN TRỌNG CHO BACKEND
      _is_editing_from_instance: !!originalEvent?.recurringEventId,
      _instance_index: event._instance_index || 1,
      _remaining_count: event._remaining_count || event.repeat_count,

      
      // ĐẢM BẢO CÁC TRƯỜNG RECURRENCE KHÔNG BỊ MẤT
      recurrence: event.recurrence,
      byday: event.byday || [],
      bymonthday: event.bymonthday || [],
      bymonth: event.bymonth || [],
      
      
    };

    

    // 3. ĐÓNG MODAL VÀ MỞ FORM CHỈNH SỬA
    setNewEvent(eventWithEditMode);
    setEditingEvent(originalEvent);
    setShowEditRecurringModal(false);
    setShowDetailPopup(false);
    setShowPopup(true);
    
    console.log("📤 Opening edit form with mode:", editMode);
  };

  // ✅ HÀM XỬ LÝ EDIT TỪ CONTEXT MENU
  const handleEditFromContextMenu = async (event) => {
    handleEditEvent(event);
    
  };

  // ✅ HÀM XỬ LÝ VIEW DETAILS TỪ CONTEXT MENU
  const handleViewDetailsFromContextMenu = (event) => {
    setSelectedEvent(event);
    setShowDetailPopup(true);
  };

  
  useEffect(() => {
    const fetchTimezones = async () => {
      try {
        const timezonesData = await getTimezones();
        if (timezonesData && timezonesData.timezones) {
          setTimezoneOptions(timezonesData.timezones);
        }
      } catch (error) {
        console.error("❌ Failed to fetch timezones, using default:", error);
      }
    };
    
    fetchTimezones();
  }, []);

  // ✅ FILTER EVENTS DỰA TRÊN CALENDAR FILTER
  const filteredEvents = events.filter(event => {
    if (calendarFilter === 'both') return true;
    if (calendarFilter === 'odd') return event._calendar_source === 'odd';
    if (calendarFilter === 'even') return event._calendar_source === 'even';
    return true;
  });

  const dailyEvents = filteredEvents.filter((e) => {
    const start = new Date(e.start.dateTime || e.start);
    const end = new Date(e.end.dateTime || e.end);
    const dayStart = new Date(selectedDate);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = new Date(selectedDate);
    dayEnd.setHours(23, 59, 59, 999);
    return end > dayStart && start < dayEnd;
  });

  const layoutEvents = (events) => {
    const dayStart = new Date(selectedDate);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = new Date(selectedDate);
    dayEnd.setHours(23, 59, 59, 999);

    const sorted = events
      .map((e) => {
        const start = new Date(e.start.dateTime || e.start);
        const end = new Date(e.end.dateTime || e.end);
        const displayStart = start < dayStart ? dayStart : start;
        const displayEnd = end > dayEnd ? dayEnd : end;
        return {
          ...e,
          startMins: displayStart.getHours() * 60 + displayStart.getMinutes(),
          endMins: displayEnd.getHours() * 60 + displayEnd.getMinutes(),
        };
      })
      .sort((a, b) => a.startMins - b.startMins);

    const positioned = [];
    for (let i = 0; i < sorted.length; i++) {
      const event = sorted[i];
      const overlapGroup = sorted.filter(
        (e) => e.startMins < event.endMins && e.endMins > event.startMins
      );
      const index = overlapGroup.findIndex((e) => e === event);
      const width = 100 / overlapGroup.length;
      const left = index * width;
      positioned.push({ ...event, width: `${width}%`, left: `${left}%` });
    }
    return positioned;
  };

  const layoutedEvents = layoutEvents(dailyEvents);

  const changeDate = (offset) => {
    const newDate = new Date(selectedDate);
    newDate.setDate(selectedDate.getDate() + offset);
    setSelectedDate(newDate);
  };

  const formatHeaderDate = (date) =>
    date.toLocaleDateString("vi-VN", { day: "numeric", month: "long", year: "numeric" });

  const getMiniCalendarDays = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startDay = firstDay.getDay();

    const days = [];
    const prevMonthLastDay = new Date(year, month, 0).getDate();
    for (let i = startDay - 1; i >= 0; i--) {
      days.push({ date: new Date(year, month - 1, prevMonthLastDay - i), isCurrent: false });
    }
    for (let i = 1; i <= daysInMonth; i++) {
      days.push({ date: new Date(year, month, i), isCurrent: true });
    }
    const totalCells = 42;
    const remaining = totalCells - days.length;
    for (let i = 1; i <= remaining; i++) {
      days.push({ date: new Date(year, month + 1, i), isCurrent: false });
    }
    return days;
  };

  const miniDays = getMiniCalendarDays();

  const normalizeEvent = (event) => {
    const raw = event.description || "";
    const { zoomLink, teacher, program, classname, meetingId, passcode } = parseZoomInfo(raw);
    const eventId = event.id || event._id || event.eventId || event.class_id;

    console.log("🔍 NORMALIZE EVENT - TYPE CHECK:", {
      eventId,
      isInstance: event._is_instance,
      isMaster: event._is_master,
      hasRecurrence: !!event.recurrence,
      recurringEventId: event.recurringEventId
    });

    // ✅ ƯU TIÊN: Nếu là instance, dùng data từ instance
    // Nếu là master, dùng data từ master
    const eventTimezone = event.start?.timeZone || event.end?.timeZone || "Asia/Ho_Chi_Minh";
    
    // ✅ XÁC ĐỊNH CALENDAR TYPE VÀ MÀU SẮC
    const calendarSource = event._calendar_source || 'odd';
    const calendarName = calendarSource === 'odd' ? '📘 Calendar Lẻ' : '📗 Calendar Chẵn';
    const calendarColor = calendarSource === 'odd' ? '#1a73e8' : '#34a853';
    const calendarBadge = calendarSource === 'odd' ? '📘' : '📗';

    return {
      ...event,
      id: eventId,
      name: event.summary || event.name || "Không có tên",
      class_name: event.classname || event.class_name || classname || "",
      teacher: event.teacher || teacher || event.instructor || "Chưa có GV",
      program: event.program || program || event.course || "Chưa có môn",
      zoom: event.zoom_link || event.zoom || zoomLink || event.meeting_url || event.location || "",
      meeting_id: event.meeting_id || meetingId || "",
      passcode: event.passcode || passcode || "",
      timezone: eventTimezone,
      recurrence: event.recurrence,
      repeat_count: event.repeat_count || 1,
      byday: event.byday || [],
      bymonthday: event.bymonthday || [],
      bymonth: event.bymonth || [],
      // ✅ THÊM CALENDAR INFO
      calendar_source: calendarSource,
      calendar_name: calendarName,
      calendar_color: calendarColor,
      calendar_badge: calendarBadge,
      // ✅ THÊM INSTANCE INFO
      is_instance: event._is_instance || false,
      is_master: event._is_master || false,
      master_event_id: event._master_event_id || event.recurringEventId
    };
  };

  // ✅ THÊM HÀM KIỂM TRA GIỜ CHẴN LẺ ĐỂ HIỂN THỊ THÔNG BÁO
  const checkEvenOddHour = (datetimeString) => {
    if (!datetimeString) return 'unknown';
    try {
      const dt = new Date(datetimeString);
      const hour = dt.getHours();
      return hour % 2 === 0 ? 'even' : 'odd';
    } catch {
      return 'unknown';
    }
  };

  const parseRecurrenceRule = (ruleString) => {
    if (!ruleString) {
      return { recurrenceType: "", repeatCount: 1, byday: [], bymonthday: [], bymonth: [] };
    }
    
    let recurrenceType = "";
    let repeatCount = 1;
    let byday = [];
    let bymonthday = [];
    let bymonth = [];

    const freqMatch = ruleString.match(/FREQ=(DAILY|WEEKLY|MONTHLY|YEARLY)/i);
    recurrenceType = freqMatch ? freqMatch[1] : "";
    
    const countMatch = ruleString.match(/COUNT=(\d+)/i);
    repeatCount = countMatch ? parseInt(countMatch[1]) : 1;

    const bydayMatch = ruleString.match(/BYDAY=([A-Z,]+)/i);
    byday = bydayMatch ? bydayMatch[1].split(",") : [];

    const bymonthdayMatch = ruleString.match(/BYMONTHDAY=([\d,-]+)/i);
    bymonthday = bymonthdayMatch 
      ? bymonthdayMatch[1].split(",").map(Number).filter(n => !isNaN(n))
      : [];

    const bymonthMatch = ruleString.match(/BYMONTH=([\d,]+)/i);
    bymonth = bymonthMatch 
      ? bymonthMatch[1].split(",").map(Number).filter(n => !isNaN(n))
      : [];

    return { recurrenceType, repeatCount, byday, bymonthday, bymonth };
  };

  // ✅ THÊM HÀM TÍNH INSTANCE INDEX Ở ĐÂY
  const calculateInstanceIndex = (instanceEvent, masterEvent, recurrenceType) => {
    if (!instanceEvent || !masterEvent) {
      console.error("❌ Missing event data for instance calculation");
      return 1;
    }
    
    try {
      const instanceStart = new Date(instanceEvent.start?.dateTime || instanceEvent.start);
      const masterStart = new Date(masterEvent.start?.dateTime || masterEvent.start);
      
      console.log("🔢 ========== INSTANCE INDEX CALCULATION ==========");
      console.log("  - Master start:", masterStart.toISOString(), `(${masterStart.toLocaleString('vi-VN')})`);
      console.log("  - Instance start:", instanceStart.toISOString(), `(${instanceStart.toLocaleString('vi-VN')})`);
      console.log("  - Recurrence type:", recurrenceType);
      
      // Đảm bảo cả 2 đều ở UTC để so sánh
      const masterTime = masterStart.getTime();
      const instanceTime = instanceStart.getTime();
      
      console.log("  - Master timestamp:", masterTime);
      console.log("  - Instance timestamp:", instanceTime);
      console.log("  - Time difference (ms):", instanceTime - masterTime);
      console.log("  - Time difference (hours):", (instanceTime - masterTime) / (1000 * 60 * 60));
      
      let index = 1;
      
      if (recurrenceType === 'DAILY') {
        // Tính số ngày chênh lệch chính xác
        const dayMs = 24 * 60 * 60 * 1000;
        const daysDiff = Math.round((instanceTime - masterTime) / dayMs);
        index = Math.max(1, daysDiff + 1);
        console.log(`  - Days difference: ${daysDiff} → Instance #${index}`);
        
        // **KIỂM TRA THÊM**: In ra tất cả các ngày để debug
        console.log("  📅 Debug - All expected days:");
        for (let i = 0; i < 10; i++) {
          const expectedDate = new Date(masterTime + (i * dayMs));
          console.log(`    Day ${i + 1}: ${expectedDate.toISOString()} (${expectedDate.toLocaleDateString('vi-VN')})`);
        }
        
      } else if (recurrenceType === 'WEEKLY') {
        const weekMs = 7 * 24 * 60 * 60 * 1000;
        const weeksDiff = Math.round((instanceTime - masterTime) / weekMs);
        index = Math.max(1, weeksDiff + 1);
        console.log(`  - Weeks difference: ${weeksDiff} → Instance #${index}`);
        
      } else if (recurrenceType === 'MONTHLY') {
        const yearDiff = instanceStart.getFullYear() - masterStart.getFullYear();
        const monthDiff = instanceStart.getMonth() - masterStart.getMonth();
        const totalMonths = (yearDiff * 12) + monthDiff;
        index = Math.max(1, totalMonths + 1);
        console.log(`  - Months difference: ${totalMonths} → Instance #${index}`);
        
      } else {
        console.warn(`⚠️ Unknown recurrence type: ${recurrenceType}, using index 1`);
        index = 1;
      }
      
      console.log(`✅ Final instance index: ${index}`);
      return index;
      
    } catch (e) {
      console.error("❌ Error calculating instance index:", e);
      return 1;
    }
  };


  const [masterEventsCache, setMasterEventsCache] = useState({});

  const parseRecurrenceFromEvent = async (cls) => {
    console.log("🔍 [RECURRENCE DEBUG] Checking event:", {
      id: cls.id,
      summary: cls.summary,
      hasDirectRecurrence: !!cls.recurrence,
      directRecurrence: cls.recurrence,
      isInstance: !!cls.recurringEventId,
      recurringEventId: cls.recurringEventId,
      _is_instance: cls._is_instance,
      _is_master: cls._is_master
    });

    // TRƯỜNG HỢP 1: Event có recurrence trực tiếp
    if (cls.recurrence && Array.isArray(cls.recurrence) && cls.recurrence.length > 0) {
      const ruleString = cls.recurrence[0];
      console.log("✅ Using direct recurrence rule from MASTER event");
      return parseRecurrenceRule(ruleString);
    }

    // TRƯỜNG HỢP 2: Event là instance
    if (cls.recurringEventId || cls._is_instance) {
      console.log("🔄 This is a RECURRING INSTANCE");
      console.log("   - Instance ID:", cls.id);
      console.log("   - Master ID:", cls.recurringEventId || cls._master_event_id);
      
      const masterEventId = cls.recurringEventId || cls._master_event_id;
      
      if (!masterEventId) {
        console.error("❌ No master event ID found for instance");
        return { recurrenceType: "", repeatCount: 1, byday: [], bymonthday: [], bymonth: [] };
      }
      
      // **KIỂM TRA CACHE TRƯỚC**
      if (masterEventsCache[masterEventId]) {
        console.log("✅ Using cached master event");
        const masterEvent = masterEventsCache[masterEventId];
        if (masterEvent.recurrence) {
          const ruleString = masterEvent.recurrence[0];
          return parseRecurrenceRule(ruleString);
        }
      }
      
      // **TÌM TRONG LOCAL EVENTS**
      const localMaster = events.find(event => event.id === masterEventId);
      if (localMaster && localMaster.recurrence) {
        console.log("✅ Found master event in local events");
        // Lưu vào cache
        setMasterEventsCache(prev => ({
          ...prev,
          [masterEventId]: localMaster
        }));
        const ruleString = localMaster.recurrence[0];
        return parseRecurrenceRule(ruleString);
      }
      
      // **FETCH TỪ API**
      console.log("🔄 Fetching master event from API...");
      try {
        const masterEvent = await getEvent(masterEventId);
        if (masterEvent && masterEvent.recurrence) {
          console.log("✅ Fetched master event from API");
          // Lưu vào cache
          setMasterEventsCache(prev => ({
            ...prev,
            [masterEventId]: masterEvent
          }));
          const ruleString = masterEvent.recurrence[0];
          return parseRecurrenceRule(ruleString);
        }
      } catch (error) {
        console.error("❌ Failed to fetch master event:", error);
      }
      
      console.log("❌ Could not get recurrence data for instance");
    }

    console.log("❌ No recurrence data available");
    return { recurrenceType: "", repeatCount: 1, byday: [], bymonthday: [], bymonth: [] };
  };

  const prepareEditData = async (cls) => {
    const { zoomLink, meetingId, passcode, program, teacher, classname } = 
      parseZoomInfo(cls.description || "");

    const recurrenceData = await parseRecurrenceFromEvent(cls);

    return {
      id: cls.id,
      name: cls.summary || "",
      classname: cls.classname || classname || "",
      teacher: cls.teacher || teacher || "",
      zoom_link: cls.zoom_link || cls.location || zoomLink || "",
      meeting_id: cls.meeting_id || meetingId || "",
      passcode: cls.passcode || passcode || "",
      program: cls.program || program || "",
      start: cls.start?.dateTime || "",
      end: cls.end?.dateTime || "",
      recurrence: recurrenceData.recurrenceType,
      repeat_count: recurrenceData.repeatCount,
      byday: recurrenceData.byday,
      bymonthday: recurrenceData.bymonthday,
      bymonth: recurrenceData.bymonth,
      timezone: cls.timezone || "Asia/Ho_Chi_Minh",
      recurrence_description: cls.recurrence_description || "",
      calendar_source: cls.calendar_source || 'odd',
    };
  };

  const findMasterEvent = (recurringEventId) => {
    if (!recurringEventId) {
      console.error("❌ No recurringEventId provided");
      return null;
    }
    
    console.log("🔍 Looking for master event:", recurringEventId);
    
    // Tìm trong danh sách events hiện tại
    const master = events.find(event => {
      const isMaster = event.id === recurringEventId;
      if (isMaster) {
        console.log("✅ Found master in current events:", {
          id: event.id,
          summary: event.summary,
          hasRecurrence: !!event.recurrence
        });
      }
      return isMaster;
    });
    
    if (!master) {
      console.warn("⚠️ Master event not found in current events");
    }
    
    return master;
  };

  const [timePosition, setTimePosition] = useState(null);
  useEffect(() => {
    const updateTimeLine = () => {
      const now = new Date();
      if (selectedDate.toDateString() !== today.toDateString()) {
        setTimePosition(null);
        return;
      }
      const pos = now.getHours() * 60 + now.getMinutes();
      setTimePosition(pos);
    };
    updateTimeLine();
    const timer = setInterval(updateTimeLine, 60000);
    return () => clearInterval(timer);
  }, [selectedDate]);

  const formatForInput = (date) => {
    if (!date) return "";
    const localDate = new Date(date);
    const year = localDate.getFullYear();
    const month = String(localDate.getMonth() + 1).padStart(2, '0');
    const day = String(localDate.getDate()).padStart(2, '0');
    const hours = String(localDate.getHours()).padStart(2, '0');
    const minutes = String(localDate.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };

  const formatForBackend = (datetimeLocal, timezone = "Asia/Ho_Chi_Minh") => {
    if (!datetimeLocal) return "";
    
    console.log("🔧 formatForBackend INPUT:", datetimeLocal, "Timezone:", timezone);
    
    const localDate = new Date(datetimeLocal);
    return localDate.toISOString();
  };

  const createConflictMessage = (conflictResult, currentTeacher) => {
    const checkType = conflictResult.check_type || 'ai_full';
    const checkTypeText = {
      'ai_suggestions': 'AI Đề Xuất Thông Minh',
      'traditional_fast': 'Kiểm Tra Nhanh',
      'ai_full': 'AI Phân Tích'
    }[checkType] || 'AI Phân Tích';
    
    let message = `🤖 KIỂM TRA XUNG ĐỘT (${checkTypeText})\n\n`;
    
    if (conflictResult.ai_analysis) {
      message += `📊 ${conflictResult.ai_analysis}\n\n`;
    }
    
    if (conflictResult.has_conflict && conflictResult.conflicts.length > 0) {
      message += `⚠️ Giáo viên "${currentTeacher}" có ${conflictResult.conflicts.length} xung đột:\n\n`;
      
      conflictResult.conflicts.forEach((conflict, index) => {
        const startTime = new Date(conflict.event_start).toLocaleString('vi-VN');
        const endTime = new Date(conflict.event_end).toLocaleString('vi-VN');
        
        message += `🚨 ${conflict.event_summary}\n`;
        message += `   👨‍🏫 GV: ${conflict.event_teacher}\n`;
        message += `   ⏰ ${startTime} - ${endTime}\n\n`;
      });
    } else {
      message += `✅ Không có xung đột trực tiếp với giáo viên "${currentTeacher}"\n\n`;
    }
    
    if (conflictResult.suggestions && conflictResult.suggestions.length > 0) {
      message += `💡 ĐỀ XUẤT THỜI GIAN THAY THẾ:\n`;
      conflictResult.suggestions.forEach((suggestion, index) => {
        const startTime = new Date(suggestion.start).toLocaleString('vi-VN');
        message += `   ${index + 1}. ${suggestion.description || 'Khung giờ phù hợp'}\n`;
        message += `      🕒 ${startTime}\n`;
        message += `\n`;
      });
    }
    
    if (conflictResult.has_conflict) {
      message += `Bạn muốn:\n`;
      message += `• "OK" - VẪN tạo sự kiện (có xung đột)\n`;
      message += `• "Cancel" - HỦY và chọn thời gian khác\n`;
      
      if (conflictResult.suggestions && conflictResult.suggestions.length > 0) {
        message += `• Hoặc nhập số (1, 2) để dùng đề xuất trên`;
      }
    } else {
      message += `✅ Không có xung đột. "OK" để tiếp tục tạo sự kiện.`;
    }
    
    return message;
  };

  const openPopup = (start, end) => {
    const defaultEnd = end > start ? end : new Date(start.getTime() + 60 * 60 * 1000);
    
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    let defaultTimezone = "Asia/Ho_Chi_Minh";
    
    const commonTimezones = [
      "America/Chicago", "America/New_York", "America/Los_Angeles",
      "Europe/London", "Europe/Paris", "Asia/Tokyo", "Australia/Sydney"
    ];
    
    if (commonTimezones.includes(userTimezone)) {
      defaultTimezone = userTimezone;
    }
    
    console.log(`🕐 User timezone: ${userTimezone}, using: ${defaultTimezone}`);
    
    // ✅ THÊM THÔNG BÁO VỀ CALENDAR SẼ ĐƯỢC CHỌN
    const hourType = checkEvenOddHour(start.toISOString());
    const targetCalendar = hourType === 'even' ? '📗 Calendar Chẵn' : '📘 Calendar Lẻ';
    
    const defaultEvent = {
      title: "",
      class_name: "",
      teacher: "",
      program: "",
      zoom_link: "",
      meeting_id: "",
      passcode: "",
      start: formatForInput(start),
      end: formatForInput(defaultEnd),
      recurrence: "",
      repeat_count: 1,
      byday: [],
      bymonthday: [],
      bymonth: [],
      timezone: defaultTimezone,
      recurrence_description: "",
      // ✅ THÊM THÔNG TIN CALENDAR
      hour_type: hourType,
      target_calendar: targetCalendar,
    };

    setNewEvent(defaultEvent);
    setEditingEvent(null);
    setShowPopup(true);
    
    // ✅ HIỂN THỊ THÔNG BÁO VỀ CALENDAR
    setTimeout(() => {
      alert(`📅 Lưu ý:\nSự kiện bắt đầu lúc ${start.getHours()}h sẽ được lưu vào:\n${targetCalendar}\n\nGiờ chẵn → 📗 Calendar Chẵn\nGiờ lẻ → 📘 Calendar Lẻ`);
    }, 100);
  };

  const handleSave = async () => {
    console.log("🔥 [GOOGLE] SAVE EVENT - Edit mode:", newEvent.editMode);
    console.log("📊 newEvent object:", {
      editMode: newEvent?.editMode,
      id: newEvent?.id,
      keys: Object.keys(newEvent || {}),
      hasEditMode: 'editMode' in (newEvent || {})
    });

    const isSingleEvent = !editingEvent?.recurrence && !editingEvent?.recurringEventId;
    const wantsRecurrence = newEvent?.recurrence && newEvent.recurrence.trim() !== "";
    // Nếu không có editMode, dùng mặc định 'this'
    let finalEditMode = newEvent?.editMode || 'this';
    console.log("🎯 FINAL EDIT MODE FOR SAVE:", finalEditMode);
  
    if (isSingleEvent && wantsRecurrence) {
      // ⚠️ **ĐÂY LÀ KEY: DÙNG 'all' CHO SINGLE→RECURRING**
      finalEditMode = 'all';
      console.log("🔄 Single → Recurring: using edit_mode='all'");
    }
    
    console.log("🎯 FINAL EDIT MODE:", finalEditMode);
    // ========== GOOGLE CALENDAR LOGIC ==========
    // If editing instance with 'this' mode, REMOVE recurrence
    if (newEvent.id && newEvent.id.includes('_') && newEvent.editMode === 'this') {
      console.log("🔄 'this' mode on instance - removing recurrence");
      
      const updatedEvent = { ...newEvent };
      
      // Remove all recurrence fields
      delete updatedEvent.recurrence;
      delete updatedEvent.repeat_count;
      delete updatedEvent.byday;
      delete updatedEvent.bymonthday;
      delete updatedEvent.bymonth;
      delete updatedEvent.rrule;
      delete updatedEvent.recurrence_description;
      
      setNewEvent(updatedEvent);
    }
    console.log("🔥 DEBUG handleSave - CURRENT TIMEZONE:", {
      timezone: newEvent?.timezone,
      fullState: newEvent
    });
    
    if (!newEvent.title) {
      alert("Vui lòng nhập tiêu đề!");
      return;
    }
    
    // ✅ KIỂM TRA GIỜ CHẴN LẺ TRƯỚC KHI LƯU
    const hourType = checkEvenOddHour(newEvent.start);
    const targetCalendar = hourType === 'even' ? '📗 Calendar Chẵn' : '📘 Calendar Lẻ';
    
    alert(`🎯 Sự kiện sẽ được lưu vào: ${targetCalendar}\nGiờ bắt đầu: ${new Date(newEvent.start).getHours()}h (${hourType === 'even' ? 'chẵn' : 'lẻ'})`);
    
    // 🔍 KIỂM TRA XUNG ĐỘT TRƯỚC KHI LƯU
    if (newEvent.teacher && newEvent.teacher.trim() !== "") {
      try {
        console.log("🛡️ Checking for schedule conflicts...");
        
        const conflictResult = await checkScheduleConflict(
          newEvent.teacher,
          formatForBackend(newEvent.start, newEvent.timezone),
          formatForBackend(newEvent.end, newEvent.timezone),
          newEvent.id
        );

        // XỬ LÝ KẾT QUẢ AI
        if (conflictResult.has_conflict) {
          const conflictMessage = createConflictMessage(conflictResult, newEvent.teacher);
          
          if (conflictResult.suggestions && conflictResult.suggestions.length > 0) {
            const userChoice = prompt(conflictMessage);
            
            if (userChoice === null) {
              alert("🚫 Đã hủy tạo lịch do trùng lịch giáo viên");
              return; 
            } else if (userChoice === '1' || userChoice === '2') {
              const suggestionIndex = parseInt(userChoice) - 1;
              const selectedSuggestion = conflictResult.suggestions[suggestionIndex];
              
              setNewEvent(prev => ({
                ...prev,
                start: formatForInput(selectedSuggestion.start),
                end: formatForInput(selectedSuggestion.end)
              }));
              
              alert(`✅ Đã chuyển sang thời gian: ${new Date(selectedSuggestion.start).toLocaleString('vi-VN')}`);
              return;
            } else if (userChoice === '') {
              alert("⚠️ Cảnh báo: Bạn vẫn tạo lịch dù có xung đột!");
              console.log("⚠️ User confirmed to create despite conflict");
            } else {
              alert("❌ Lựa chọn không hợp lệ. Vui lòng thử lại.");
              return;
            }
          } else {
            const userConfirmed = window.confirm(conflictMessage + "\n\nBấm OK để VẪN TẠO, Cancel để HỦY");
            
            if (!userConfirmed) {
              alert("🚫 Đã hủy tạo lịch do trùng lịch giáo viên");
              return;
            }
            alert("⚠️ Cảnh báo: Bạn vẫn tạo lịch dù có xung đột!");
          }
        } else {
          if (conflictResult.ai_analysis) {
            alert(`🤖 AI Phân tích:\n${conflictResult.ai_analysis}\n\n✅ Không có xung đột!`);
          }
        }
      } catch (error) {
        alert(`❌ LỖI CHECK CONFLICT:\n\nStatus: ${error.response?.status}\nMessage: ${error.response?.data?.detail || error.message}`);
        console.error("❌ Error during conflict check:", error.response?.data || error);
      }
    }

    const startTime = new Date(newEvent.start);
    const endTime = new Date(newEvent.end);
    
    if (endTime <= startTime) {
      alert("Thời gian kết thúc phải LỚN HƠN thời gian bắt đầu!");
      return;
    }

    if (newEvent.recurrence && newEvent.recurrence.trim() !== "") {
      if (newEvent.recurrence === "WEEKLY" && (!newEvent.byday || newEvent.byday.length === 0)) {
        alert("Vui lòng chọn ít nhất một ngày trong tuần cho lịch lặp hàng tuần!");
        return;
      }

      if (newEvent.recurrence === "MONTHLY" && (!newEvent.bymonthday || newEvent.bymonthday.length === 0)) {
        alert("Vui lòng nhập ít nhất một ngày trong tháng cho lịch lặp hàng tháng!");
        return;
      }

      if (newEvent.recurrence === "YEARLY") {
        if (!newEvent.bymonth || newEvent.bymonth.length === 0) {
          alert("Vui lòng nhập ít nhất một tháng cho lịch lặp hàng năm!");
          return;
        }
        if (!newEvent.bymonthday || newEvent.bymonthday.length === 0) {
          alert("Vui lòng nhập ít nhất một ngày cho lịch lặp hàng năm!");
          return;
        }
      }
    }

    console.log("🔥 DEBUG FRONTEND BEFORE UPDATE:");
    console.log(" - newEvent.timezone:", newEvent.timezone);
    console.log(" - selected timezone:", timezoneOptions.find(tz => tz.value === newEvent.timezone)?.label);

    const finalTimezone = newEvent?.timezone || "Asia/Ho_Chi_Minh";
  
    console.log("🔥 FINAL TIMEZONE FOR SAVE:", finalTimezone);
    const eventData = {
      ...(newEvent.id && { id: newEvent.id }),
      name: newEvent.title,
      classname: newEvent.class_name || "",
      teacher: newEvent.teacher,
      program: newEvent.program,
      zoom_link: newEvent.zoom_link,
      meeting_id: newEvent.meeting_id,
      passcode: newEvent.passcode,
      // Only add recurrence if not 'this' mode on instance
      ...(newEvent.editMode !== 'this' || !newEvent.id?.includes('_') ? {
        recurrence: newEvent.recurrence || "",
        repeat_count: newEvent.repeat_count || 1,
        byday: newEvent.byday || [],
        bymonthday: newEvent.bymonthday || [],
        bymonth: newEvent.bymonth || [],
      } : {}),
      ...(newEvent.recurrence && {
        recurrence: newEvent.recurrence,
        repeat_count: newEvent.repeat_count || 1,
        byday: newEvent.byday || [],
        bymonthday: newEvent.bymonthday || [],
        bymonth: newEvent.bymonth || [],
      }),
      start: formatForBackend(newEvent.start, finalTimezone),
      end: formatForBackend(newEvent.end, finalTimezone),
      timezone: finalTimezone,
      recurrence_description: newEvent.recurrence_description || "",
      edit_mode: finalEditMode,
      isEdit: !!editingEvent,
      
    };
    console.log("📦 FINAL EVENT DATA with edit_mode:", eventData.edit_mode);

    // Add master_event_id if exists
    if (newEvent.master_event_id) {
      eventData.master_event_id = newEvent.master_event_id;
    }
    
    console.log("🎯 [GOOGLE] FINAL DATA:", eventData);

    

    if (onCreateEvent) {
      onCreateEvent(eventData);
    } else {
      console.error("❌ onCreateEvent is not defined!");
    }

    setEditingEvent(null);
    setNewEvent(null);
    setShowPopup(false);
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (popupRef.current && !popupRef.current.contains(e.target)) setShowPopup(false);
    };
    if (showPopup) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showPopup]);

  useEffect(() => {
    if (showPopup) {
      console.log("📝 POPUP STATE:", {
        newEvent,
        editingEvent,
        hasId: !!newEvent?.id,
        idValue: newEvent?.id
      });
    }
  }, [showPopup, newEvent, editingEvent]);

  const handleDateTimeChange = (field, value) => {
    if (field === 'start') {
      const newStart = value;
      const newEnd = newEvent.end;
      
      if (newEnd && newStart >= newEnd) {
        const startDate = new Date(newStart);
        const adjustedEnd = new Date(startDate.getTime() + 60 * 60 * 1000);
        setNewEvent({ 
          ...newEvent, 
          start: newStart,
          end: formatForInput(adjustedEnd)
        });
      } else {
        setNewEvent({ ...newEvent, start: newStart });
      }
    } else if (field === 'end') {
      const newEnd = value;
      const newStart = newEvent.start;
      
      if (newStart && newEnd <= newStart) {
        alert("Thời gian kết thúc phải LỚN HƠN thời gian bắt đầu!");
        return;
      }
      
      setNewEvent({ ...newEvent, end: newEnd });
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.leftHeader}>
          <button onClick={() => changeDate(-1)} className={styles.navBtn}>‹</button>
          <button onClick={() => changeDate(1)} className={styles.navBtn}>›</button>
          <button onClick={() => setSelectedDate(today)} className={styles.todayBtn}>Hôm nay</button>
          <div className={styles.headerDate}>{formatHeaderDate(selectedDate)}</div>
        </div>
      </div>

      <div className={styles.mainArea}>
        <div className={styles.sidebar}>
          <button
            className={styles.createButton}
            onClick={() =>
              openPopup(selectedDate, new Date(selectedDate.getTime() + 60 * 60 * 1000))
            }
          >
            + Tạo
          </button>

          <div className={styles.miniCalendar}>
            <div className={styles.miniHeader}>
              <span>{currentDate.toLocaleDateString("vi-VN", { month: "long", year: "numeric" })}</span>
              <div>
                <button
                  onClick={() =>
                    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1))
                  }
                >
                  ‹
                </button>
                <button
                  onClick={() =>
                    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1))
                  }
                >
                  ›
                </button>
              </div>
            </div>
            <div className={styles.miniWeekdays}>
              {["CN", "T2", "T3", "T4", "T5", "T6", "T7"].map((d) => (
                <div key={d}>{d}</div>
              ))}
            </div>
            <div className={styles.miniDays}>
              {miniDays.map((d, i) => {
                const isToday = d.date.toDateString() === today.toDateString();
                const isSelected = d.date.toDateString() === selectedDate.toDateString();
                return (
                  <div
                    key={i}
                    onClick={() => setSelectedDate(d.date)}
                    className={`${styles.miniDay} ${!d.isCurrent ? styles.otherMonth : ""} ${
                      isToday ? styles.today : ""
                    } ${isSelected ? styles.selected : ""}`}
                  >
                    {d.date.getDate()}
                  </div>
                );
              })}
            </div>
          </div>

          <div className={styles.calendarList}>
            <div className={styles.listTitle}>Lịch của tôi</div>
            {myCalendars.map((cal) => (
              <div
                key={cal.id}
                className={styles.calendarItem}
                onClick={() =>
                  setMyCalendars((c) =>
                    c.map((x) => (x.id === cal.id ? { ...x, checked: !x.checked } : x))
                  )
                }
              >
                <span
                  className={`${styles.checkbox} ${cal.checked ? styles.checked : ""}`}
                  style={{
                    borderColor: cal.color,
                    background: cal.checked ? cal.color : "transparent",
                  }}
                ></span>
                {cal.name}
              </div>
            ))}
          </div>
        </div>

        <div className={styles.calendarMain} ref={eventsRef}>
          <div
            className={styles.timeline}
            onClick={(e) => {
              // TEST 1: Lấy tất cả thông tin
              const timeline = e.currentTarget;
              const eventsColumn = timeline.querySelector(`.${styles.eventsColumn}`);
              
              
              // Dùng eventsColumn nếu có, không thì dùng timeline
              const targetEl = eventsColumn || timeline;
              const rect = targetEl.getBoundingClientRect();
              const scrollTop = targetEl.scrollTop;
              
              const clickY = e.clientY - rect.top + scrollTop;
              const hour = Math.floor(clickY / 60);
              const safeHour = Math.max(0, Math.min(23, hour));
              
              
              
              const newStart = new Date(selectedDate);
              newStart.setHours(safeHour, 0, 0, 0);
              const newEnd = new Date(newStart);
              newEnd.setHours(safeHour + 1, 0, 0, 0);
              
              openPopup(newStart, newEnd);
            }}
          >
            <div className={styles.timeColumn}>
              {/*<div className={styles.timezoneHeader}>
                GMT{(new Date().getTimezoneOffset() / -60) >= 0 ? '+' : ''}
                {new Date().getTimezoneOffset() / -60}
              </div>*/}
              
              <div className={styles.timeLabels}>
                {timeSlots.map((t) => (
                  <div key={t} className={styles.timeLabel}>{t}</div>
                ))}
              </div>
            </div>

            <div className={styles.eventsColumn} style={{ position: "relative" }}>
              <div className={styles.hourLines}>
                {timeSlots.map((_, i) => (
                  <div key={i} className={styles.hourLine}></div>
                ))}
              </div>

              {layoutedEvents.map((e, i) => {
                const normalizedEvent = normalizeEvent(e);
                const top = e.startMins;
                const height = Math.max(e.endMins - e.startMins, 30);
                
                // ✅ ÁP DỤNG CSS CLASS DỰA TRÊN CALENDAR SOURCE
                const eventClass = normalizedEvent.calendar_source === 'odd' 
                  ? styles.eventItemOdd 
                  : styles.eventItemEven;
                
                return (
                  <div
                    key={i}
                    className={`${styles.eventItem} ${eventClass}`}
                    style={{
                      top: `${top}px`,
                      height: `${height}px`,
                      width: e.width,
                      left: e.left,
                      position: "absolute",
                      borderLeft: `4px solid ${normalizedEvent.calendar_color}`,
                      background: normalizedEvent.calendar_source === 'odd' 
                        ? 'rgba(26, 115, 232, 0.1)' 
                        : 'rgba(52, 168, 83, 0.1)',
                    }}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      console.log("🖱️ CLICKED EVENT:", normalizedEvent);
                      setSelectedEvent(normalizedEvent);
                      setShowDetailPopup(true);
                    }}
                    onContextMenu={(ev) => handleEventRightClick(e, normalizedEvent, ev)}
                    title={`Nhấn chuột phải để xóa: ${normalizedEvent.name}`}
                  >
                    <div className={styles.eventName}>
                      {normalizedEvent.name}
                      <span className={styles.calendarBadge}>
                        {normalizedEvent.calendar_badge}
                      </span>
                    </div>
                    <div className={styles.eventTeacher}>{normalizedEvent.teacher}</div>
                    <div className={styles.eventTime}>
                      {new Date(normalizedEvent.start?.dateTime || normalizedEvent.start).toLocaleTimeString('vi-VN', { 
                        hour: '2-digit', 
                        minute: '2-digit' 
                      })}
                    </div>
                  </div>
                );
              })}

              {timePosition !== null && (
                <div className={styles.currentTimeLine} style={{ top: `${timePosition}px` }} />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu.visible && contextMenu.event && (
        <EventContextMenu
          position={contextMenu.position}
          event={contextMenu.event}
          isRecurring={contextMenu.isRecurring}
          onClose={handleCloseContextMenu}
          onDelete={handleDeleteFromContextMenu}
          onEdit={handleEditFromContextMenu}
          onViewDetails={handleViewDetailsFromContextMenu}
        />
      )}
      
      {/* Delete Confirmation Modal */}
      {showDeleteModal && eventToDelete && (
        <DeleteConfirmationModal
          event={eventToDelete}
          isRecurring={eventToDelete.recurrence || eventToDelete.recurringEventId}
          onConfirm={handleConfirmDelete}
          onCancel={() => {
            setShowDeleteModal(false);
            setEventToDelete(null);
          }}
        />
      )}

      {/* Thêm Edit Recurring Modal - đặt cùng cấp với các modal khác */}
      {showEditRecurringModal && editRecurringOptions.event && (
        <EditRecurringModal
          event={editRecurringOptions.originalEvent}
          onConfirm={handleConfirmEditMode}
          onCancel={() => {
            setShowEditRecurringModal(false);
            setEditRecurringOptions({
              event: null,
              originalEvent: null,
              editMode: 'this'
            });
          }}
        />
      )}

      {showDetailPopup && selectedEvent && (
        <div className={styles.popupOverlay}>
          <div className={styles.detailPopup}>
            <div className={styles.detailHeader}>
              <h3>{selectedEvent.name}</h3>
              <div className={`${styles.calendarBadgeDetail} ${
                selectedEvent.calendar_source === 'odd' ? styles.badgeOdd : styles.badgeEven
              }`}>
                {selectedEvent.calendar_badge} {selectedEvent.calendar_name}
              </div>
            </div>

            {selectedEvent.class_name && (
              <p><b>Tên lớp:</b> {selectedEvent.class_name}</p>
            )}
            <p><b>Giáo viên:</b> {selectedEvent.teacher}</p>
            <p><b>Chương trình:</b> {selectedEvent.program}</p>

            <p>
              <b>Thời gian:</b>{" "}
              {new Date(selectedEvent.start?.dateTime || selectedEvent.start).toLocaleString("vi-VN", {
                hour12: false,
                hour: "2-digit",
                minute: "2-digit",
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
              })}
              {" – "}
              {new Date(selectedEvent.end?.dateTime || selectedEvent.end).toLocaleString("vi-VN", {
                hour12: false,
                hour: "2-digit",
                minute: "2-digit",
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
              })}
            </p>

            <p>
              <b>Múi giờ:</b> {
                (() => {
                  const eventTimezone = selectedEvent.timezone || 
                                      selectedEvent.start?.timeZone || 
                                      selectedEvent.end?.timeZone ||
                                      "Asia/Ho_Chi_Minh";
                  
                  const timezoneOption = timezoneOptions.find(tz => tz.value === eventTimezone);
                  
                  return timezoneOption ? timezoneOption.label : eventTimezone;
                })()
              }
            </p>

            {selectedEvent.recurrence_description && (
              <div className={styles.recurrenceDescription}>
                <p><strong>📅 Lịch lặp:</strong> {selectedEvent.recurrence_description}</p>
              </div>
            )}

            {selectedEvent.zoom && (
              <p>
                <b>Zoom:</b>{" "}
                <a href={selectedEvent.zoom} target="_blank" rel="noopener noreferrer">
                  {selectedEvent.zoom}
                </a>
              </p>
            )}

            {(selectedEvent.meeting_id || selectedEvent.passcode) && (
              <div className={styles.meetingRow}>
                {selectedEvent.meeting_id && (
                  <p><b>Meeting ID:</b> {selectedEvent.meeting_id}</p>
                )}
                {selectedEvent.passcode && (
                  <p><b>Passcode:</b> {selectedEvent.passcode}</p>
                )}
              </div>
            )}

            {(selectedEvent.recurrence || selectedEvent.recurringEventId) && (
              <div className={styles.repeatBlock}>
                {(() => {
                  const hasRecurrence = selectedEvent.recurrence && 
                    (Array.isArray(selectedEvent.recurrence) || selectedEvent.recurrence.trim() !== "");
                  
                  return (
                    <>
                      <p><strong>🔁 Lịch lặp:</strong></p>
                      
                      {hasRecurrence ? (
                        <>
                          <p><b>Hình thức:</b> {selectedEvent.recurrence}</p>
                          
                          {selectedEvent.repeat_count > 1 && (
                            <p><b>Số lần lặp:</b> {selectedEvent.repeat_count}</p>
                          )}
                          
                          {selectedEvent.recurrence === "WEEKLY" && selectedEvent.byday?.length > 0 && (
                            <p><b>Ngày trong tuần:</b> {selectedEvent.byday.join(", ")}</p>
                          )}
                          
                          {selectedEvent.recurrence === "MONTHLY" && selectedEvent.bymonthday?.length > 0 && (
                            <p><b>Ngày trong tháng:</b> {selectedEvent.bymonthday.join(", ")}</p>
                          )}
                          
                          {selectedEvent.recurrence === "YEARLY" && (
                            <>
                              {selectedEvent.bymonth?.length > 0 && (
                                <p><b>Tháng:</b> {selectedEvent.bymonth.join(", ")}</p>
                              )}
                              {selectedEvent.bymonthday?.length > 0 && (
                                <p><b>Ngày:</b> {selectedEvent.bymonthday.join(", ")}</p>
                              )}
                            </>
                          )}
                        </>
                      ) : (
                        <p><b>Hình thức:</b> Sự kiện lặp lại</p>
                      )}
                    </>
                  );
                })()}
              </div>
            )}

            <div className={styles.detailActions}>
              <button
                onClick={async () => {
                  if (!selectedEvent.id) {
                    alert("Không thể chỉnh sửa: thiếu ID sự kiện");
                    return;
                  }
                  const recurrenceData = await parseRecurrenceFromEvent(selectedEvent);

                  const editEventData = {
                    id: selectedEvent.id,
                    title: selectedEvent.name,
                    class_name: selectedEvent.class_name || selectedEvent.classname || "",
                    teacher: selectedEvent.teacher,
                    program: selectedEvent.program,
                    zoom_link: selectedEvent.zoom,
                    meeting_id: selectedEvent.meeting_id || "",
                    passcode: selectedEvent.passcode || "",
                    recurrence: recurrenceData.recurrenceType,
                    repeat_count: recurrenceData.repeatCount,
                    byday: recurrenceData.byday,
                    bymonthday: recurrenceData.bymonthday,
                    bymonth: recurrenceData.bymonth,
                    start: formatForInput(selectedEvent.start?.dateTime || selectedEvent.start),
                    end: formatForInput(selectedEvent.end?.dateTime || selectedEvent.end),
                    timezone: selectedEvent.timezone || "Asia/Ho_Chi_Minh",
                    recurrence_description: selectedEvent.recurrence_description || "",
                    calendar_source: selectedEvent.calendar_source,
                  };

                  setNewEvent(editEventData);
                  handleEditEvent(selectedEvent);
                  setShowDetailPopup(false);
                  setShowPopup(true);
                }}
              >
                ✏️ Chỉnh sửa
              </button>

              <button
                onClick={() => {
                  if (!selectedEvent.id) {
                    alert("Không thể xóa: thiếu ID sự kiện");
                    return;
                  }
                  onDeleteEvent?.(selectedEvent);
                  setShowDetailPopup(false);
                }}
              >
                🗑️ Xóa
              </button>

              <button onClick={() => setShowDetailPopup(false)}>Đóng</button>
            </div>
          </div>
        </div>
      )}

      {showPopup && (
        <div className={styles.popupOverlay}>
          <div className={styles.popupBox} ref={popupRef}>
            <div className={styles.popupHeader}>
              <h3>🗓️ {editingEvent ? `Chỉnh sửa: ${newEvent.title}` : "Thêm sự kiện mới"}</h3>
              {newEvent?.target_calendar && (
                <div className={`${styles.calendarIndicator} ${
                  newEvent?.hour_type === 'even' ? styles.indicatorEven : styles.indicatorOdd
                }`}>
                  ⚡ Sẽ lưu vào: {newEvent.target_calendar}
                </div>
              )}
            </div>

            <div className={styles.debugInfo}>
              <div><strong>DEBUG CALENDAR LOGIC:</strong></div>
              <div>Giờ bắt đầu: {newEvent.start ? new Date(newEvent.start).getHours() : 'N/A'}h</div>
              <div>Loại giờ: {newEvent?.hour_type || 'chưa xác định'} ({newEvent?.hour_type === 'even' ? 'chẵn' : 'lẻ'})</div>
              <div>Calendar đích: {newEvent?.target_calendar || 'tự động'}</div>
            </div>

            <label>
              Tiêu đề (tự động):
              <input
                type="text"
                value={newEvent.title}
                readOnly
                style={{ backgroundColor: "#f0f0f0" }}
              />
            </label>
            
            <label>
              Tên lớp:
              <input
                type="text"
                value={newEvent.class_name || ""}
                onChange={(e) => {
                  const updated = { ...newEvent, class_name: e.target.value };
                  updated.title = `${updated.class_name || ""} - ${updated.teacher || ""} - ${updated.program || ""}`.trim();
                  setNewEvent(updated);
                }}
              />
            </label>

            <label>
              Giáo viên:
              <input
                type="text"
                value={newEvent.teacher}
                onChange={(e) => {
                  const updated = { ...newEvent, teacher: e.target.value };
                  updated.title = `${updated.class_name || ""} - ${updated.teacher || ""} - ${updated.program || ""}`.trim();
                  setNewEvent(updated);
                }}
              />
            </label>

            <label>
              Chương trình:
              <select
                value={newEvent.program}
                onChange={(e) => {
                  const updated = { ...newEvent, program: e.target.value };
                  updated.title = `${updated.class_name || ""} - ${updated.teacher || ""} - ${updated.program || ""}`.trim();
                  setNewEvent(updated);
                }}
                className={styles.programSelect}
              >
                {programOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Link Zoom:
              <input
                type="text"
                value={newEvent.zoom_link}
                onChange={(e) => setNewEvent({ ...newEvent, zoom_link: e.target.value })}
              />
            </label>

            <div className={styles.formRow}>
              <div className={styles.formGroup}>
                <label>Meeting ID:</label>
                <input
                  type="text"
                  value={newEvent.meeting_id || ""}
                  onChange={(e) =>
                    setNewEvent({ ...newEvent, meeting_id: e.target.value })
                  }
                />
              </div>
              <div className={styles.formGroup}>
                <label>Passcode:</label>
                <input
                  type="text"
                  value={newEvent.passcode || ""}
                  onChange={(e) =>
                    setNewEvent({ ...newEvent, passcode: e.target.value })
                  }
                />
              </div>
            </div>

            <div className={styles.formRow}>
              <div className={styles.formGroup}>
                <label>Bắt đầu:</label>
                <input
                  type="datetime-local"
                  value={newEvent.start || ""}
                  onChange={(e) => {
                    handleDateTimeChange('start', e.target.value);
                    
                    // ✅ CẬP NHẬT CALENDAR INDICATOR KHI GIỜ THAY ĐỔI
                    const hourType = checkEvenOddHour(e.target.value);
                    const targetCalendar = hourType === 'even' ? '📗 Calendar Chẵn' : '📘 Calendar Lẻ';
                    
                    setNewEvent(prev => ({
                      ...prev,
                      hour_type: hourType,
                      target_calendar: targetCalendar
                    }));
                  }}
                />
                {newEvent.start && (
                  <div className={styles.timeNote}>
                    Giờ: {new Date(newEvent.start).getHours()}h → {newEvent?.hour_type === 'even' ? '📗 Calendar Chẵn' : '📘 Calendar Lẻ'}
                  </div>
                )}
              </div>
              <div className={styles.formGroup}>
                <label>Kết thúc:</label>
                <input
                  type="datetime-local"
                  value={newEvent.end || ""}
                  onChange={(e) => handleDateTimeChange('end', e.target.value)}
                />
              </div>
            </div>

            <label>
              Múi giờ:
              <select
                value={newEvent?.timezone || "Asia/Ho_Chi_Minh"}
                onChange={(e) => {
                  const newTimezone = e.target.value;
                  console.log("🔄 TIMEZONE CHANGED - BEFORE SETSTATE:", {
                    from: newEvent?.timezone,
                    to: newTimezone
                  });
                  
                  setNewEvent(prev => {
                    const updated = { ...prev, timezone: newTimezone };
                    console.log("🔄 TIMEZONE CHANGED - AFTER SETSTATE:", updated.timezone);
                    return updated;
                  });
                }}
              >
                {timezoneOptions.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Lặp lại:
              <select
                value={newEvent.recurrence || ""}
                onChange={(e) => {
                  const val = e.target.value;
                  console.log("🔁 Chọn lặp lại:", val);
                  setNewEvent(prev => ({
                    ...prev,
                    recurrence: val,
                    repeat_count: val ? (prev.repeat_count > 1 ? prev.repeat_count : 2) : 1,
                    byday: Array.isArray(prev.byday) ? prev.byday : [],
                    bymonthday: Array.isArray(prev.bymonthday) ? prev.bymonthday : [],
                    bymonth: Array.isArray(prev.bymonth) ? prev.bymonth : [],
                  }));
                }}
              >
                <option value="">Không lặp</option>
                <option value="DAILY">Hàng ngày</option>
                <option value="WEEKLY">Hàng tuần</option>
                <option value="MONTHLY">Hàng tháng</option>
                <option value="YEARLY">Hàng năm</option>
              </select>
            </label>

            {newEvent.recurrence && (
              <label>
                Số lần lặp:
                <input
                  type="number"
                  min={1}
                  value={newEvent.repeat_count || 1}
                  onChange={(e) => setNewEvent(prev => ({
                    ...prev,
                    repeat_count: Number(e.target.value)
                  }))}
                />
              </label>
            )}

            

            {newEvent.recurrence === "WEEKLY" && (
              <div className={styles.weeklyGroup}>
                <label>Chọn ngày trong tuần:</label>
                <div className={styles.dayCheckboxes}>
                  {["MO", "TU", "WE", "TH", "FR", "SA", "SU"].map((day) => (
                    <label key={day} style={{ marginRight: "10px" }}>
                      <input
                        type="checkbox"
                        checked={Array.isArray(newEvent.byday) && newEvent.byday.includes(day)}
                        onChange={() => {
                          const arr = Array.isArray(newEvent.byday) ? newEvent.byday : [];
                          const newArr = arr.includes(day)
                            ? arr.filter((d) => d !== day)
                            : [...arr, day];
                          setNewEvent(prev => ({
                            ...prev,
                            byday: newArr
                          }));
                        }}
                      />
                      {day}
                    </label>
                  ))}
                </div>
              </div>
            )}

            {newEvent.recurrence === "MONTHLY" && (
              <label>
                Ngày trong tháng (vd: 1,15,30):
                <input
                  type="text"
                  value={Array.isArray(newEvent.bymonthday) ? newEvent.bymonthday.join(",") : ""}
                  onChange={(e) =>
                    setNewEvent({
                      ...newEvent,
                      bymonthday: e.target.value
                        .split(",")
                        .map((x) => Number(x.trim()))
                        .filter(Boolean),
                    })
                  }
                />
              </label>
            )}

            {newEvent.recurrence === "YEARLY" && (
              <>
                <label>
                  Tháng (vd: 1,6,12):
                  <input
                    type="text"
                    value={Array.isArray(newEvent.bymonth) ? newEvent.bymonth.join(",") : ""}
                    onChange={(e) =>
                      setNewEvent({
                        ...newEvent,
                        bymonth: e.target.value
                          .split(",")
                          .map((x) => Number(x.trim()))
                          .filter(Boolean),
                      })
                    }
                  />
                </label>
                <label>
                  Ngày (vd: 1,15,20):
                  <input
                    type="text"
                    value={Array.isArray(newEvent.bymonthday) ? newEvent.bymonthday.join(",") : ""}
                    onChange={(e) =>
                      setNewEvent({
                        ...newEvent,
                        bymonthday: e.target.value
                          .split(",")
                          .map((x) => Number(x.trim()))
                          .filter(Boolean),
                      })
                    }
                  />
                </label>
              </>
            )}

            <div className={styles.popupActions}>
              <button onClick={handleSave} className={styles.btnSave}>
                {editingEvent ? "💾 Cập nhật" : "➕ Tạo mới"}
              </button>
              
              <button onClick={() => setShowPopup(false)} className={styles.btnCancel}>
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}