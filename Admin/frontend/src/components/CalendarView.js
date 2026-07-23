// frontend/src/components/CalendarView.js
import { useState, useEffect, useRef, useMemo, useImperativeHandle, forwardRef } from "react";
import styles from "./CalendarView.module.css";
import { parseZoomInfo } from "../utils/sanitizeDescription";
import { getEvent } from "../services/api";
import { checkScheduleConflict } from "../services/api";
import { getTimezones } from "../services/api";
import { getPrograms } from "../services/api";
import DeleteConfirmationModal from "./DeleteConfirmationModal";
import EventContextMenu from "./EventContextMenu";
import EditRecurringModal from "./EditRecurringModal";
import ProgramManageModal from "./ProgramManageModal";
import moment from "moment-timezone";



const CalendarView = forwardRef(function CalendarView({ events, onCreateEvent, onDeleteEvent, calendarFilter }, ref) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [showPopup, setShowPopup] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [showDetailPopup, setShowDetailPopup] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [newEvent, setNewEvent] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const savingRef = useRef(false);
  const popupRef = useRef(null);
  const eventsRef = useRef(null);
  const scrollTargetRef = useRef(null); // ✅ THÊM REF LƯU TRỮ THỜI GIAN CẦN SCROLL
  const searchBarRef = useRef(null); // ✅ REF CHO Ô TÌM KIẾM
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
  const [searchQuery, setSearchQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [editRecurringOptions, setEditRecurringOptions] = useState({
    event: null,
    originalEvent: null,
    editMode: 'this'
  });

  // ✅ PROGRAM MANAGEMENT
  const [showProgramModal, setShowProgramModal] = useState(false);


  const [myCalendars, setMyCalendars] = useState([
    { id: 1, name: "Calendar Lẻ (Giờ lẻ)", color: "#1a73e8", checked: true },
    { id: 2, name: "Calendar Chẵn (Giờ chẵn)", color: "#34a853", checked: true },
  ]);
  

  const [timezoneOptions, setTimezoneOptions] = useState([
    { value: "Asia/Ho_Chi_Minh", label: "🇻🇳 Giờ Việt Nam (UTC+7)" },
    { value: "America/Chicago", label: "🇺🇸 Giờ miền Trung - Chicago (UTC-6/-5)" },
  ]);

  const [programOptions, setProgramOptions] = useState([
    { value: "", label: "-- Chọn chương trình --" }
  ]);

  // ✅ ĐỊNH NGHĨA LOADPROGRAMS FUNCTION
  const loadPrograms = async () => {
    try {
      const data = await getPrograms();
      const options = [
        { value: "", label: "-- Chọn chương trình --" },
        ...data.map(p => ({ value: p.id, label: p.name }))
      ];
      setProgramOptions(options);
    } catch (error) {
      console.error("❌ Failed to load programs:", error);
      // Keep default option on error
    }
  };

  // ✅ HELPER: GET PROGRAM NAME FROM ID
  const getProgramNameFromId = (programId) => {
    if (!programId) return "";
    const program = programOptions.find(p => p.value === programId);
    return program ? program.label : programId;
  };

  // 📌 LOAD PROGRAMS FROM API
  useEffect(() => {
    loadPrograms();
  }, []);

  const timeSlots = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, "0")}:00`);

  // ✅ THÊM HÀM SCROLL ĐẾN EVENT VỪA TẠO
  useImperativeHandle(ref, () => ({
    scrollToEvent: (eventStartTime) => {
      if (!eventStartTime) {
        console.warn("⚠️ scrollToEvent called with invalid time:", eventStartTime);
        return;
      }
      
      console.log("📍 scrollToEvent called with:", eventStartTime);
      
      try {
        // ✅ HANDLE DIFFERENT INPUT FORMATS
        let timeString = null;
        
        // Format 1: Google Calendar object {dateTime: "...", date: "..."}
        if (typeof eventStartTime === 'object') {
          if (eventStartTime.dateTime) {
            timeString = eventStartTime.dateTime;
            console.log("📦 Extracted dateTime from object:", timeString);
          } else if (eventStartTime.date) {
            timeString = eventStartTime.date;
            console.log("📦 Extracted date from object:", timeString);
          } else if (eventStartTime.start) {
            timeString = eventStartTime.start;
            console.log("📦 Extracted start from object:", timeString);
          }
        } else if (typeof eventStartTime === 'string') {
          // Format 2: Direct string
          timeString = eventStartTime;
        }
        
        if (!timeString) {
          console.warn("⚠️ Could not extract time string from input:", eventStartTime);
          return;
        }
        
        // ✅ PARSE THỜI GIAN - HỖ TRỢ ĐỊNH DẠNG ISO VÀ TIMEZONE
        let startDate;
        
        // Nếu là chuỗi ISO, sử dụng moment để parse chính xác
        if (timeString.includes('T') || timeString.includes('-')) {
          const m = moment(timeString);
          if (m.isValid()) {
            startDate = m.toDate();
            console.log("📅 Parsed ISO date with moment:", startDate);
          } else {
            console.warn("⚠️ moment.isValid() returned false for:", timeString);
            return;
          }
        } else {
          startDate = new Date(timeString);
          if (isNaN(startDate.getTime())) {
            console.warn("⚠️ Invalid Date object created from:", timeString);
            return;
          }
        }
        
        // ✅ DOUBLE CHECK VALIDITY BEFORE USING
        if (isNaN(startDate.getTime())) {
          console.error("❌ Invalid date after parsing:", startDate);
          return;
        }
        
        // ✅ ĐIỀU HƯỚNG ĐẾN NGÀY CỦA SỰ KIỆN
        setCurrentDate(startDate);
        setSelectedDate(startDate);
        
        // ✅ LƯU THỜI GIAN CẦN SCROLL VÀO REF (CẬP NHẬT LOGIC)
        scrollTargetRef.current = {
          timeString: timeString,
          hour: startDate.getHours(),
          minute: startDate.getMinutes()
        };
        
        console.log("✅ Scroll target saved:", scrollTargetRef.current);
      } catch (err) {
        console.error("❌ Error parsing event start time:", err);
      }
    }
  }), []);

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
      
      const eventTimezone = event.timezone || event.start?.timeZone || "Asia/Ho_Chi_Minh";
      const userTimezone = eventTimezone; // hoặc lấy timezone người dùng hiện tại nếu có

      // 🕐 Chuyển UTC ISO → giờ local theo timezone đúng
      const localStart = moment.tz(event.start?.dateTime || event.start, eventTimezone)
        .tz(userTimezone)
        .format("YYYY-MM-DDTHH:mm");
      const localEnd = moment.tz(event.end?.dateTime || event.end, eventTimezone)
        .tz(userTimezone)
        .format("YYYY-MM-DDTHH:mm");

      // ✅ TÍNH CÁC COUNT TỰ ĐỘNG CHO TẤT CẢ LOẠI RECURRENCE
      let weekCount = 1;
      let monthCount = 1;
      let yearCount = 1;
      
      switch (recurrenceData.recurrenceType) {
        case "WEEKLY":
          if (recurrenceData.byday && recurrenceData.byday.length > 0) {
            weekCount = Math.ceil(adjustedRepeatCount / recurrenceData.byday.length);
          } else {
            weekCount = adjustedRepeatCount;
          }
          break;
          
        case "MONTHLY":
          if (recurrenceData.bymonthday && recurrenceData.bymonthday.length > 0) {
            monthCount = Math.ceil(adjustedRepeatCount / recurrenceData.bymonthday.length);
          } else {
            monthCount = adjustedRepeatCount;
          }
          break;
          
        case "YEARLY":
          const daysPerYear = recurrenceData.bymonthday?.length || 1;
          yearCount = Math.ceil(adjustedRepeatCount / daysPerYear);
          break;
          
        default:
          // DAILY hoặc không lặp
          weekCount = 1;
          monthCount = 1;
          yearCount = 1;
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
        start: localStart,
        end: localEnd,
        timezone: userTimezone,
        recurrence_description: event.recurrence_description || "",
        calendar_source: event.calendar_source,
        is_recurring: event.recurrence || event.recurringEventId,
        recurring_event_id: event.recurringEventId,
        // ✅ THÊM TẤT CẢ CÁC COUNT
        week_count: weekCount,
        month_count: monthCount,
        year_count: yearCount,
        
        // ✅ THÊM TRƯỜNG INPUT TẠM THỜI ĐỂ HIỂN THỊ
        _monthly_input: recurrenceData.bymonthday ? recurrenceData.bymonthday.join(",") : "",
        _yearly_month_input: recurrenceData.bymonth ? recurrenceData.bymonth.join(",") : "",
        _yearly_day_input: recurrenceData.bymonthday ? recurrenceData.bymonthday.join(",") : "",
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
    const userTimezone = eventTimezone; // Hoặc timezone hiện tại của user

    // 🕐 Convert UTC ISO → local time theo timezone
    const localStart = moment
      .tz(event.start, eventTimezone)
      .tz(userTimezone)
      .format("YYYY-MM-DDTHH:mm");
    const localEnd = moment
      .tz(event.end, eventTimezone)
      .tz(userTimezone)
      .format("YYYY-MM-DDTHH:mm");

    // 2. TẠO EVENT DATA VỚI METADATA ĐÚNG
    const eventWithEditMode = {
      ...event,
      start: localStart,
      end: localEnd,
      editMode: editMode,
      repeat_count: finalRepeatCount,
      timezone: userTimezone,
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

  // ✅ GỢI Ý TÌM KIẾM — tính từ tất cả events
  const searchSuggestions = useMemo(() => {
    if (!searchQuery.trim()) return { names: [], teachers: [], programs: [] };
    const q = searchQuery.trim().toLowerCase();
    const names = new Set();
    const teachers = new Set();
    const programs = new Set();
    events.forEach(event => {
      const rawDesc = event.description || "";
      const parsed = parseZoomInfo(rawDesc);
      const className = event.class_name || event.classname || parsed.classname || event.summary || event.name || "";
      const teacher = event.teacher || parsed.teacher || "";
      const programId = event.program || parsed.program || "";
      // ✅ CONVERT PROGRAM ID TO NAME FOR SUGGESTIONS
      const programName = getProgramNameFromId(programId);
      if (className && className.toLowerCase().includes(q)) names.add(className);
      if (teacher && teacher.toLowerCase().includes(q)) teachers.add(teacher);
      if (programName && programName.toLowerCase().includes(q)) programs.add(programName);
    });
    return {
      names: [...names].slice(0, 6),
      teachers: [...teachers].slice(0, 6),
      programs: [...programs].slice(0, 6)
    };
  }, [events, searchQuery, programOptions]);

  // ✅ FILTER EVENTS DỰA TRÊN CALENDAR FILTER
  const filteredEvents = events.filter(event => {
    // 1. Lọc theo calendarFilter (odd/even/both)
    let passesCalendarFilter = true;
    if (calendarFilter === 'odd') {
      passesCalendarFilter = event._calendar_source === 'odd';
    } else if (calendarFilter === 'even') {
      passesCalendarFilter = event._calendar_source === 'even';
    }
    
    if (!passesCalendarFilter) return false;
    
    // 2. Lọc theo myCalendars đã chọn
    const eventCalendarSource = event._calendar_source || 'odd';
    const eventCalendarType = 
      eventCalendarSource === 'odd' ? "Calendar Lẻ (Giờ lẻ)" :
      eventCalendarSource === 'even' ? "Calendar Chẵn (Giờ chẵn)" : "Other";
    
    // Tìm calendar tương ứng trong myCalendars
    const matchingCalendar = myCalendars.find(cal => 
      cal.name.includes(eventCalendarType) ||
      (eventCalendarSource === 'odd' && cal.name.includes("Lẻ")) ||
      (eventCalendarSource === 'even' && cal.name.includes("Chẵn"))
    );
    
    // Nếu không tìm thấy calendar phù hợp, cho phép hiển thị (fallback)
    if (!matchingCalendar) return true;
    
    // Chỉ hiển thị nếu calendar được checked
    return matchingCalendar.checked;
  }).filter(event => {
    // 3. Lọc theo từ khóa tìm kiếm (tên lớp, giáo viên, chương trình)
    if (!searchQuery.trim()) return true;
    // Tách query thành nhiều từ — từng từ phải khớp ít nhất 1 trong 3 trường
    const words = searchQuery.trim().toLowerCase().split(/\s+/);
    // Parse từ description giống ClassTable.js (dùng parseZoomInfo)
    const rawDesc = event.description || "";
    const parsed = parseZoomInfo(rawDesc);
    const className = (event.class_name || event.classname || parsed.classname || event.summary || event.name || "").toLowerCase();
    const teacher = (event.teacher || parsed.teacher || "").toLowerCase();
    const program = (event.program || parsed.program || "").toLowerCase();
    // AND logic: mỗi từ phải khớp ít nhất 1 trường
    return words.every(w => className.includes(w) || teacher.includes(w) || program.includes(w));
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

  // ✅ AUTO-SCROLL KHIBANGAY CÓ SCROLL TARGET
  useEffect(() => {
    if (!scrollTargetRef.current || !eventsRef.current) return;
    
    const scrollTarget = scrollTargetRef.current;
    scrollTargetRef.current = null; // Reset để không scroll lại
    
    try {
      let hour, minute;
      
      // ✅ HANDLE NEW OBJECT STRUCTURE
      if (typeof scrollTarget === 'object' && scrollTarget.hour !== undefined) {
        hour = scrollTarget.hour;
        minute = scrollTarget.minute;
        console.log("📊 Using stored scroll target:", scrollTarget);
      } else {
        // Fallback: parse time string
        const timeString = typeof scrollTarget === 'string' ? scrollTarget : scrollTarget.toString();
        
        let startDate;
        if (timeString.includes('T')) {
          const m = moment(timeString);
          if (m.isValid()) {
            startDate = m.toDate();
            console.log("📅 Parsed event time with moment:", startDate);
          } else {
            console.warn("⚠️ Invalid moment parse for:", timeString);
            return;
          }
        } else {
          startDate = new Date(timeString);
        }
        
        if (isNaN(startDate.getTime())) {
          console.warn("⚠️ Invalid date:", startDate);
          return;
        }
        
        hour = startDate.getHours();
        minute = startDate.getMinutes();
      }
      
      const scrollPosition = hour * 60 + minute;
      
      console.log("📊 Scroll calculation", {
        hour,
        minute,
        scrollPosition
      });
      
      setTimeout(() => {
        if (eventsRef.current) {
          // ✅ FIND .timeline ELEMENT (child of calendarMain, not parent)
          const timelineElement = eventsRef.current.querySelector(`.${styles.timeline}`);
          
          if (timelineElement) {
            console.log("📍 Found .timeline element", {
              scrollHeight: timelineElement.scrollHeight,
              clientHeight: timelineElement.clientHeight,
              scrollPosition
            });
            
            timelineElement.scrollTop = scrollPosition;
            console.log("✅ Scrolled .timeline", {
              scrollPosition,
              newScrollTop: timelineElement.scrollTop,
              match: Math.abs(timelineElement.scrollTop - scrollPosition) < 5
            });
          } else {
            console.warn("⚠️ .timeline element not found!");
          }
        }
      }, 300);
    } catch (error) {
      console.error("❌ Error in auto-scroll effect:", error);
    }
  }, [layoutedEvents, styles]);

  const changeDate = (offset) => {
    const newDate = new Date(selectedDate);
    if (viewMode === "week") {
      newDate.setDate(selectedDate.getDate() + offset * 7);
    } else if (viewMode === "month") {
      newDate.setMonth(selectedDate.getMonth() + offset);
    } else {
      newDate.setDate(selectedDate.getDate() + offset);
    }
    setSelectedDate(newDate);
  };

  // ✅ Sync mini calendar month theo selectedDate (bao gồm cả nút Hôm nay, mini click, changeDate)
  useEffect(() => {
    if (
      selectedDate.getMonth() !== currentDate.getMonth() ||
      selectedDate.getFullYear() !== currentDate.getFullYear()
    ) {
      setCurrentDate(new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1));
    }
  }, [selectedDate]);

  const formatHeaderDate = (date) =>
    date.toLocaleDateString("vi-VN", { day: "numeric", month: "long", year: "numeric" });

  // ✅ VIEW MODE HELPERS
  const getWeekDays = (date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    const monday = new Date(d);
    monday.setDate(d.getDate() + diff);
    monday.setHours(0, 0, 0, 0);
    return Array.from({ length: 7 }, (_, i) => {
      const wd = new Date(monday);
      wd.setDate(monday.getDate() + i);
      return wd;
    });
  };

  const getMonthDays = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    let startDay = firstDay.getDay();
    startDay = startDay === 0 ? 6 : startDay - 1; // Mon=0, Sun=6
    const days = [];
    const prevMonthLastDay = new Date(year, month, 0).getDate();
    for (let i = startDay - 1; i >= 0; i--) {
      days.push({ date: new Date(year, month - 1, prevMonthLastDay - i), isCurrent: false });
    }
    for (let i = 1; i <= daysInMonth; i++) {
      days.push({ date: new Date(year, month, i), isCurrent: true });
    }
    const remaining = (7 - (days.length % 7)) % 7;
    for (let i = 1; i <= remaining; i++) {
      days.push({ date: new Date(year, month + 1, i), isCurrent: false });
    }
    return days;
  };

  const layoutEventsForDay = (evts, day) => {
    const dayStart = new Date(day);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = new Date(day);
    dayEnd.setHours(23, 59, 59, 999);
    const sorted = evts
      .map((e) => {
        const start = new Date(e.start?.dateTime || e.start);
        const end = new Date(e.end?.dateTime || e.end);
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
      const idx = overlapGroup.findIndex((e) => e === event);
      const width = 100 / overlapGroup.length;
      const left = idx * width;
      positioned.push({ ...event, width: `${width}%`, left: `${left}%` });
    }
    return positioned;
  };

  const formatWeekHeader = (date) => {
    const days = getWeekDays(date);
    const start = days[0];
    const end = days[6];
    if (start.getMonth() === end.getMonth()) {
      return `${start.getDate()} – ${end.getDate()} Tháng ${start.getMonth() + 1}, ${start.getFullYear()}`;
    }
    return `${start.getDate()} Tháng ${start.getMonth() + 1} – ${end.getDate()} Tháng ${end.getMonth() + 1}, ${end.getFullYear()}`;
  };

  const formatMonthHeader = (date) =>
    date.toLocaleDateString("vi-VN", { month: "long", year: "numeric" });

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
  const [viewMode, setViewMode] = useState("week"); // "day" | "week" | "month"

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

  

  const formatForBackend = (datetimeLocal, timezone = "Asia/Ho_Chi_Minh", convertToUTC = true) => {
      if (!datetimeLocal) return "";

      if (convertToUTC) {
          // Chuyển local → UTC (cho backend lưu UTC)
          const utcISO = moment.tz(datetimeLocal, timezone)
              .utc()
              .format("YYYY-MM-DDTHH:mm:ss[Z]");
          console.log("📤 formatForBackend (UTC):", datetimeLocal, "(", timezone, ") →", utcISO);
          return utcISO;
      } else {
          // Gửi local ISO + timezone, giữ UTC để Google Calendar hiển thị đúng
          const localISO = moment.tz(datetimeLocal, timezone)
              .format("YYYY-MM-DDTHH:mm:ss");
          console.log("📤 formatForBackend (local):", datetimeLocal, "(", timezone, ") →", localISO);
          return localISO;
      }
  };

  const createConflictMessage = (conflictResult, currentTeacher) => {
      let message = `⚠️ KIỂM TRA XUNG ĐỘT LỊCH\n\n`;
      
      if (conflictResult.has_conflict && conflictResult.conflicts.length > 0) {
          message += `Giáo viên "${currentTeacher}" có ${conflictResult.conflicts.length} xung đột:\n\n`;
          
          conflictResult.conflicts.forEach((conflict, index) => {
              const startTime = new Date(conflict.event_start).toLocaleString('vi-VN');
              const endTime = new Date(conflict.event_end).toLocaleString('vi-VN');
              
              message += `${index + 1}. ${conflict.event_summary}\n`;
              message += `   👨‍🏫 ${conflict.event_teacher}\n`;
              message += `   🕒 ${startTime} - ${endTime}\n\n`;
          });
          
          message += `Bạn muốn:\n`;
          message += `• "OK" - VẪN tạo sự kiện (có xung đột)\n`;
          message += `• "Cancel" - HỦY và chọn thời gian khác\n`;
      } else {
          message += `✅ Không có xung đột với giáo viên "${currentTeacher}"\n\n`;
          message += `"OK" để tiếp tục tạo sự kiện.`;
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
      week_count: 1,      // THÊM DÒNG NÀY
      month_count: 1,     // THÊM DÒNG NÀY
      year_count: 1,      // THÊM DÒNG NÀY
      byday: [],
      bymonthday: [],
      bymonth: [],
      timezone: defaultTimezone,
      recurrence_description: "",
      // ✅ THÊM THÔNG TIN CALENDAR
      hour_type: hourType,
      target_calendar: targetCalendar,
      // Thêm trường tạm thời
      _monthly_input: "",
      _yearly_month_input: "",
      _yearly_day_input: "",
    };

    setNewEvent(defaultEvent);
    setEditingEvent(null);
    setShowPopup(true);
    
    // ✅ HIỂN THỊ THÔNG BÁO VỀ CALENDAR
    //setTimeout(() => {
    //}, 100);
  };

  const performSave = async () => {
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
    
    if (!newEvent.class_name || newEvent.class_name.trim() === "") {
      alert("Vui lòng nhập tên lớp học!");
      return;
    }
    if (!newEvent.teacher || newEvent.teacher.trim() === "") {
      alert("Vui lòng nhập tên giáo viên!");
      return;
    }
    if (!newEvent.program || newEvent.program.trim() === "") {
      alert("Vui lòng chọn tên chương trình!");
      return;
    }
    if (!newEvent.zoom_link || newEvent.zoom_link.trim() === "") {
      alert("Vui lòng nhập liên kết Zoom!");
      return;
    }
    
    // 🔹 Chỉ gửi ISO chuẩn UTC (cực kỳ quan trọng)
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
          const userConfirmed = window.confirm(conflictMessage);
          if (!userConfirmed) return; // Không có alert thêm
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
    // 🕐 Xác định xem người dùng có đổi timezone thực sự không
    const timezoneChanged =
      editingEvent && newEvent.timezone && editingEvent.timezone !== newEvent.timezone;

    // ⚙️ Nếu chỉ đổi timezone hiển thị, giữ UTC gốc (convertToUTC=false)
    const startForBackend = formatForBackend(
      newEvent.start,
      finalTimezone,
      timezoneChanged // convertToUTC = true khi timezoneChanged = true
    );
    const endForBackend = formatForBackend(
      newEvent.end,
      finalTimezone,
      timezoneChanged
    );

    console.log("🕓 Timezone change detected:", timezoneChanged);
    console.log("📤 Sending to backend:", {
      startForBackend,
      endForBackend,
      finalTimezone,
      convertToUTC: timezoneChanged,
    });

    // ✅ Gói dữ liệu gửi backend
    const eventData = {
      ...(newEvent.id && { id: newEvent.id }),
      name: newEvent.title,
      classname: newEvent.class_name || "",
      teacher: newEvent.teacher,
      program: newEvent.program,
      zoom_link: newEvent.zoom_link,
      meeting_id: newEvent.meeting_id,
      passcode: newEvent.passcode,
      ...(newEvent.editMode !== "this" || !newEvent.id?.includes("_")
        ? {
            recurrence: newEvent.recurrence || "",
            repeat_count: newEvent.repeat_count || 1,
            byday: newEvent.byday || [],
            bymonthday: newEvent.bymonthday || [],
            bymonth: newEvent.bymonth || [],
          }
        : {}),
      start: startForBackend,
      end: endForBackend,
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
      await onCreateEvent(eventData);
    } else {
      throw new Error("onCreateEvent is not defined");
    }

    setEditingEvent(null);
    setNewEvent(null);
    setShowPopup(false);
  };

  const handleSave = async () => {
    if (savingRef.current) return;

    savingRef.current = true;
    setIsSaving(true);
    try {
      await performSave();
    } catch (error) {
      console.error("❌ Failed to save event:", error);
    } finally {
      savingRef.current = false;
      setIsSaving(false);
    }
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      // ✅ CHECK IF CLICK IS FROM WITHIN A MODAL
      const isClickFromModal = e.target.closest('[data-modal="true"]') || 
                               e.target.closest('.modalOverlay');
      
      if (isClickFromModal) return; // Don't close popup if clicking on modal
      
      if (popupRef.current && !popupRef.current.contains(e.target)) setShowPopup(false);
    };
    if (showPopup) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showPopup]);

  // ✅ ĐÓNG DROPDOWN GỢI Ý KHI CLICK RA NGOÀI
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchBarRef.current && !searchBarRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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
          <div className={styles.headerDate}>
            {viewMode === "day" && formatHeaderDate(selectedDate)}
            {viewMode === "week" && formatWeekHeader(selectedDate)}
            {viewMode === "month" && formatMonthHeader(selectedDate)}
          </div>
        </div>
        <div className={styles.searchBar} ref={searchBarRef}>
          <input
            type="text"
            placeholder="🔍 Tìm theo tên lớp, giáo viên, chương trình..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setShowSuggestions(true); }}
            onFocus={() => setShowSuggestions(true)}
            className={styles.searchInput}
          />
          {searchQuery && (
            <button
              className={styles.searchClearBtn}
              onClick={() => { setSearchQuery(""); setShowSuggestions(false); }}
              title="Xóa tìm kiếm"
            >
              ✕
            </button>
          )}
          {showSuggestions && searchQuery.trim() &&
            (searchSuggestions.names.length + searchSuggestions.teachers.length + searchSuggestions.programs.length) > 0 && (
            <div className={styles.searchDropdown}>
              {searchSuggestions.names.length > 0 && (
                <>
                  <div className={styles.searchDropdownSection}>📚 Tên lớp</div>
                  {searchSuggestions.names.map((name, i) => (
                    <div key={i} className={styles.searchDropdownItem}
                      onMouseDown={() => { setSearchQuery(name); setShowSuggestions(false); }}>
                      {name}
                    </div>
                  ))}
                </>
              )}
              {searchSuggestions.teachers.length > 0 && (
                <>
                  <div className={styles.searchDropdownSection}>👤 Giáo viên</div>
                  {searchSuggestions.teachers.map((t, i) => (
                    <div key={i} className={styles.searchDropdownItem}
                      onMouseDown={() => { setSearchQuery(t); setShowSuggestions(false); }}>
                      {t}
                    </div>
                  ))}
                </>
              )}
              {searchSuggestions.programs.length > 0 && (
                <>
                  <div className={styles.searchDropdownSection}>🎯 Chương trình</div>
                  {searchSuggestions.programs.map((p, i) => (
                    <div key={i} className={styles.searchDropdownItem}
                      onMouseDown={() => { setSearchQuery(p); setShowSuggestions(false); }}>
                      {p}
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
        {/* ✅ View Mode Selector */}
        <div className={styles.viewSelector}>
          <button
            className={`${styles.viewBtn} ${viewMode === "day" ? styles.viewBtnActive : ""}`}
            onClick={() => setViewMode("day")}
          >
            Ngày
          </button>
          <button
            className={`${styles.viewBtn} ${viewMode === "week" ? styles.viewBtnActive : ""}`}
            onClick={() => setViewMode("week")}
          >
            Tuần
          </button>
          <button
            className={`${styles.viewBtn} ${viewMode === "month" ? styles.viewBtnActive : ""}`}
            onClick={() => setViewMode("month")}
          >
            Tháng
          </button>
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
          {/* ✅ DAY VIEW */}
          {viewMode === "day" && (
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
                console.log("🧭 DEBUG EVENT:", normalizedEvent);
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
                      {moment(normalizedEvent.start?.dateTime)
                        .tz(normalizedEvent.start?.timeZone || normalizedEvent.timezone || "Asia/Ho_Chi_Minh")
                        .format("HH:mm")}
                    </div>
                  </div>
                );
              })}

              {timePosition !== null && (
                <div className={styles.currentTimeLine} style={{ top: `${timePosition}px` }} />
              )}
            </div>
          </div>
          )} {/* end day view */}

          {/* ✅ WEEK VIEW */}
          {viewMode === "week" && (
            <div className={styles.weekView}>
              {/* Week day header row */}
              <div className={styles.weekViewHeader}>
                <div className={styles.weekTimeGutter}></div>
                {getWeekDays(selectedDate).map((day, idx) => {
                  const isToday = day.toDateString() === today.toDateString();
                  return (
                    <div
                      key={idx}
                      className={`${styles.weekDayHeader} ${isToday ? styles.weekDayToday : ""}`}
                      onClick={() => { setSelectedDate(day); setViewMode("day"); }}
                    >
                      <div className={styles.weekDayName}>
                        {day.toLocaleDateString("vi-VN", { weekday: "short" })}
                      </div>
                      <div className={`${styles.weekDayNum} ${isToday ? styles.todayCircle : ""}`}>
                        {day.getDate()}
                      </div>
                    </div>
                  );
                })}
              </div>
              {/* Scrollable week body */}
              <div className={styles.weekBody}>
                <div className={styles.weekTimeColumn}>
                  {timeSlots.map((t) => (
                    <div key={t} className={styles.weekTimeLabel}>{t}</div>
                  ))}
                </div>
                {getWeekDays(selectedDate).map((day, dayIdx) => {
                  const dayEvts = filteredEvents.filter((e) => {
                    const s = new Date(e.start?.dateTime || e.start);
                    const en = new Date(e.end?.dateTime || e.end);
                    const ds = new Date(day); ds.setHours(0, 0, 0, 0);
                    const de = new Date(day); de.setHours(23, 59, 59, 999);
                    return en > ds && s < de;
                  });
                  const layoutedDay = layoutEventsForDay(dayEvts, day);
                  const isDayToday = day.toDateString() === today.toDateString();
                  return (
                    <div
                      key={dayIdx}
                      className={`${styles.weekDayColumn} ${isDayToday ? styles.weekDayColumnToday : ""}`}
                      onClick={(e) => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        const clickY = e.clientY - rect.top;
                        const hour = Math.max(0, Math.min(23, Math.floor(clickY / 60)));
                        const newStart = new Date(day);
                        newStart.setHours(hour, 0, 0, 0);
                        const newEnd = new Date(newStart);
                        newEnd.setHours(hour + 1, 0, 0, 0);
                        openPopup(newStart, newEnd);
                      }}
                    >
                      <div className={styles.hourLines}>
                        {timeSlots.map((_, i) => (
                          <div key={i} className={styles.hourLine}></div>
                        ))}
                      </div>
                      {layoutedDay.map((ev, i) => {
                        const ne = normalizeEvent(ev);
                        const top = ev.startMins;
                        const height = Math.max(ev.endMins - ev.startMins, 20);
                        const eventClass = ne.calendar_source === "odd"
                          ? styles.eventItemOdd
                          : styles.eventItemEven;
                        return (
                          <div
                            key={i}
                            className={`${styles.weekEventItem} ${eventClass}`}
                            style={{
                              top: `${top}px`,
                              height: `${height}px`,
                              width: ev.width,
                              left: ev.left,
                              position: "absolute",
                              borderLeft: `4px solid ${ne.calendar_color}`,
                            }}
                            onClick={(evv) => {
                              evv.stopPropagation();
                              setSelectedEvent(ne);
                              setShowDetailPopup(true);
                            }}
                            onContextMenu={(evv) => handleEventRightClick(ev, ne, evv)}
                          >
                            <div className={styles.eventName}>{ne.name}</div>
                            <div className={styles.eventTime}>
                              {moment(ne.start?.dateTime || ne.start)
                                .tz(ne.timezone || "Asia/Ho_Chi_Minh")
                                .format("HH:mm")}
                            </div>
                          </div>
                        );
                      })}
                      {timePosition !== null && isDayToday && (
                        <div className={styles.currentTimeLine} style={{ top: `${timePosition}px` }} />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ✅ MONTH VIEW */}
          {viewMode === "month" && (
            <div className={styles.monthView}>
              <div className={styles.monthWeekdayHeader}>
                {["T2", "T3", "T4", "T5", "T6", "T7", "CN"].map((d) => (
                  <div key={d} className={styles.monthWeekdayLabel}>{d}</div>
                ))}
              </div>
              <div className={styles.monthGrid}>
                {getMonthDays(selectedDate).map((d, i) => {
                  const isToday = d.date.toDateString() === today.toDateString();
                  const dayEvts = filteredEvents.filter((e) => {
                    const s = new Date(e.start?.dateTime || e.start);
                    const ds = new Date(d.date); ds.setHours(0, 0, 0, 0);
                    const de = new Date(d.date); de.setHours(23, 59, 59, 999);
                    return s >= ds && s <= de;
                  });
                  const maxVisible = 3;
                  const visibleEvts = dayEvts.slice(0, maxVisible);
                  const hiddenCount = dayEvts.length - maxVisible;
                  return (
                    <div
                      key={i}
                      className={`${styles.monthCell} ${!d.isCurrent ? styles.monthOtherMonth : ""} ${isToday ? styles.monthToday : ""}`}
                      onClick={() => { setSelectedDate(d.date); setViewMode("day"); }}
                    >
                      <div className={`${styles.monthDayNum} ${isToday ? styles.monthTodayNum : ""}`}>
                        {d.date.getDate()}
                      </div>
                      {visibleEvts.map((ev, j) => {
                        const ne = normalizeEvent(ev);
                        return (
                          <div
                            key={j}
                            className={`${styles.monthEventChip} ${ne.calendar_source === "odd" ? styles.chipOdd : styles.chipEven}`}
                            onClick={(e) => { e.stopPropagation(); setSelectedEvent(ne); setShowDetailPopup(true); }}
                            title={ne.name}
                          >
                            {ne.name}
                          </div>
                        );
                      })}
                      {hiddenCount > 0 && (
                        <div
                          className={styles.monthMoreEvents}
                          onClick={(e) => { e.stopPropagation(); setSelectedDate(d.date); setViewMode("day"); }}
                        >
                          +{hiddenCount} thêm
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
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
                  const programName = getProgramNameFromId(updated.program);
                  updated.title = `${updated.class_name || ""} - ${updated.teacher || ""} - ${programName}`.trim();
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
                  const programName = getProgramNameFromId(updated.program);
                  updated.title = `${updated.class_name || ""} - ${updated.teacher || ""} - ${programName}`.trim();
                  setNewEvent(updated);
                }}
              />
            </label>

            <label>
              Chương trình:
              <div className={styles.programContainer}>
                <select
                  value={newEvent.program}
                  onChange={(e) => {
                    const updated = { ...newEvent, program: e.target.value };
                    const programName = getProgramNameFromId(updated.program);
                    updated.title = `${updated.class_name || ""} - ${updated.teacher || ""} - ${programName}`.trim();
                    setNewEvent(updated);
                  }}
                  className={styles.programSelect}
                >
                  <option value="" disabled hidden>-- Chọn chương trình --</option>
                  {programOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className={styles.manageBtn}
                  onClick={() => setShowProgramModal(true)}
                  title="Thêm/sửa/xoá chương trình"
                >
                  ⚙️ Quản lý
                </button>
              </div>
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
                  
                  // Tạo bản sao của state hiện tại
                  const updatedEvent = { ...newEvent, recurrence: val };
                  
                  // Reset các count về 1 khi đổi loại recurrence
                  if (val === "WEEKLY") {
                    updatedEvent.week_count = 1;
                    updatedEvent.repeat_count = updatedEvent.byday?.length || 1;
                  } else if (val === "MONTHLY") {
                    updatedEvent.month_count = 1;
                    updatedEvent.repeat_count = updatedEvent.bymonthday?.length || 1;
                  } else if (val === "YEARLY") {
                    updatedEvent.year_count = 1;
                    updatedEvent.repeat_count = updatedEvent.bymonthday?.length || 1;
                  } else if (val === "DAILY") {
                    // Giữ nguyên repeat_count cho DAILY
                    updatedEvent.repeat_count = updatedEvent.repeat_count || 1;
                  } else {
                    // Không lặp
                    updatedEvent.repeat_count = 1;
                  }
                  
                  setNewEvent(updatedEvent);
                }}
              >
                <option value="">Không lặp</option>
                <option value="DAILY">Hàng ngày</option>
                <option value="WEEKLY">Hàng tuần</option>
                <option value="MONTHLY">Hàng tháng</option>
                <option value="YEARLY">Hàng năm</option>
              </select>
            </label>

            

            {/* PHẦN DAILY - CHỈ HIỂN THỊ KHI CHỌN DAILY */}
            {newEvent.recurrence === "DAILY" && (
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

            {/* PHẦN WEEKLY - HIỂN THỊ MỚI VỚI "Số tuần lặp lại" */}
            {newEvent.recurrence === "WEEKLY" && (
              <div className={styles.recurrenceCustomGroup}>
                <label>
                  Số tuần lặp lại:
                  <input
                    type="number"
                    min={1}
                    value={newEvent.week_count || 1}
                    onChange={(e) => {
                      const weeks = Number(e.target.value);
                      const totalEvents = weeks * (newEvent.byday?.length || 1);
                      setNewEvent(prev => ({
                        ...prev,
                        week_count: weeks,
                        repeat_count: totalEvents
                      }));
                    }}
                  />
                </label>
                {newEvent.byday?.length > 0 && (
                  <div className={styles.recurrenceNote}>
                    (Tổng cộng {newEvent.repeat_count || 1} buổi học)
                  </div>
                )}
                
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
                            // Tự động tính lại repeat_count
                            const totalEvents = newEvent.week_count * newArr.length;
                            setNewEvent(prev => ({
                              ...prev,
                              byday: newArr,
                              repeat_count: totalEvents
                            }));
                          }}
                        />
                        {day}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* PHẦN MONTHLY - HIỂN THỊ MỚI VỚI "Số tháng lặp lại" */}
            {newEvent.recurrence === "MONTHLY" && (
              <div className={styles.recurrenceCustomGroup}>
                <label>
                  Số tháng lặp lại:
                  <input
                    type="number"
                    min={1}
                    value={newEvent.month_count || 1}
                    onChange={(e) => {
                      const months = Number(e.target.value);
                      const totalEvents = months * (newEvent.bymonthday?.length || 1);
                      setNewEvent(prev => ({
                        ...prev,
                        month_count: months,
                        repeat_count: totalEvents
                      }));
                    }}
                  />
                </label>
                
                <label>
                  Ngày trong tháng (vd: 1,15,30):
                  <input
                    type="text"
                    value={newEvent._monthly_input || (Array.isArray(newEvent.bymonthday) ? newEvent.bymonthday.join(",") : "")}
                    onChange={(e) => {
                      // CHỈ lưu text tạm thời
                      setNewEvent(prev => ({
                        ...prev,
                        _monthly_input: e.target.value
                      }));
                    }}
                    onBlur={(e) => {
                      // KHI RỜI KHỎI INPUT mới parse
                      const inputValue = e.target.value.trim();
                      
                      if (!inputValue) {
                        setNewEvent(prev => ({
                          ...prev,
                          bymonthday: [],
                          _monthly_input: "",
                          repeat_count: prev.month_count * 0
                        }));
                        return;
                      }
                      
                      // Parse thành mảng số
                      const newBymonthday = inputValue
                        .split(",")
                        .map(x => {
                          const num = Number(x.trim());
                          return isNaN(num) ? null : num;
                        })
                        .filter(n => n !== null && n > 0 && n <= 31)
                        .sort((a, b) => a - b); // Sắp xếp tăng dần
                      
                      // Tự động tính lại repeat_count
                      const totalEvents = newEvent.month_count * newBymonthday.length;
                      
                      // Cập nhật state với giá trị đã cleaned
                      const cleanedInput = newBymonthday.join(",");
                      
                      setNewEvent(prev => ({
                        ...prev,
                        bymonthday: newBymonthday,
                        repeat_count: totalEvents,
                        _monthly_input: cleanedInput
                      }));
                    }}
                    placeholder="Nhập các ngày (1-31), cách nhau bằng dấu phẩy"
                  />
                </label>
                
                {newEvent.bymonthday?.length > 0 && (
                  <div className={styles.recurrenceNote}>
                    (Tổng cộng {newEvent.repeat_count || 1} buổi học - các ngày: {newEvent.bymonthday?.join(", ")})
                  </div>
                )}
                
                {/* Quick select buttons */}
                <div style={{ marginTop: '10px' }}>
                  <div style={{ fontSize: '12px', color: '#666', marginBottom: '5px' }}>Chọn nhanh:</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                    {[1, 5, 10, 15, 20, 25, 30].map(day => (
                      <button
                        key={day}
                        type="button"
                        style={{
                          padding: '4px 8px',
                          border: '1px solid #ddd',
                          borderRadius: '3px',
                          background: newEvent.bymonthday?.includes(day) ? '#4CAF50' : '#f5f5f5',
                          color: newEvent.bymonthday?.includes(day) ? '#fff' : '#333',
                          cursor: 'pointer',
                          fontSize: '12px'
                        }}
                        onClick={() => {
                          const current = newEvent.bymonthday || [];
                          let newBymonthday;
                          
                          if (current.includes(day)) {
                            newBymonthday = current.filter(d => d !== day);
                          } else {
                            newBymonthday = [...current, day].sort((a, b) => a - b);
                          }
                          
                          const totalEvents = newEvent.month_count * newBymonthday.length;
                          const cleanedInput = newBymonthday.join(",");
                          
                          setNewEvent(prev => ({
                            ...prev,
                            bymonthday: newBymonthday,
                            repeat_count: totalEvents,
                            _monthly_input: cleanedInput
                          }));
                        }}
                      >
                        {day}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* PHẦN YEARLY - CÁCH TỐT NHẤT: DÙNG onBlur để parse */}
            {newEvent.recurrence === "YEARLY" && (
              <div className={styles.recurrenceCustomGroup}>
                <label>
                  Số năm lặp lại:
                  <input
                    type="number"
                    min={1}
                    value={newEvent.year_count || 1}
                    onChange={(e) => {
                      const years = Number(e.target.value);
                      const totalEvents = years * (newEvent.bymonthday?.length || 1);
                      setNewEvent(prev => ({
                        ...prev,
                        year_count: years,
                        repeat_count: totalEvents
                      }));
                    }}
                  />
                </label>
                
                <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                  <div style={{ flex: 1 }}>
                    <label>
                      Tháng (vd: 1,6,12):
                      <input
                        type="text"
                        value={newEvent._yearly_month_input || (Array.isArray(newEvent.bymonth) ? newEvent.bymonth.join(",") : "")}
                        onChange={(e) => {
                          setNewEvent(prev => ({
                            ...prev,
                            _yearly_month_input: e.target.value
                          }));
                        }}
                        onBlur={(e) => {
                          const inputValue = e.target.value.trim();
                          
                          if (!inputValue) {
                            setNewEvent(prev => ({
                              ...prev,
                              bymonth: [],
                              _yearly_month_input: ""
                            }));
                            return;
                          }
                          
                          const newBymonth = inputValue
                            .split(",")
                            .map(x => {
                              const num = Number(x.trim());
                              return isNaN(num) ? null : num;
                            })
                            .filter(n => n !== null && n >= 1 && n <= 12)
                            .sort((a, b) => a - b);
                          
                          const cleanedInput = newBymonth.join(",");
                          
                          setNewEvent(prev => ({
                            ...prev,
                            bymonth: newBymonth,
                            _yearly_month_input: cleanedInput
                          }));
                        }}
                        placeholder="Các tháng (1-12)"
                        style={{ width: '100%' }}
                      />
                    </label>
                  </div>
                  
                  <div style={{ flex: 1 }}>
                    <label>
                      Ngày (vd: 1,15,20):
                      <input
                        type="text"
                        value={newEvent._yearly_day_input || (Array.isArray(newEvent.bymonthday) ? newEvent.bymonthday.join(",") : "")}
                        onChange={(e) => {
                          setNewEvent(prev => ({
                            ...prev,
                            _yearly_day_input: e.target.value
                          }));
                        }}
                        onBlur={(e) => {
                          const inputValue = e.target.value.trim();
                          
                          if (!inputValue) {
                            setNewEvent(prev => ({
                              ...prev,
                              bymonthday: [],
                              _yearly_day_input: "",
                              repeat_count: prev.year_count * 0
                            }));
                            return;
                          }
                          
                          const newBymonthday = inputValue
                            .split(",")
                            .map(x => {
                              const num = Number(x.trim());
                              return isNaN(num) ? null : num;
                            })
                            .filter(n => n !== null && n > 0 && n <= 31)
                            .sort((a, b) => a - b);
                          
                          const totalEvents = newEvent.year_count * newBymonthday.length;
                          const cleanedInput = newBymonthday.join(",");
                          
                          setNewEvent(prev => ({
                            ...prev,
                            bymonthday: newBymonthday,
                            repeat_count: totalEvents,
                            _yearly_day_input: cleanedInput
                          }));
                        }}
                        placeholder="Các ngày (1-31)"
                        style={{ width: '100%' }}
                      />
                    </label>
                  </div>
                </div>
                
                {/* Quick select for months */}
                <div style={{ marginBottom: '10px' }}>
                  <div style={{ fontSize: '12px', color: '#666', marginBottom: '5px' }}>Chọn tháng nhanh:</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                    {[1, 3, 6, 9, 12].map(month => (
                      <button
                        key={month}
                        type="button"
                        style={{
                          padding: '4px 8px',
                          border: '1px solid #ddd',
                          borderRadius: '3px',
                          background: newEvent.bymonth?.includes(month) ? '#4CAF50' : '#f5f5f5',
                          color: newEvent.bymonth?.includes(month) ? '#fff' : '#333',
                          cursor: 'pointer',
                          fontSize: '12px'
                        }}
                        onClick={() => {
                          const current = newEvent.bymonth || [];
                          let newBymonth;
                          
                          if (current.includes(month)) {
                            newBymonth = current.filter(m => m !== month);
                          } else {
                            newBymonth = [...current, month].sort((a, b) => a - b);
                          }
                          
                          const cleanedInput = newBymonth.join(",");
                          
                          setNewEvent(prev => ({
                            ...prev,
                            bymonth: newBymonth,
                            _yearly_month_input: cleanedInput
                          }));
                        }}
                      >
                        Tháng {month}
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Quick select for days */}
                <div style={{ marginBottom: '10px' }}>
                  <div style={{ fontSize: '12px', color: '#666', marginBottom: '5px' }}>Chọn ngày nhanh:</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                    {[1, 5, 10, 15, 20, 25, 30].map(day => (
                      <button
                        key={day}
                        type="button"
                        style={{
                          padding: '4px 8px',
                          border: '1px solid #ddd',
                          borderRadius: '3px',
                          background: newEvent.bymonthday?.includes(day) ? '#4CAF50' : '#f5f5f5',
                          color: newEvent.bymonthday?.includes(day) ? '#fff' : '#333',
                          cursor: 'pointer',
                          fontSize: '12px'
                        }}
                        onClick={() => {
                          const current = newEvent.bymonthday || [];
                          let newBymonthday;
                          
                          if (current.includes(day)) {
                            newBymonthday = current.filter(d => d !== day);
                          } else {
                            newBymonthday = [...current, day].sort((a, b) => a - b);
                          }
                          
                          const totalEvents = newEvent.year_count * newBymonthday.length;
                          const cleanedInput = newBymonthday.join(",");
                          
                          setNewEvent(prev => ({
                            ...prev,
                            bymonthday: newBymonthday,
                            repeat_count: totalEvents,
                            _yearly_day_input: cleanedInput
                          }));
                        }}
                      >
                        {day}
                      </button>
                    ))}
                  </div>
                </div>
                
                {(newEvent.bymonthday?.length > 0 || newEvent.bymonth?.length > 0) && (
                  <div className={styles.recurrenceNote}>
                    (Tổng cộng {newEvent.repeat_count || 1} buổi học)
                    {newEvent.bymonth?.length > 0 && ` - Tháng: ${newEvent.bymonth.join(", ")}`}
                    {newEvent.bymonthday?.length > 0 && ` - Ngày: ${newEvent.bymonthday.join(", ")}`}
                  </div>
                )}
              </div>
            )}

            <div className={styles.popupActions}>
              <button onClick={handleSave} className={styles.btnSave} disabled={isSaving}>
                {isSaving ? "⏳ Đang lưu..." : editingEvent ? "💾 Cập nhật" : "➕ Tạo mới"}
              </button>
              
              <button onClick={() => setShowPopup(false)} className={styles.btnCancel} disabled={isSaving}>
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ✅ PROGRAM MANAGE MODAL */}
      <ProgramManageModal
        isOpen={showProgramModal}
        onClose={() => setShowProgramModal(false)}
        onProgramsUpdate={loadPrograms}
      />
    </div>
  );
});

export default CalendarView;
