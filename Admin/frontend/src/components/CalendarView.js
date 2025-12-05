import React, { useState, useEffect, useRef } from "react";
import styles from "./CalendarView.module.css";
import { parseZoomInfo } from "../utils/sanitizeDescription";
import { getEvent } from "../services/api";
import { checkScheduleConflict } from "../services/api";
import { getTimezones } from "../services/api";

export default function CalendarView({ events, onEventClick, onDateSelect, onCreateEvent, onDeleteEvent }) {
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

  const [myCalendars, setMyCalendars] = useState([
    { id: 1, name: "Thang Nguyen", color: "#1a73e8", checked: true },
    { id: 2, name: "Sinh nhật", color: "#fbbc04", checked: true },
    { id: 3, name: "Tasks", color: "#34a853", checked: true },
    { id: 4, name: "ZenAI Tutor Schedule", color: "#ea4335", checked: true },
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

  const timeSlots = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, "0")}:00`);

  useEffect(() => {
    const fetchTimezones = async () => {
      try {
        const timezonesData = await getTimezones();
        if (timezonesData && timezonesData.timezones) {
          setTimezoneOptions(timezonesData.timezones);
        }
      } catch (error) {
        console.error("❌ Failed to fetch timezones, using default:", error);
        // Vẫn giữ default options nếu API fail
      }
    };
    
    fetchTimezones();
  }, []);

  const dailyEvents = events.filter((e) => {
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

    console.log("🔍 NORMALIZE EVENT - RECURRENCE CHECK:", {
      eventId,
      hasRecurrenceArray: Array.isArray(event.recurrence),
      recurrenceArray: event.recurrence,
      recurringEventId: event.recurringEventId
    });

    // ✅ THÊM: Extract timezone từ Google Calendar event
    const eventTimezone = event.start?.timeZone || event.end?.timeZone || "Asia/Ho_Chi_Minh";

    return {
      ...event, // ⚠️ QUAN TRỌNG: Giữ nguyên tất cả fields gốc từ API
      id: eventId,
      name: event.summary || event.name || "Không có tên",
      class_name: event.classname || event.class_name || classname || "",
      teacher: event.teacher || teacher || event.instructor || "Chưa có GV",
      program: event.program || program || event.course || "Chưa có môn",
      zoom: event.zoom_link || event.zoom || zoomLink || event.meeting_url || event.location || "",
      meeting_id: event.meeting_id || meetingId || "",
      passcode: event.passcode || passcode || "",
      
      // ✅ QUAN TRỌNG: Thêm timezone vào normalized event
      timezone: eventTimezone,
      
      // ✅ QUAN TRỌNG: Giữ nguyên recurrence data gốc
      recurrence: event.recurrence, // Giữ nguyên array nếu có
      repeat_count: event.repeat_count || 1,
      byday: event.byday || [],
      bymonthday: event.bymonthday || [],
      bymonth: event.bymonth || [],
    };
  };

  // ✅ THÊM VÀO CALENDARVIEW (sau hàm normalizeEvent)

// 1. Copy hàm parseRecurrenceRule từ AdminSchedule
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

  // 2. Copy hàm parseRecurrenceFromEvent từ AdminSchedule  
  // 2. Copy hàm parseRecurrenceFromEvent từ AdminSchedule  
  const parseRecurrenceFromEvent = async (cls) => {
    // TRƯỜNG HỢP 1: Event có recurrence trực tiếp
    if (cls.recurrence && Array.isArray(cls.recurrence) && cls.recurrence.length > 0) {
      const ruleString = cls.recurrence[0];
      return parseRecurrenceRule(ruleString);
    }

    // TRƯỜNG HỢP 2: Event là instance - tìm master event
    if (cls.recurringEventId) {
      let masterEvent = null;
      
      // Tìm trong data hiện tại trước
      masterEvent = events.find(event => event.id === cls.recurringEventId);
      if (masterEvent && masterEvent.recurrence) {
        const ruleString = masterEvent.recurrence[0];
        return parseRecurrenceRule(ruleString);
      }

      // Fetch từ API nếu không tìm thấy - ✅ SỬA: DÙNG getEvent ĐÃ IMPORT Ở ĐẦU FILE
      try {
        masterEvent = await getEvent(cls.recurringEventId); // ✅ ĐÃ IMPORT, KHÔNG CẦN dynamic import
        if (masterEvent && masterEvent.recurrence) {
          const ruleString = masterEvent.recurrence[0];
          return parseRecurrenceRule(ruleString);
        }
      } catch (error) {
        console.error("Failed to fetch master event:", error);
      }
    }

    return { recurrenceType: "", repeatCount: 1, byday: [], bymonthday: [], bymonth: [] };
  };

  // 3. Copy hàm prepareEditData từ AdminSchedule
  const prepareEditData = async (cls) => {
    const { zoomLink, meetingId, passcode, program, teacher, classname } = 
      parseZoomInfo(cls.description || "");

    // Parse recurrence data
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
      // ✅ Dùng recurrence data đã parse
      recurrence: recurrenceData.recurrenceType,
      repeat_count: recurrenceData.repeatCount,
      byday: recurrenceData.byday,
      bymonthday: recurrenceData.bymonthday,
      bymonth: recurrenceData.bymonth,
      timezone: cls.timezone || "Asia/Ho_Chi_Minh", // ✅ LẤY TIMEZONE TỪ EVENT
      recurrence_description: cls.recurrence_description || "",
    };
  };


  // ✅ HÀM TÌM MASTER EVENT TRONG DANH SÁCH EVENTS
  const findMasterEvent = (recurringEventId) => {
    if (!recurringEventId) return null;
    
    const master = events.find(event => event.id === recurringEventId);
    console.log("🔍 FIND MASTER EVENT:", {
      recurringEventId,
      found: !!master,
      masterId: master?.id,
      masterRecurrence: master?.recurrence
    });
    
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

  // Thêm hàm tạo conflict message
  const createConflictMessage = (conflictResult, currentTeacher) => {
    // 🆕 HIỂN THỊ LOẠI CHECK ĐỂ USER BIẾT
    const checkType = conflictResult.check_type || 'ai_full';
    const checkTypeText = {
      'ai_suggestions': 'AI Đề Xuất Thông Minh',
      'traditional_fast': 'Kiểm Tra Nhanh',
      'ai_full': 'AI Phân Tích'
    }[checkType] || 'AI Phân Tích';
    
    let message = `🤖 KIỂM TRA XUNG ĐỘT (${checkTypeText})\n\n`;
    
    // Hiển thị phân tích AI nếu có
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
    
    // Đề xuất thông minh từ AI
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
    
    // ✅ DETECT USER TIMEZONE THÔNG MINH HƠN
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    
    // Tìm timezone phù hợp nhất với user
    let defaultTimezone = "Asia/Ho_Chi_Minh"; // Mặc định Vietnam
    
    // Nếu user ở các timezone phổ biến khác, dùng timezone của họ
    const commonTimezones = [
      "America/Chicago", "America/New_York", "America/Los_Angeles",
      "Europe/London", "Europe/Paris", "Asia/Tokyo", "Australia/Sydney"
    ];
    
    if (commonTimezones.includes(userTimezone)) {
      defaultTimezone = userTimezone;
    }
    
    console.log(`🕐 User timezone: ${userTimezone}, using: ${defaultTimezone}`);
    
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
      timezone: defaultTimezone, // ✅ DÙNG TIMEZONE PHÙ HỢP
      recurrence_description: "",
    };

    setNewEvent(defaultEvent);
    setEditingEvent(null);
    setShowPopup(true);
  };

  const handleSave = async () => {
    console.log("🔥 DEBUG handleSave - CURRENT TIMEZONE:", {
      timezone: newEvent?.timezone,
      fullState: newEvent
    });
    if (!newEvent.title) {
      alert("Vui lòng nhập tiêu đề!");
      return;
    }
    alert("🎯 Hàm handleSave được gọi!");

    // 🚨 THÊM ALERT TEST - DÒNG NÀY  
    alert("🔍 Giáo viên: " + (newEvent.teacher || "CHƯA CÓ GIÁO VIÊN"));
    
    // 🔍 KIỂM TRA XUNG ĐỘT TRƯỚC KHI LƯU
    if (newEvent.teacher && newEvent.teacher.trim() !== "") {
      // 🚨 THÊM ALERT TEST - DÒNG NÀY
      alert("🛡️ Bắt đầu kiểm tra conflict...");
      
      try {
        console.log("🛡️ Checking for schedule conflicts...");
        
        const conflictResult = await checkScheduleConflict(
          newEvent.teacher,
          formatForBackend(newEvent.start, newEvent.timezone),
          formatForBackend(newEvent.end, newEvent.timezone),
          newEvent.id
        );

        // 🚨 THÊM ALERT TEST - DÒNG NÀY
        alert("📊 Kết quả check conflict: " + JSON.stringify(conflictResult));

        // XỬ LÝ KẾT QUẢ AI
        if (conflictResult.has_conflict) {
          const conflictMessage = createConflictMessage(conflictResult, newEvent.teacher);
          
          // NẾU CÓ ĐỀ XUẤT TỪ AI
          if (conflictResult.suggestions && conflictResult.suggestions.length > 0) {
            const userChoice = prompt(conflictMessage);
            
            if (userChoice === null) {
              // USER BẤM CANCEL - CHẶN
              alert("🚫 Đã hủy tạo lịch do trùng lịch giáo viên");
              return; 
            } else if (userChoice === '1' || userChoice === '2') {
              // USER CHỌN ĐỀ XUẤT - CHẶN (để chuyển thời gian)
              const suggestionIndex = parseInt(userChoice) - 1;
              const selectedSuggestion = conflictResult.suggestions[suggestionIndex];
              
              // TỰ ĐỘNG CẬP NHẬT THỜI GIAN
              setNewEvent(prev => ({
                ...prev,
                start: formatForInput(selectedSuggestion.start),
                end: formatForInput(selectedSuggestion.end)
              }));
              
              alert(`✅ Đã chuyển sang thời gian: ${new Date(selectedSuggestion.start).toLocaleString('vi-VN')}`);
              return; // Dừng để user xem thời gian mới
            } else if (userChoice === '') {
              // USER BẤM OK - CHO PHÉP TẠO (không return)
              alert("⚠️ Cảnh báo: Bạn vẫn tạo lịch dù có xung đột!");
              console.log("⚠️ User confirmed to create despite conflict");
              // TIẾP TỤC KHÔNG RETURN
            } else {
              // INPUT KHÔNG HỢP LỆ - CHẶN
              alert("❌ Lựa chọn không hợp lệ. Vui lòng thử lại.");
              return;
            }
          } else {
            // KHÔNG CÓ ĐỀ XUẤT
            const userConfirmed = window.confirm(conflictMessage + "\n\nBấm OK để VẪN TẠO, Cancel để HỦY");
            
            if (!userConfirmed) {
              // USER BẤM CANCEL - CHẶN
              alert("🚫 Đã hủy tạo lịch do trùng lịch giáo viên");
              return;
            }
            // USER BẤM OK - CHO PHÉP TẠO (không return)
            alert("⚠️ Cảnh báo: Bạn vẫn tạo lịch dù có xung đột!");
          }
        
        } else {
          // 🚨 THÊM ALERT TEST - DÒNG NÀY
          alert("✅ KHÔNG CÓ XUNG ĐỘT!");
          
          // KHÔNG CÓ XUNG ĐỘT, HIỂN THỊ PHÂN TÍCH AI
          if (conflictResult.ai_analysis) {
            alert(`🤖 AI Phân tích:\n${conflictResult.ai_analysis}\n\n✅ Không có xung đột!`);
          }
        }
      } catch (error) {
        // 🚨 HIỂN THỊ LỖI CHI TIẾT
          alert(`❌ LỖI CHECK CONFLICT:\n\n` +
                `Status: ${error.response?.status}\n` +
                `Message: ${error.response?.data?.detail || error.message}\n\n` +
                `Vui lòng kiểm tra console để biết thêm chi tiết.`);
          
          console.error("❌ Error during conflict check:", error.response?.data || error);
      }
    } else {
      // 🚨 THÊM ALERT TEST - DÒNG NÀY
      alert("⚠️ Bỏ qua check conflict vì không có giáo viên");
    }

    // 🔍 DEBUG TRƯỚC KHI TẠO EVENT DATA
    console.log("🔍 DEBUG BEFORE CREATING EVENT DATA:");
    console.log("newEvent.recurrence:", newEvent.recurrence);
    console.log("newEvent.repeat_count:", newEvent.repeat_count);
    console.log("newEvent.byday:", newEvent.byday);
    console.log("newEvent.bymonthday:", newEvent.bymonthday);
    console.log("newEvent.bymonth:", newEvent.bymonth);
    console.log("Full newEvent state:", newEvent);

    const startTime = new Date(newEvent.start);
    const endTime = new Date(newEvent.end);
    
    if (endTime <= startTime) {
      alert("Thời gian kết thúc phải LỚN HƠN thời gian bắt đầu!");
      return;
    }

    // 🔧 THÊM VALIDATION - kiểm tra recurrence có giá trị không
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
      recurrence: newEvent.recurrence || "",
      repeat_count: newEvent.repeat_count || 1,
      byday: newEvent.byday || [],
      bymonthday: newEvent.bymonthday || [],
      bymonth: newEvent.bymonth || [],
      start: formatForBackend(newEvent.start, finalTimezone),
      end: formatForBackend(newEvent.end, finalTimezone),
      timezone: newEvent.timezone || "Asia/Ho_Chi_Minh", // ✅ DÙNG newEvent TRỰC TIẾP
      recurrence_description: newEvent.recurrence_description || "",
      isEdit: !!editingEvent,
    };

    console.log("🎯 SAVING EVENT - FINAL DATA:", eventData);

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
              const rect = e.currentTarget.getBoundingClientRect();
              const clickY = e.clientY - rect.top;
              const hour = Math.floor(clickY / 60);
              const newStart = new Date(selectedDate);
              newStart.setHours(hour, 0, 0, 0);
              const newEnd = new Date(newStart);
              newEnd.setHours(hour + 1);
              openPopup(newStart, newEnd);
            }}
          >
            <div className={styles.timeColumn}>
              {/* Phần GMT+7 riêng */}
              <div className={styles.timezoneHeader}>
                GMT{(new Date().getTimezoneOffset() / -60) >= 0 ? '+' : ''}
                {new Date().getTimezoneOffset() / -60}
              </div>
              
              {/* Phần các giờ */}
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
                return (
                  <div
                    key={i}
                    className={styles.eventItem}
                    style={{
                      top: `${top}px`,
                      height: `${height}px`,
                      width: e.width,
                      left: e.left,
                      position: "absolute",
                    }}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      console.log("🖱️ CLICKED EVENT:", normalizedEvent);
                      setSelectedEvent(normalizedEvent);
                      setShowDetailPopup(true);
                    }}
                  >
                    <div className={styles.eventName}>{normalizedEvent.name}</div>
                    <div className={styles.eventTeacher}>{normalizedEvent.teacher}</div>
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

      {showDetailPopup && selectedEvent && (
        <div className={styles.popupOverlay}>
          <div className={styles.detailPopup}>
            <h3>{selectedEvent.name}</h3>

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

            {/* ✅ HIỂN THỊ TIMEZONE THÔNG MINH */}
            <p>
              <b>Múi giờ:</b> {
                (() => {
                  // Lấy timezone từ nhiều nguồn khác nhau
                  const eventTimezone = selectedEvent.timezone || 
                                      selectedEvent.start?.timeZone || 
                                      selectedEvent.end?.timeZone ||
                                      "Asia/Ho_Chi_Minh";
                  
                  // Tìm label trong options
                  const timezoneOption = timezoneOptions.find(tz => tz.value === eventTimezone);
                  
                  // Nếu không tìm thấy, hiển thị giá trị gốc
                  return timezoneOption ? timezoneOption.label : eventTimezone;
                })()
              }
            </p>

            {/* ✅ THÊM RECURRENCE DESCRIPTION Ở ĐÂY */}
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
                {/* LUÔN PARSE RECURRENCE DATA MỚI NHẤT */}
                {(() => {
                  // ❌ KHÔNG THỂ DÙNG ASYNC TRONG JSX - HIỂN THỊ TỪ NORMALIZED EVENT
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
                    recurrence: recurrenceData.recurrenceType,  // ✅ DÙNG recurrenceType
                    repeat_count: recurrenceData.repeatCount,        // ← SỬA Ở ĐÂY
                    byday: recurrenceData.byday,                     // ← SỬA Ở ĐÂY
                    bymonthday: recurrenceData.bymonthday,           // ← SỬA Ở ĐÂY
                    bymonth: recurrenceData.bymonth,      
                    start: formatForInput(selectedEvent.start?.dateTime || selectedEvent.start),
                    end: formatForInput(selectedEvent.end?.dateTime || selectedEvent.end),
                    timezone: selectedEvent.timezone || "Asia/Ho_Chi_Minh",
                    recurrence_description: selectedEvent.recurrence_description || "", 
                  };

                  setNewEvent(editEventData);
                  setEditingEvent(selectedEvent);
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
            <h3>🗓️ {editingEvent ? `Chỉnh sửa: ${newEvent.title}` : "Thêm sự kiện mới"}</h3>

            <div style={{ fontSize: '12px', color: '#666', marginBottom: '10px', padding: '5px', border: '1px solid #ccc', background: '#f9f9f9' }}>
              <div><strong>DEBUG RECURRENCE STATE:</strong></div>
              <div>recurrence: "{newEvent.recurrence}"</div>
              <div>repeat_count: {newEvent.repeat_count}</div>
              <div>byday: [{newEvent.byday?.join(", ") || "none"}]</div>
              <div>bymonthday: [{newEvent.bymonthday?.join(", ") || "none"}]</div>
              <div>bymonth: [{newEvent.bymonth?.join(", ") || "none"}]</div>
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
              <input
                type="text"
                value={newEvent.program}
                onChange={(e) => {
                  const updated = { ...newEvent, program: e.target.value };
                  updated.title = `${updated.class_name || ""} - ${updated.teacher || ""} - ${updated.program || ""}`.trim();
                  setNewEvent(updated);
                }}
              />
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
                  onChange={(e) => handleDateTimeChange('start', e.target.value)}
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
                    // ✅ ĐẢM BẢO MẢNG LUÔN LÀ MẢNG
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
              {/* ✅ BUTTON DEBUG */}
              <button 
                type="button"
                onClick={() => console.log("🔍 DEBUG BUTTON - CURRENT STATE:", newEvent)}
                style={{background: 'orange'}}
              >
                🔍 Debug State
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