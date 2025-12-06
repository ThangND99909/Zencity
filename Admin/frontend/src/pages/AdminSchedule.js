// frontend/src/pages/AdminSchedule.js
import React, { useEffect, useState } from "react";
import { getClasses, addClass, updateClass, deleteClass, suggestClass, getEvent } from "../services/api";
import ClassTable from "../components/ClassTable";
import ClassForm from "../components/ClassForm";
import CalendarView from "../components/CalendarView";
import styles from "./AdminSchedule.module.css";
import { parseZoomInfo } from "../utils/sanitizeDescription";

export default function AdminSchedule() {
  const [classes, setClasses] = useState([]);
  const [editingClass, setEditingClass] = useState(null);
  const [creatingClass, setCreatingClass] = useState(null);
  const [showCalendar, setShowCalendar] = useState(false);
  const [loading, setLoading] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [calendarFilter, setCalendarFilter] = useState('both'); // 'odd', 'even', 'both'

  const loadClasses = async (filter = calendarFilter) => {
    try {
      setLoading(true);
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
        
        console.log("📊 CALENDAR STATS:", {
          totalEvents: data.length,
          oddCalendar: oddEvents.length,
          evenCalendar: evenEvents.length,
          unknownSource: unknownEvents.length
        });
        
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
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClasses();
  }, []);

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

  const handleAISuggest = async () => {
    try {
      const teacher = prompt("Teacher (optional):");
      const durationInput = prompt("Duration in hours (default: 1):", "1");
      const duration_hours = parseInt(durationInput) || 1;

      const data = await suggestClass(teacher, duration_hours);
      if (!data || data.error) {
        showMessage("AI Suggestion Error: " + (data?.error || "No response from server."));
        return;
      }

      setCreatingClass({
        name: "New Class",
        teacher: teacher || "",
        zoom_link: "",
        meeting_id: "",
        passcode: "",
        program: "",
        start: data.start,
        end: data.end,
      });
      setEditingClass(null);
      setShowCalendar(false);
      showMessage("AI suggestion loaded! Please review and save.", "success");
    } catch (err) {
      showMessage("AI Suggestion failed: " + err.message);
    }
  };

  const handleAdd = async (data) => {
    try {
      await addClass({
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
      showMessage("Class added successfully!", "success");
    } catch (err) {
      showMessage("Failed to add class: " + err.message);
    }
  };

  const handleUpdate = async (data) => {
    try {
      const id = data.id || editingClass?.id;
      if (!id) {
        showMessage("Cannot update: Missing event ID.");
        return;
      }

      await updateClass(id, {
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
      setEditingClass(null);
      showMessage("Class updated successfully!", "success");
    } catch (err) {
      showMessage("Failed to update class: " + err.message);
    }
  };

  const handleDelete = async (id) => {
    if (!id) {
      showMessage("Cannot delete: Missing ID");
      return;
    }
    if (window.confirm("Are you sure you want to delete this class?")) {
      try {
        await deleteClass(id);
        await loadClasses(calendarFilter);
        showMessage("Class deleted successfully!", "success");
      } catch (err) {
        showMessage("Failed to delete class: " + err.message);
      }
    }
  };

  const handleCancelEdit = () => {
    setEditingClass(null);
    setCreatingClass(null);
  };

  const handleRefresh = () => {
    loadClasses(calendarFilter);
    showMessage("Classes refreshed!", "success");
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
      <h1>📚 Admin Schedule Management</h1>

      {error && (
        <div className={`${styles.alert} ${styles.alertError}`}>
          ⚠️ {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}
      {success && (
        <div className={`${styles.alert} ${styles.alertSuccess}`}>
          ✅ {success}
          <button onClick={() => setSuccess(null)}>×</button>
        </div>
      )}
      {loading && <div className={styles.loading}>🔄 Loading classes...</div>}
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
          className={`${styles.btn} ${showCalendar ? styles.btnSecondary : styles.btnPrimary}`}
          onClick={() => {
            setEditingClass(null);
            setCreatingClass(null);
            setShowCalendar(!showCalendar);
          }}
        >
          {showCalendar ? "📅 Hide Calendar" : "📅 Show Calendar"}
        </button>

        
        <button className={`${styles.btn} ${styles.btnInfo}`} onClick={handleRefresh}>
          🔄 Refresh
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
              events={classes}
              onEventClick={handleEventClick}
              onCreateEvent={(event) => {
                if (event.id) {
                  handleUpdate(event);
                } else {
                  handleAdd(event);
                }
              }}
              onDeleteEvent={(event) => handleDelete(event.id)}
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
    </div>
  );
}