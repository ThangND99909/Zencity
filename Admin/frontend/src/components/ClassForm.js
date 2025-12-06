// frontend/src/components/ClassForm.js
import React, { useState, useEffect } from "react";
import styles from "./ClassForm.module.css";

export default function ClassForm({ onSubmit, initialData, onCancel }) {
  const [classData, setClassData] = useState({
    name: "",
    classname: "",
    teacher: "",
    zoom_link: "",
    meeting_id: "",
    passcode: "",
    program: "",
    start: "",
    end: "",
    recurrence: "",       // loại lặp
    repeat_count: 1,      // số lần lặp
    byday: [],            // các ngày trong tuần cho WEEKLY
    bymonthday: [],       // các ngày trong tháng cho MONTHLY/YEARLY
    bymonth: [],          // tháng cho YEARLY
    timezone: "Asia/Ho_Chi_Minh",
  });

  // ✅ THÊM STATE CHO CALENDAR INFO
  const [calendarInfo, setCalendarInfo] = useState({
    source: "odd",
    name: "📘 Calendar Lẻ",
    color: "#1a73e8",
    badge: "📘",
    hourType: "odd", // 'odd' hoặc 'even'
  });

  // ✅ TIMEZONE OPTIONS
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

  // ✅ HÀM XÁC ĐỊNH CALENDAR TỪ GIỜ
  const determineCalendarByHour = (hour) => {
    return hour % 2 === 0 ? "even" : "odd";
  };

  // ✅ HÀM CẬP NHẬT CALENDAR INFO
  const updateCalendarInfo = (hour) => {
    const hourType = determineCalendarByHour(hour);
    const calendarSource = hourType === "even" ? "even" : "odd";
    
    setCalendarInfo({
      source: calendarSource,
      name: calendarSource === "odd" ? "Calendar Lẻ" : "Calendar Chẵn",
      color: calendarSource === "odd" ? "#1a73e8" : "#34a853",
      badge: calendarSource === "odd" ? "📘" : "📗",
      hourType: hourType,
    });
  };

  // ✅ HÀM XỬ LÝ GIỜ BẮT ĐẦU THAY ĐỔI
  const handleStartTimeChange = (datetimeLocal) => {
    if (datetimeLocal) {
      const date = new Date(datetimeLocal);
      const hour = date.getHours();
      updateCalendarInfo(hour);
      
      // Cập nhật classData với giờ mới
      setClassData(prev => ({
        ...prev,
        start: datetimeLocal
      }));
      
      // Tự động điều chỉnh end time nếu cần
      if (classData.end) {
        const endDate = new Date(classData.end);
        const startDate = new Date(datetimeLocal);
        
        if (endDate <= startDate) {
          const newEnd = new Date(startDate.getTime() + 60 * 60 * 1000); // +1 hour
          setClassData(prev => ({
            ...prev,
            end: formatForDateTimeLocal(newEnd.toISOString())
          }));
        }
      } else {
        // Nếu chưa có end time, set mặc định +1 hour
        const startDate = new Date(datetimeLocal);
        const newEnd = new Date(startDate.getTime() + 60 * 60 * 1000);
        setClassData(prev => ({
          ...prev,
          end: formatForDateTimeLocal(newEnd.toISOString())
        }));
      }
    }
  };

  // Populate form nếu có initialData
  useEffect(() => {
    if (initialData) {
      const formattedData = {
        ...initialData,
        classname: initialData.classname || "",
        start: initialData.start ? formatForDateTimeLocal(initialData.start) : "",
        end: initialData.end ? formatForDateTimeLocal(initialData.end) : "",
        meeting_id: initialData.meeting_id || "",
        passcode: initialData.passcode || "",
        recurrence: initialData.recurrence || "",
        repeat_count: initialData.repeat_count || 1,
        byday: Array.isArray(initialData.byday) ? initialData.byday : [],
        bymonthday: Array.isArray(initialData.bymonthday) ? initialData.bymonthday : [],
        bymonth: Array.isArray(initialData.bymonth) ? initialData.bymonth : [],
        timezone: initialData.timezone || "Asia/Ho_Chi_Minh",
      };
      
      // ✅ CẬP NHẬT CALENDAR INFO TỪ INITIAL DATA
      if (initialData.calendar_source) {
        const calendarSource = initialData.calendar_source;
        setCalendarInfo({
          source: calendarSource,
          name: calendarSource === "odd" ? "📘 Calendar Lẻ" : "📗 Calendar Chẵn",
          color: calendarSource === "odd" ? "#1a73e8" : "#34a853",
          badge: calendarSource === "odd" ? "📘" : "📗",
          hourType: calendarSource === "odd" ? "odd" : "even",
        });
      } else if (initialData.start) {
        // Nếu không có calendar_source, tính từ giờ
        const startDate = new Date(initialData.start);
        const hour = startDate.getHours();
        updateCalendarInfo(hour);
      }
      
      formattedData.name = `${formattedData.classname} - ${formattedData.teacher} - ${formattedData.program}`;
      setClassData(formattedData);
    }
    
    console.log("🧩 ClassForm mounted/updated with initialData:", initialData);
  }, [initialData]);

  // Tự động cập nhật name
  useEffect(() => {
    setClassData(prev => ({
      ...prev,
      name: `${prev.classname} - ${prev.teacher} - ${prev.program}`
    }));
  }, [classData.classname, classData.teacher, classData.program]);

  // ✅ CẬP NHẬT CALENDAR INFO KHI START TIME THAY ĐỔI
  useEffect(() => {
    if (classData.start) {
      const date = new Date(classData.start);
      const hour = date.getHours();
      updateCalendarInfo(hour);
    }
  }, [classData.start]);

  const formatForDateTimeLocal = (isoString) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
      return local.toISOString().slice(0, 16);
    } catch (error) {
      console.error("Error formatting datetime:", error);
      return "";
    }
  };

  const formatForBackend = (datetimeLocal) => {
    if (!datetimeLocal) return "";
    return new Date(datetimeLocal).toISOString();
  };

  const handleChange = (e) => {
    const { name, value, type: inputType } = e.target;
    
    if (name === "start") {
      handleStartTimeChange(value);
    } 
    else if (inputType === "select-one") {
    // Xử lý select dropdown
    setClassData({ ...classData, [name]: value });
  }
    else {
      setClassData({ ...classData, [name]: value });
    }
  };

  // Handle checkbox cho byday/bymonthday/bymonth
  const handleCheckboxChange = (field, value) => {
    const arr = classData[field] || [];
    if (arr.includes(value)) {
      setClassData({ ...classData, [field]: arr.filter(x => x !== value) });
    } else {
      setClassData({ ...classData, [field]: [...arr, value] });
    }
  };

  // ✅ HÀM VALIDATE FORM
  const validateForm = () => {
    const errors = [];
    
    if (!classData.classname.trim()) errors.push("Class name is required");
    if (!classData.teacher.trim()) errors.push("Teacher is required");
    if (!classData.program.trim()) errors.push("Program is required");
    if (!classData.zoom_link.trim()) errors.push("Zoom link is required");
    if (!classData.start) errors.push("Start time is required");
    if (!classData.end) errors.push("End time is required");
    
    if (classData.start && classData.end) {
      const startDate = new Date(classData.start);
      const endDate = new Date(classData.end);
      if (endDate <= startDate) {
        errors.push("End time must be after start time");
      }
    }
    
    // Validate recurrence
    if (classData.recurrence === "WEEKLY" && (!classData.byday || classData.byday.length === 0)) {
      errors.push("Please select at least one day for weekly recurrence");
    }
    
    if (classData.recurrence === "MONTHLY" && (!classData.bymonthday || classData.bymonthday.length === 0)) {
      errors.push("Please enter at least one day for monthly recurrence");
    }
    
    if (classData.recurrence === "YEARLY") {
      if (!classData.bymonth || classData.bymonth.length === 0) {
        errors.push("Please enter at least one month for yearly recurrence");
      }
      if (!classData.bymonthday || classData.bymonthday.length === 0) {
        errors.push("Please enter at least one day for yearly recurrence");
      }
    }
    
    return errors;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Validate form
    const errors = validateForm();
    if (errors.length > 0) {
      alert("❌ Please fix the following errors:\n\n" + errors.join("\n"));
      return;
    }
    
    // ✅ THÊM CALENDAR INFO VÀO DATA GỬI ĐI
    const formattedData = {
      ...classData,
      start: formatForBackend(classData.start),
      end: formatForBackend(classData.end),
      location: classData.zoom_link || "",
      recurrence: classData.recurrence,       
      repeat_count: classData.repeat_count,   
      byday: classData.byday,                 
      bymonthday: classData.bymonthday,       
      bymonth: classData.bymonth,
      timezone: classData.timezone || "Asia/Ho_Chi_Minh",
      // ✅ THÊM CALENDAR INFO (cho reference)
      _calendar_source: calendarInfo.source,
      calendar_source: calendarInfo.source,
      calendar_info: calendarInfo.name,
    };
    
    console.log("📤 Gửi dữ liệu:", formattedData);
    console.log("📅 Calendar sẽ lưu:", calendarInfo.name);
    
    // Show confirmation with calendar info
    const confirmMessage = `Event sẽ được lưu vào:\n${calendarInfo.name}\n\nGiờ bắt đầu: ${new Date(classData.start).getHours()}h (${calendarInfo.hourType === 'even' ? 'chẵn' : 'lẻ'})\n\nXác nhận tạo event?`;
    
    if (window.confirm(confirmMessage)) {
      onSubmit(formattedData);
    }
  };

  // ✅ HÀM RESET FORM
  const handleReset = () => {
    setClassData({
      name: "",
      classname: "",
      teacher: "",
      zoom_link: "",
      meeting_id: "",
      passcode: "",
      program: "",
      start: "",
      end: "",
      recurrence: "",
      repeat_count: 1,
      byday: [],
      bymonthday: [],
      bymonth: [],
      timezone: "Asia/Ho_Chi_Minh",
    });
    setCalendarInfo({
      source: "odd",
      name: "📘 Calendar Lẻ",
      color: "#1a73e8",
      badge: "📘",
      hourType: "odd",
    });
  };

  // ✅ HÀM FORMAT THỜI GIAN HIỂN THỊ
  const formatTimeDisplay = (datetimeLocal) => {
    if (!datetimeLocal) return "N/A";
    const date = new Date(datetimeLocal);
    return date.toLocaleString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  };

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      {/* ================= HEADER WITH CALENDAR INFO ================= */}
      <div className={styles.formHeader}>
        <h3 className={styles.formTitle}>
          {initialData ? "✏️ Edit Class" : "➕ Add New Class"}
        </h3>
        
        {/* ✅ CALENDAR INDICATOR */}
        <div 
          className={`${styles.calendarIndicator} ${
            calendarInfo.source === "odd" ? styles.indicatorOdd : styles.indicatorEven
          }`}
        >
          <span className={styles.calendarBadge}>{calendarInfo.badge}</span>
          <span className={styles.calendarText}>{calendarInfo.name}</span>
          {classData.start && (
            <span className={styles.timeInfo}>
              Giờ: {new Date(classData.start).getHours()}h ({calendarInfo.hourType === 'even' ? 'chẵn' : 'lẻ'})
            </span>
          )}
        </div>
      </div>

      {/* ================= BASIC INFO SECTION ================= */}
      <div className={styles.section}>
        
        
        {/* Subject */}
        <div className={styles.formGroup}>
          <label className={styles.requiredLabel}>Tiêu đề (tự động)</label>
          <input 
            name="name" 
            value={classData.name} 
            readOnly 
            className={styles.readOnlyInput}
          />
        </div>

        {/* Class Name */}
        <div className={styles.formGroup}>
          <label className={styles.requiredLabel}>Tên lớp</label>
          <input 
            name="classname" 
            value={classData.classname} 
            onChange={handleChange} 
            required 
            placeholder="Enter class name"
          />
        </div>

        {/* Teacher */}
        <div className={styles.formGroup}>
          <label className={styles.requiredLabel}>Giáo viên</label>
          <input 
            name="teacher" 
            value={classData.teacher} 
            onChange={handleChange} 
            required 
            placeholder="Enter teacher name"
          />
        </div>

        {/* Program */}
        <div className={styles.formGroup}>
          <label className={styles.requiredLabel}>Chương trình</label>
          
          <select
            name="program"
            value={classData.program}
            onChange={handleChange}
            required
            className={styles.programSelect}
          >
            <option value="" disabled hidden>-- Chọn chương trình --</option>
            <option value="toán">📐 Toán học</option>
            <option value="vật_lý">⚛️ Vật lý</option>
            <option value="hóa_học">🧪 Hóa học</option>
            <option value="sinh_học">🧬 Sinh học</option>
            <option value="tiếng_anh">🇬🇧 Tiếng Anh</option>
            <option value="ngữ_văn">📖 Ngữ văn</option>
            <option value="lịch_sử">🏛️ Lịch sử</option>
            <option value="địa_lý">🗺️ Địa lý</option>
            <option value="gdcd">⚖️ Giáo dục công dân</option>
            <option value="tin_học">💻 Tin học</option>
            <option value="công_nghệ">🔧 Công nghệ</option>
            <option value="ielts">🎯 IELTS</option>
            <option value="toefl">📝 TOEFL</option>
            <option value="programming">👨‍💻 Lập trình</option>
            <option value="stem">🔬 STEM</option>
            <option value="khác">📌 Khác</option>
          </select>
          
          
        </div>
      </div>

      {/* ================= ZOOM INFO SECTION ================= */}
      <div className={styles.section}>
        
        
        {/* Zoom Link */}
        <div className={styles.formGroup}>
          <label className={styles.requiredLabel}>Zoom Link</label>
          <input 
            name="zoom_link" 
            value={classData.zoom_link} 
            onChange={handleChange} 
            required 
            placeholder="https://zoom.us/j/..."
            type="url"
          />
        </div>

        {/* Meeting ID & Passcode */}
        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label>Meeting ID</label>
            <input 
              name="meeting_id" 
              value={classData.meeting_id} 
              onChange={handleChange} 
              placeholder="Optional"
            />
          </div>
          <div className={styles.formGroup}>
            <label>Passcode</label>
            <input 
              name="passcode" 
              value={classData.passcode} 
              onChange={handleChange} 
              placeholder="Optional"
            />
          </div>
        </div>
      </div>

      {/* ================= TIME SECTION ================= */}
      <div className={styles.section}>
        
        
        {/* Start & End */}
        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label className={styles.requiredLabel}>Start Time</label>
            <input 
              type="datetime-local" 
              name="start" 
              value={classData.start} 
              onChange={handleChange} 
              required 
              className={styles.timeInput}
            />
            
          </div>
          <div className={styles.formGroup}>
            <label className={styles.requiredLabel}>End Time</label>
            <input 
              type="datetime-local" 
              name="end" 
              value={classData.end} 
              onChange={handleChange} 
              required 
              className={styles.timeInput}
            />
            
          </div>
        </div>

        {/* Timezone */}
        <div className={styles.formGroup}>
          <label className={styles.requiredLabel}>Timezone</label>
          <select 
            name="timezone" 
            value={classData.timezone} 
            onChange={handleChange}
            className={styles.timezoneSelect}
          >
            {timezoneOptions.map((tz) => (
              <option key={tz.value} value={tz.value}>
                {tz.label}
              </option>
            ))}
          </select>
          <div className={styles.timezoneHelp}>
            ⏰ Selected: {timezoneOptions.find(tz => tz.value === classData.timezone)?.label}
          </div>
        </div>
        
        {/* Duration Info */}
        {classData.start && classData.end && (
          <div className={styles.durationInfo}>
            <span>⏱️ Duration: </span>
            <span className={styles.durationValue}>
              {Math.round((new Date(classData.end) - new Date(classData.start)) / (1000 * 60 * 60) * 10) / 10} hours
            </span>
          </div>
        )}
      </div>

      {/* ================= RECURRENCE SECTION ================= */}
      <div className={styles.section}>
        
        
        {/* Recurrence Type */}
        <div className={styles.formGroup}>
          <label>Repeat</label>
          <select 
            name="recurrence" 
            value={classData.recurrence} 
            onChange={handleChange}
            className={styles.recurrenceSelect}
          >
            <option value="">Không lặp (Single Event)</option>
            <option value="DAILY">Hàng ngày (Daily)</option>
            <option value="WEEKLY">Hàng tuần (Weekly)</option>
            <option value="MONTHLY">Hàng tháng (Monthly)</option>
            <option value="YEARLY">Hàng năm (Yearly)</option>
          </select>
        </div>

        {/* Repeat count */}
        {classData.recurrence && (
          <div className={styles.formGroup}>
            <label>Number of Occurrences</label>
            <div className={styles.repeatCountContainer}>
              <input 
                type="number" 
                name="repeat_count" 
                value={classData.repeat_count} 
                min={1} 
                max={999}
                onChange={handleChange} 
                className={styles.repeatCountInput}
              />
              <span className={styles.repeatCountLabel}>times</span>
            </div>
          </div>
        )}

        {/* Weekly: chọn ngày */}
        {classData.recurrence === "WEEKLY" && (
          <div className={styles.formGroup}>
            <label>Select Days of Week</label>
            <div className={styles.dayCheckboxes}>
              {["MO","TU","WE","TH","FR","SA","SU"].map(day => (
                <label key={day} className={styles.dayCheckbox}>
                  <input
                    type="checkbox"
                    checked={classData.byday?.includes(day)}
                    onChange={() => handleCheckboxChange("byday", day)}
                    className={styles.checkboxInput}
                  />
                  <span className={styles.dayLabel}>{day}</span>
                </label>
              ))}
            </div>
            <div className={styles.selectedDays}>
              Selected: {classData.byday.length > 0 ? classData.byday.join(", ") : "No days selected"}
            </div>
          </div>
        )}

        {/* Monthly: chọn ngày trong tháng */}
        {classData.recurrence === "MONTHLY" && (
          <div className={styles.formGroup}>
            <label>Days of Month (comma separated)</label>
            <input
              type="text"
              placeholder="e.g., 1,15,20"
              value={classData.bymonthday.join(",")}
              onChange={e => setClassData({...classData, bymonthday: e.target.value.split(",").filter(x => x.trim()).map(Number)})}
              className={styles.monthInput}
            />
            <div className={styles.inputHelp}>
              Enter day numbers (1-31) separated by commas
            </div>
          </div>
        )}

        {/* Yearly: chọn tháng + ngày */}
        {classData.recurrence === "YEARLY" && (
          <>
            <div className={styles.formGroup}>
              <label>Months (comma separated)</label>
              <input
                type="text"
                placeholder="e.g., 1,6,12"
                value={classData.bymonth.join(",")}
                onChange={e => setClassData({...classData, bymonth: e.target.value.split(",").filter(x => x.trim()).map(Number)})}
                className={styles.monthInput}
              />
              <div className={styles.inputHelp}>
                Enter month numbers (1-12) separated by commas
              </div>
            </div>
            <div className={styles.formGroup}>
              <label>Days of Month (comma separated)</label>
              <input
                type="text"
                placeholder="e.g., 1,15,20"
                value={classData.bymonthday.join(",")}
                onChange={e => setClassData({...classData, bymonthday: e.target.value.split(",").filter(x => x.trim()).map(Number)})}
                className={styles.monthInput}
              />
              <div className={styles.inputHelp}>
                Enter day numbers (1-31) separated by commas
              </div>
            </div>
          </>
        )}
      </div>

      {/* ================= DEBUG INFO (optional) ================= */}
      <div className={styles.debugInfo}>
        <details>
          <summary>🔍 Debug Info</summary>
          <pre>
            Calendar: {calendarInfo.source} ({calendarInfo.name})
            {"\n"}Start: {classData.start}
            {"\n"}End: {classData.end}
            {"\n"}Recurrence: {classData.recurrence || "none"}
            {"\n"}Timezone: {classData.timezone}
          </pre>
        </details>
      </div>

      {/* ================= BUTTONS ================= */}
      <div className={styles.buttonGroup}>
        <button type="submit" className={styles.saveBtn}>
          {initialData ? "💾 Update" : "➕ Create"}
          <span className={styles.saveCalendar}>
            {" "}({calendarInfo.badge})
          </span>
        </button>
        <button 
          type="button" 
          className={styles.resetBtn} 
          onClick={handleReset}
          title="Reset form"
        >
          🔄 Reset
        </button>
        {onCancel && (
          <button type="button" className={styles.cancelBtn} onClick={onCancel}>
            ❌ Cancel
          </button>
        )}
      </div>
    </form>
  );
}