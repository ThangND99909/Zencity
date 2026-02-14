// frontend/src/pages/AdminSchedule.js
import React, { useEffect, useState, useRef } from "react";
import { getClasses, addClass, updateClass, deleteClass, suggestClass, getEvent } from "../services/api";
import ClassTable from "../components/ClassTable";
import ClassForm from "../components/ClassForm";
import CalendarView from "../components/CalendarView";
import styles from "./AdminSchedule.module.css";
import { parseZoomInfo } from "../utils/sanitizeDescription";
import LoadingOverlay from '../components/LoadingOverlay';
import PasscodeModal from "../components/PasscodeModal";
//import logo from '../assets/logo.png';

const CORRECT_PASSCODE = "1234"; // 🔐 Thay đổi passcode của bạn tại đây

export default function AdminSchedule() {
  const [classes, setClasses] = useState([]);
  const [editingClass, setEditingClass] = useState(null);
  const [creatingClass, setCreatingClass] = useState(null);
  const [showCalendar, setShowCalendar] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingType, setLoadingType] = useState('default');
  const [loadingMessage, setLoadingMessage] = useState('');
  const [editLoading, setEditLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [calendarFilter, setCalendarFilter] = useState('both'); // 'odd', 'even', 'both'
  const [isPasscodeVerified, setIsPasscodeVerified] = useState(false);
  const [showPasscodeModal, setShowPasscodeModal] = useState(true);

  // ✅ THÊM REF CHO CALENDAR VIEW
  const calendarViewRef = useRef(null);

  // Hàm show loading
  const showLoading = (type = 'default', customMessage = '') => {
    setLoadingType(type);
    if (customMessage) {
      setLoadingMessage(customMessage);
    }
    setLoading(true);
  };

  const hideLoading = () => {
    setLoading(false);
    setLoadingMessage('');
  };

  // 🔐 Xử lý xác thực passcode
  const handlePasscodeSubmit = async (inputPasscode) => {
    // Giả lập delay để tạo cảm giác như đang kiểm tra
    await new Promise(resolve => setTimeout(resolve, 500));
    
    if (inputPasscode === CORRECT_PASSCODE) {
      setIsPasscodeVerified(true);
      setShowPasscodeModal(false);
      return { success: true, message: "Passcode chính xác" };
    } else {
      return { success: false, message: "Passcode không chính xác" };
    }
  };

  const loadClasses = async (filter = calendarFilter) => {
    try {
      showLoading('classes');
      setError(null);
      
      // ✅ THÊM PARAMETER calendar_type
      const data = await getClasses(filter);
      
      // ✅ THÊM DEBUG CHI TIẾT RECURRENCE VÀ CALENDAR DATA
      console.log("📦 FULL API RESPONSE STRUCTURE:", data);
      
      if (data && data.length > 0) {
        // Phân tích calendar source
        const oddEvents = data.filter(event => event._calendar_source === 'odd');
        const evenEvents = data.filter(event => event._calendar_source === 'even');
        const unknownEvents = data.filter(event => !event._calendar_source);
        
        
        // Tìm events có recurrence
        const eventsWithRecurrence = data.filter(event => event.recurrence);
        const recurringInstances = data.filter(event => event.recurringEventId);
        
        console.log("🔄 RECURRENCE STATS:", {
          masterEvents: eventsWithRecurrence.length,
          instances: recurringInstances.length
        });
      }
      
      setClasses(data);
    } catch (err) {
      setError("Failed to load classes: " + err.message);
      console.error("Load classes error:", err);
    } finally {
      hideLoading();
    }
  };

  // 🔐 Chỉ load data khi đã xác thực passcode
  useEffect(() => {
    if (isPasscodeVerified) {
      loadClasses();
    }
  }, [isPasscodeVerified]);

  const showMessage = (message, type = "error") => {
    if (type === "error") {
      setError(message);
      setSuccess(null);
    } else {
      setSuccess(message);
      setError(null);
    }
    setTimeout(() => {
      setError(null);
      setSuccess(null);
    }, 5000);
  };

  

  const handleAdd = async (data) => {
    try {
      showLoading('add');
      const createResponse = await addClass({
        name: data.name,
        classname: data.classname || "",
        teacher: data.teacher || "",
        zoom_link: data.zoom_link || "",
        program: data.program || "",
        start: data.start,
        end: data.end,
        meeting_id: data.meeting_id || "",
        passcode: data.passcode || "",
        recurrence: data.recurrence || "",
        repeat_count: data.repeat_count || 1,
        byday: data.byday || [],
        bymonthday: data.bymonthday || [],
        bymonth: data.bymonth || [],
        timezone: data.timezone || "Asia/Ho_Chi_Minh"
      });
      await loadClasses(calendarFilter);
      setCreatingClass(null);
      
      // ✅ SHOW CALENDAR TỚI TRƯỚC ĐỂ ĐỢI RENDER
      if (!showCalendar) {
        setShowCalendar(true);
      }
      
      // ✅ SAU ĐÓ GỌI SCROLL (ĐỢI STATE UPDATE VÀ CALENDAR REFRESH)
      setTimeout(() => {
        if (calendarViewRef.current && createResponse) {
          console.log("📞 Calling scrollToEvent from handleAdd");
          // ✅ PROPERLY EXTRACT START TIME FROM API RESPONSE
          let eventStartTime = null;
          
          // Handle Google Calendar format {dateTime: "...", date: "..."}
          if (createResponse.start && typeof createResponse.start === 'object') {
            eventStartTime = createResponse.start.dateTime || createResponse.start.date;
          } else if (createResponse.start && typeof createResponse.start === 'string') {
            eventStartTime = createResponse.start;
          } else if (data.start) {
            // Fallback to original data
            eventStartTime = data.start;
          }
          
          console.log("📍 Using event start time for scroll:", eventStartTime);
          if (eventStartTime) {
            calendarViewRef.current.scrollToEvent(eventStartTime);
          } else {
            console.warn("⚠️ Could not extract event start time from response");
          }
        }
      }, 300); // Increased delay to ensure loadClasses completes
      
      setTimeout(() => {
        showMessage("Class added successfully! 🎉", "success");
      }, 400);
    } catch (err) {
      showMessage("Failed to add class: " + err.message);
    } finally {
      hideLoading();
    }
  };

  // frontend/src/pages/AdminSchedule.js

  const handleUpdate = async (data) => {
    try {
      showLoading('update');
      const id = data.id || editingClass?.id;
      const editMode = data.edit_mode || data.editMode || 'this';
      
      
      Object.keys(data).forEach(key => {
        if (key.startsWith('_') || key.includes('mode') || key.includes('instance')) {
          console.log(`   - ${key}: ${JSON.stringify(data[key])}`);
        }
      });

      // GOOGLE CALENDAR: If 'all' mode on instance, use master ID
      const targetId = id;
      
      
      // ĐẢM BẢO EDIT_MODE ĐƯỢC TRUYỀN ĐÚNG
      const updateData = {
        ...data,
        edit_mode: editMode  // CRITICAL! Đảm bảo tên đúng
      };
      
      

      // Call API with edit_mode
      await updateClass(targetId, updateData);
      
      await loadClasses(calendarFilter);
      setEditingClass(null);
      
      // Success message theo mode
      let message = "Cập nhật thành công!";
      if (editMode === 'following') {
        message = "Đã cập nhật sự kiện này và các sự kiện tiếp theo!";
      }
      
      showMessage(message, "success");
      
    } catch (err) {
      console.error("❌ Update error details:", {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status
      });
      showMessage("Lỗi cập nhật: " + err.message);
    } finally {
      hideLoading();
    }
  };

  const handleDelete = async (eventData) => {
    try {
      showLoading('delete');
      console.log("🔥 HANDLE DELETE CALLED - FULL DATA:", eventData);
      
      // **FIX: Xử lý cả string và object**
      let eventId;
      let deleteMode = 'this';
      
      if (typeof eventData === 'string') {
        // Trường hợp cũ: chỉ có ID
        eventId = eventData;
        console.log("⚠️ Legacy string format, using default deleteMode: 'this'");
      } else if (typeof eventData === 'object') {
        // Trường hợp mới: có object với deleteMode
        eventId = eventData.id;
        deleteMode = eventData.deleteMode || 'this';
        
        console.log("✅ Object format detected:", {
          eventId,
          deleteMode,
          hasRecurrence: eventData.recurrence,
          hasRecurringEventId: eventData.recurringEventId
        });
      }
      
      if (!eventId) {
        showMessage("Cannot delete: Missing ID");
        return;
      }
      
      console.log("🎯 FINAL DELETE PARAMS:", { eventId, deleteMode });
      
      // Xác nhận với người dùng dựa trên mode
      let confirmationMessage = "";
      
      switch(deleteMode) {
        case 'all':
          confirmationMessage = "Bạn có chắc muốn xóa TOÀN BỘ chuỗi sự kiện lặp lại?";
          break;
        case 'following':
          confirmationMessage = "Bạn có chắc muốn xóa sự kiện này VÀ TẤT CẢ sự kiện sau nó trong chuỗi?";
          break;
        default:
          confirmationMessage = "Bạn có chắc chắn muốn xóa sự kiện này?";
      }
      
      if (!window.confirm(confirmationMessage)) {
        return;
      }
      
      // Gọi API xóa với mode tương ứng
      const result = await deleteClass(eventId, deleteMode);
      
      console.log("🗑️ Delete result:", result);
      
      // Reload data
      await loadClasses(calendarFilter);
      
      // Hiển thị thông báo thành công
      showMessage("✅ Đã xóa sự kiện thành công!", "success");
      
    } catch (err) {
      console.error("❌ Delete error:", err);
      showMessage("Failed to delete class: " + err.message);
    } finally {
      hideLoading();
    }
  };

  const handleCancelEdit = () => {
    setEditingClass(null);
    setCreatingClass(null);
  };

  const handleRefresh = async () => {
    try {
      // Load classes trước
      await loadClasses(calendarFilter);
      
      // Delay một chút để loading ẩn đi rồi mới hiển thị thông báo
      setTimeout(() => {
        showMessage("Classes refreshed successfully!", "success");
      }, 100); // Delay 100ms
      
    } catch (err) {
      showMessage("Refresh failed: " + err.message, "error");
    }
  };

  // ✅ HÀM CHUẨN: Parse recurrence rule
  const parseRecurrenceRule = (ruleString) => {
    if (!ruleString) {
      console.log("❌ No rule string to parse");
      return { recurrenceType: "", repeatCount: 1, byday: [], bymonthday: [], bymonth: [] };
    }
    
    console.log("🎯 Parsing recurrence rule:", ruleString);
    
    let recurrenceType = "";
    let repeatCount = 1;
    let byday = [];
    let bymonthday = [];
    let bymonth = [];

    // FREQ - Tần suất lặp
    const freqMatch = ruleString.match(/FREQ=(DAILY|WEEKLY|MONTHLY|YEARLY)/i);
    recurrenceType = freqMatch ? freqMatch[1] : "";
    
    // COUNT - Số lần lặp
    const countMatch = ruleString.match(/COUNT=(\d+)/i);
    repeatCount = countMatch ? parseInt(countMatch[1]) : 1;

    // BYDAY - Các ngày trong tuần (cho WEEKLY)
    const bydayMatch = ruleString.match(/BYDAY=([A-Z,]+)/i);
    byday = bydayMatch ? bydayMatch[1].split(",") : [];

    // BYMONTHDAY - Các ngày trong tháng (cho MONTHLY)
    const bymonthdayMatch = ruleString.match(/BYMONTHDAY=([\d,-]+)/i);
    bymonthday = bymonthdayMatch 
      ? bymonthdayMatch[1].split(",").map(Number).filter(n => !isNaN(n))
      : [];

    // BYMONTH - Các tháng (cho YEARLY)
    const bymonthMatch = ruleString.match(/BYMONTH=([\d,]+)/i);
    bymonth = bymonthMatch 
      ? bymonthMatch[1].split(",").map(Number).filter(n => !isNaN(n))
      : [];

    console.log("✅ Parsed recurrence result:", {
      recurrenceType,
      repeatCount,
      byday,
      bymonthday,
      bymonth
    });

    return { recurrenceType, repeatCount, byday, bymonthday, bymonth };
  };

  // ✅ HÀM CẢI THIỆN: Parse recurrence từ event với fallback
  const parseRecurrenceFromEvent = async (cls) => {
    console.log("🔍 Checking event for recurrence:", {
      id: cls.id,
      summary: cls.summary,
      hasRecurrence: !!cls.recurrence,
      recurrence: cls.recurrence,
      recurringEventId: cls.recurringEventId
    });

    // TRƯỜNG HỢP 1: Event có recurrence trực tiếp
    if (cls.recurrence && Array.isArray(cls.recurrence) && cls.recurrence.length > 0) {
      const ruleString = cls.recurrence[0];
      console.log("✅ Using direct recurrence rule from event");
      return parseRecurrenceRule(ruleString);
    }

    // TRƯỜNG HỢP 2: Event là instance - tìm master event
    if (cls.recurringEventId) {
      console.log("🔄 This is recurring instance, master ID:", cls.recurringEventId);
      
      let masterEvent = null;
      
      // Cách 1: Tìm trong data hiện tại trước
      masterEvent = classes.find(event => event.id === cls.recurringEventId);
      if (masterEvent && masterEvent.recurrence) {
        console.log("✅ Found master event in current data");
        const ruleString = masterEvent.recurrence[0];
        return parseRecurrenceRule(ruleString);
      }

      // Cách 2: Fetch từ API nếu không tìm thấy
      console.log("🔄 Master not found in current data, fetching from API...");
      try {
        masterEvent = await getEvent(cls.recurringEventId);
        if (masterEvent && masterEvent.recurrence) {
          console.log("✅ Found master event via API");
          const ruleString = masterEvent.recurrence[0];
          return parseRecurrenceRule(ruleString);
        } else {
          console.log("❌ Master event found but no recurrence data");
        }
      } catch (error) {
        console.error("❌ Failed to fetch master event:", error);
      }
    }

    console.log("❌ No recurrence data available, using defaults");
    return { recurrenceType: "", repeatCount: 1, byday: [], bymonthday: [], bymonth: [] };
  };

  // ✅ HÀM CHUẨN: Prepare edit data
  const prepareEditData = async (cls, includeTimezone = false) => {
    console.log("🧩 Preparing edit data for event:", {
      id: cls.id,
      summary: cls.summary,
      recurrence: cls.recurrence,
      recurringEventId: cls.recurringEventId,
      calendarSource: cls._calendar_source
    });

    const { zoomLink, meetingId, passcode, program, teacher, classname } = 
      parseZoomInfo(cls.description || "");

    // Parse recurrence data
    const recurrenceData = await parseRecurrenceFromEvent(cls);
    const eventTimezone = includeTimezone 
      ? cls.start?.timeZone || cls.end?.timeZone || cls.timezone || "Asia/Ho_Chi_Minh"
      : undefined;

    console.log("✅ Final edit data with recurrence:", {
      recurrence: recurrenceData.recurrenceType,
      repeatCount: recurrenceData.repeatCount,
      byday: recurrenceData.byday
    });

    const baseData = {
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
      calendar_source: cls._calendar_source || 'odd', // Thêm calendar source
    };

    // ✅ THÊM TIMEZONE CHỈ KHI ĐƯỢC YÊU CẦU
    if (includeTimezone) {
      baseData.timezone = eventTimezone;
      baseData.recurrence_description = cls.recurrence_description || "";
    }

    return baseData;
  };

  // ✅ HÀM CHUẨN: Handle edit với error handling
  const handleEdit = async (cls) => {
    try {
      setEditLoading(true);
      console.log("✏️ Starting edit process for:", cls.summary);
      
      const editData = await prepareEditData(cls, true);
      setEditingClass(editData);
      setCreatingClass(null);
      setShowCalendar(false);
      
      // Tự động scroll lên đầu form
      setTimeout(() => {
        const formElement = document.querySelector(`.${styles.formBox}`);
        if (formElement) {
          formElement.scrollIntoView({ behavior: "smooth", block: "start" });
        } else {
          window.scrollTo({ top: 0, behavior: "smooth" });
        }
      }, 100);
    } catch (err) {
      console.error("❌ Error preparing edit data:", err);
      showMessage("Failed to load event data: " + err.message);
    } finally {
      setEditLoading(false);
    }
  };

  const handleEventClick = (event) => {
    if (!event) return;

    if (event.delete) {
      if (window.confirm(`Bạn có chắc muốn xóa lớp "${event.summary}" không?`)) {
        handleDelete(event.id);
      }
      return;
    }

    handleEdit(event);
  };

  const handleDateSelect = (selectInfo) => {
    const startTime = selectInfo.start.toISOString();
    const endTime = selectInfo.end.toISOString();
    setCreatingClass({
      name: "New Class",
      teacher: "",
      zoom_link: "",
      meeting_id: "",
      passcode: "",
      program: "",
      start: startTime,
      end: endTime,
    });
    setEditingClass(null);
    setShowCalendar(false);
  };

  const isEditing = !!editingClass;
  const isCreating = !!creatingClass;
  const showForm = isEditing || isCreating;
  const formData = editingClass || creatingClass;

  return (
    <div className={styles.container}>
      {/* 🔐 Passcode Modal */}
      <PasscodeModal 
        isOpen={showPasscodeModal} 
        onSubmit={handlePasscodeSubmit}
      />

      {/* Ẩn toàn bộ giao diện khi chưa xác thực passcode */}
      {!isPasscodeVerified ? (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: '#f5f5f5',
          zIndex: 998,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center'
        }}>
          <div style={{ textAlign: 'center', color: '#999' }}>
            <h2>Vui lòng nhập passcode để tiếp tục</h2>
          </div>
        </div>
      ) : (
        <>
      <LoadingOverlay 
        isLoading={loading}
        type={loadingType}
        message={loadingMessage}
      />
      <div className={styles.headerWithLogo}>
        <img src="/assets/logo.png" alt="Smart Calendar Logo" className={styles.logo} />
        <h1 className={styles.mainTitle}>
          Admin Schedule Management
        </h1>
      </div>

      {success && (
        <div className={`${styles.elegantNotify} ${styles.elegantSuccess}`}>
          <div className={styles.elegantIcon}>✓</div>
          <div className={styles.elegantText}>{success}</div>
          <div className={styles.elegantSubtext}>Đã hoàn thành</div>
          <button className={styles.elegantClose} onClick={() => setSuccess(null)}>
            ×
          </button>
        </div>
      )}

      {error && (
        <div className={`${styles.elegantNotify} ${styles.elegantError}`}>
          <div className={styles.elegantIcon}>⚠</div>
          <div className={styles.elegantText}>{error}</div>
          <div className={styles.elegantSubtext}>Vui lòng kiểm tra lại</div>
          <button className={styles.elegantClose} onClick={() => setError(null)}>
            ×
          </button>
        </div>
      )}
      
      {editLoading && (
        <div className={styles.loading}>🔄 Loading recurrence data...</div>
      )}

      <div className={styles.controlBar}>
        {/* ✅ THÊM CALENDAR FILTER */}
        <div className={styles.calendarFilter}>
          <label>📅 Calendar: </label>
          <select 
            value={calendarFilter}
            onChange={(e) => {
              const newFilter = e.target.value;
              setCalendarFilter(newFilter);
              loadClasses(newFilter);
            }}
            className={styles.filterSelect}
          >
            <option value="both">📊 Cả hai Calendar</option>
            <option value="odd">📘 Calendar Lẻ (Giờ lẻ: 1,3,5...)</option>
            <option value="even">📗 Calendar Chẵn (Giờ chẵn: 2,4,6...)</option>
          </select>
        </div>

        <button
          className={`${styles.btn} ${styles.btnToggleCalendar}`}
          onClick={() => {
            setEditingClass(null);
            setCreatingClass(null);
            setShowCalendar(!showCalendar);
          }}
        >
          {showCalendar ? "📅 Hide Calendar" : "📅 Show Calendar"}
        </button>

        
        <button className={`${styles.btn} ${styles.btnRefresh}`} onClick={handleRefresh}>
          <span className={styles.refreshIcon}>🔄</span> Refresh
        </button>
        
        
        
        {showForm && (
          <button className={`${styles.btn} ${styles.btnDanger}`} onClick={handleCancelEdit}>
            ❌ Cancel {isEditing ? "Edit" : "Create"}
          </button>
        )}
      </div>

      {/* ✅ THÊM CALENDAR INFO BANNER */}
      <div className={styles.calendarInfo}>
        <div className={styles.calendarBadgeOdd}>
          📘 Calendar Lẻ: {classes.filter(e => e._calendar_source === 'odd').length} events
        </div>
        <div className={styles.calendarBadgeEven}>
          📗 Calendar Chẵn: {classes.filter(e => e._calendar_source === 'even').length} events
        </div>
        <div className={styles.calendarNote}>
          ℹ️ Events sẽ tự động được phân vào calendar dựa trên giờ bắt đầu (chẵn/lẻ)
        </div>
      </div>

      <div className={styles.mainContent}>
        {showCalendar ? (
          <div className={styles.calendarWrapper}>
            <CalendarView
              ref={calendarViewRef}
              events={classes}
              onEventClick={handleEventClick}
              onCreateEvent={(event) => {
                if (event.id) {
                  handleUpdate(event);
                } else {
                  handleAdd(event);
                }
              }}
              onDeleteEvent={handleDelete}
              onDateSelect={handleDateSelect}
              highlightedSlot={creatingClass}
              calendarFilter={calendarFilter}
            />
          </div>
        ) : (
          <div className={styles.tableWrapper}>
            {showForm && (
              <div className={styles.formBox}>
                
                <ClassForm
                  initialData={formData}
                  onSubmit={isEditing ? handleUpdate : handleAdd}
                  onCancel={handleCancelEdit}
                />
              </div>
            )}
            <div>
              <h2>Class List ({classes.length} classes)</h2>
              {classes.length === 0 ? (
                <div className={styles.emptyBox}>No classes found. Create your first class!</div>
              ) : (
                <ClassTable 
                  classes={classes} 
                  onEdit={handleEdit} 
                  onDelete={handleDelete} 
                  calendarFilter={calendarFilter}
                />
              )}
            </div>
          </div>
        )}
      </div>

      <div className={styles.footer}>
        📊 Total: {classes.length} classes • 
        Calendar: {calendarFilter === 'both' ? 'Both' : calendarFilter === 'odd' ? 'ODD' : 'EVEN'} • 
        {showForm && (isEditing ? "Editing Mode" : "Creating Mode")} • 
        Last updated: {new Date().toLocaleTimeString()}
      </div>
        </>
      )}
    </div>
  );
}