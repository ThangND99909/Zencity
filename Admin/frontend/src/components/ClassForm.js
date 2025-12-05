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

  // ✅ THÊM TIMEZONE OPTIONS (đồng bộ với CalendarView)
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
        byday: initialData.byday || [],
        bymonthday: initialData.bymonthday || [],
        bymonth: initialData.bymonth || [],
        timezone: initialData.timezone || "Asia/Ho_Chi_Minh", // ✅ THÊM TIMEZONE
      };
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

  const formatForDateTimeLocal = (isoString) => {
    if (!isoString) return "";
    const date = new Date(isoString);
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  };

  const formatForBackend = (datetimeLocal) => {
    if (!datetimeLocal) return "";
    return new Date(datetimeLocal).toISOString();
  };

  const handleChange = (e) => {
    setClassData({ ...classData, [e.target.name]: e.target.value });
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

  const handleSubmit = (e) => {
    e.preventDefault();
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
      timezone: classData.timezone || "Asia/Ho_Chi_Minh" // ✅ THÊM TIMEZONE VÀO DATA GỬI ĐI  
    };
    console.log("📤 Gửi dữ liệu:", formattedData);
    onSubmit(formattedData);
  };

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      {/* Subject */}
      <div className={styles.formGroup}>
        <label className={styles.requiredLabel}>Subject</label>
        <input name="name" value={classData.name} readOnly />
      </div>

      {/* Class Name */}
      <div className={styles.formGroup}>
        <label className={styles.requiredLabel}>Class Name</label>
        <input name="classname" value={classData.classname} onChange={handleChange} required />
      </div>

      {/* Teacher */}
      <div className={styles.formGroup}>
        <label className={styles.requiredLabel}>Teacher</label>
        <input name="teacher" value={classData.teacher} onChange={handleChange} required />
      </div>

      {/* Program */}
      <div className={styles.formGroup}>
        <label className={styles.requiredLabel}>Program</label>
        <input name="program" value={classData.program} onChange={handleChange} required />
      </div>

      {/* Zoom Link */}
      <div className={styles.formGroup}>
        <label className={styles.requiredLabel}>Zoom Link</label>
        <input name="zoom_link" value={classData.zoom_link} onChange={handleChange} required />
      </div>

      {/* Meeting ID & Passcode */}
      <div className={styles.formRow}>
        <div className={styles.formGroup}>
          <label>Meeting ID</label>
          <input name="meeting_id" value={classData.meeting_id} onChange={handleChange} />
        </div>
        <div className={styles.formGroup}>
          <label>Passcode</label>
          <input name="passcode" value={classData.passcode} onChange={handleChange} />
        </div>
      </div>

      {/* Start & End */}
      <div className={styles.formRow}>
        <div className={styles.formGroup}>
          <label className={styles.requiredLabel}>Start Time</label>
          <input type="datetime-local" name="start" value={classData.start} onChange={handleChange} required />
        </div>
        <div className={styles.formGroup}>
          <label className={styles.requiredLabel}>End Time</label>
          <input type="datetime-local" name="end" value={classData.end} onChange={handleChange} required />
        </div>
      </div>

      {/* ✅ THÊM TIMEZONE SELECTOR */}
      <div className={styles.formGroup}>
        <label className={styles.requiredLabel}>Múi giờ</label>
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
          ⏰ Đã chọn: {timezoneOptions.find(tz => tz.value === classData.timezone)?.label}
        </div>
      </div>

      {/* Recurrence */}
      <div className={styles.formGroup}>
        <label>Repeat</label>
        <select name="recurrence" value={classData.recurrence} onChange={handleChange}>
          <option value="">Không lặp</option>
          <option value="DAILY">Hàng ngày</option>
          <option value="WEEKLY">Hàng tuần</option>
          <option value="MONTHLY">Hàng tháng</option>
          <option value="YEARLY">Hàng năm</option>
        </select>
      </div>

      {/* Repeat count */}
      {classData.recurrence && (
        <div className={styles.formGroup}>
          <label>Số lần lặp</label>
          <input type="number" name="repeat_count" value={classData.repeat_count} min={1} onChange={handleChange} />
        </div>
      )}

      {/* Weekly: chọn ngày */}
      {classData.recurrence === "WEEKLY" && (
        <div className={styles.formGroup}>
          <label>Chọn ngày trong tuần</label>
          {["MO","TU","WE","TH","FR","SA","SU"].map(day => (
            <label key={day} style={{marginRight:"8px"}}>
              <input
                type="checkbox"
                checked={classData.byday?.includes(day)}
                onChange={() => handleCheckboxChange("byday", day)}
              />
              {day}
            </label>
          ))}
        </div>
      )}

      {/* Monthly: chọn ngày trong tháng */}
      {classData.recurrence === "MONTHLY" && (
        <div className={styles.formGroup}>
          <label>Chọn ngày trong tháng</label>
          <input
            type="text"
            placeholder="1,15,20"
            value={classData.bymonthday.join(",")}
            onChange={e => setClassData({...classData, bymonthday: e.target.value.split(",").map(Number)})}
          />
        </div>
      )}

      {/* Yearly: chọn tháng + ngày */}
      {classData.recurrence === "YEARLY" && (
        <div className={styles.formGroup}>
          <label>Chọn tháng</label>
          <input
            type="text"
            placeholder="1,6,12"
            value={classData.bymonth.join(",")}
            onChange={e => setClassData({...classData, bymonth: e.target.value.split(",").map(Number)})}
          />
          <label>Chọn ngày</label>
          <input
            type="text"
            placeholder="1,15,20"
            value={classData.bymonthday.join(",")}
            onChange={e => setClassData({...classData, bymonthday: e.target.value.split(",").map(Number)})}
          />
        </div>
      )}

      {/* Buttons */}
      <div className={styles.buttonGroup}>
        <button type="submit" className={styles.saveBtn}>💾 Save</button>
        {onCancel && (
          <button type="button" className={styles.cancelBtn} onClick={onCancel}>❌ Cancel</button>
        )}
      </div>
    </form>
  );
}
