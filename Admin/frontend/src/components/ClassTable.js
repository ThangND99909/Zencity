// frontend/src/components/ClassTable.js
import React, { useState, useMemo } from "react";
import styles from "./ClassTable.module.css";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";
import { parseZoomInfo } from "../utils/sanitizeDescription";

export default function ClassTable({ classes, onEdit, onDelete, calendarFilter }) {
  const [copiedItem, setCopiedItem] = useState(null);

  // --- Bộ lọc ---
  const [filters, setFilters] = useState({
    name: "",
    program: "",
    teacher: "",
    calendar: "all" // Thêm filter calendar
  });

  const handleFilterChange = (e) => {
    setFilters({ ...filters, [e.target.name]: e.target.value });
  };

  // Trích xuất thông tin từ description và các field trực tiếp
  const extractClassInfo = (cls) => {
    const rawDescription = cls.description || "";
    const { zoomLink, meetingId, passcode, program, teacher, classname } = parseZoomInfo(rawDescription);

    // ✅ THÊM THÔNG TIN CALENDAR
    const calendarSource = cls._calendar_source || 
                          (cls.calendar_id ? (cls.calendar_id.includes('even') ? 'even' : 'odd') : 'odd');
    
    const calendarInfo = {
      source: calendarSource,
      name: calendarSource === 'odd' ? '📘 Calendar Lẻ' : '📗 Calendar Chẵn',
      color: calendarSource === 'odd' ? '#1a73e8' : '#34a853',
      badge: calendarSource === 'odd' ? '📘' : '📗'
    };

    return {
      classname: cls.classname || classname || "N/A",
      teacher: cls.teacher || teacher || "N/A",
      zoom_link:
        cls.zoom_link ||
        cls.zoom ||
        cls.meeting_url ||
        cls.location ||
        zoomLink ||
        "",
      meeting_id: cls.meeting_id || meetingId || "",
      passcode: cls.passcode || passcode || "",
      program: cls.program || program || "N/A",
      // ✅ THÊM CALENDAR INFO
      calendar_source: calendarInfo.source,
      calendar_name: calendarInfo.name,
      calendar_color: calendarInfo.color,
      calendar_badge: calendarInfo.badge,
      // ✅ THÊM THÔNG TIN RECURRENCE
      recurrence: cls.recurrence,
      recurringEventId: cls.recurringEventId,
      recurrence_description: cls.recurrence_description || ""
    };
  };

  // ================= Lọc lớp =================
  const filteredClasses = useMemo(() => {
    let result = classes.filter((cls) => {
      // ✅ FILTER QUAN TRỌNG: Loại bỏ events đã bị xóa
      if (cls.status === "cancelled") return false;
      
      // ✅ ÁP DỤNG CALENDAR FILTER TỪ PROPS
      if (calendarFilter && calendarFilter !== 'both') {
        const calendarSource = cls._calendar_source || 'odd';
        if (calendarFilter !== calendarSource) return false;
      }
      
      const info = extractClassInfo(cls);
      const matchName = cls.summary.toLowerCase().includes(filters.name.toLowerCase());
      const matchProgram = info.program.toLowerCase().includes(filters.program.toLowerCase());
      const matchTeacher = info.teacher.toLowerCase().includes(filters.teacher.toLowerCase());
      
      // ✅ FILTER CALENDAR (NẾU CÓ)
      let matchCalendar = true;
      if (filters.calendar && filters.calendar !== 'all') {
        matchCalendar = info.calendar_source === filters.calendar;
      }
      
      return matchName && matchProgram && matchTeacher && matchCalendar;
    });

    // ✅ SẮP XẾP THEO THỜI GIAN BẮT ĐẦU
    result.sort((a, b) => {
      const timeA = new Date(a.start?.dateTime || a.start).getTime();
      const timeB = new Date(b.start?.dateTime || b.start).getTime();
      return timeA - timeB;
    });

    return result;
  }, [classes, filters, calendarFilter]);

  const handleCopy = (classId, value, type, e) => {
    e.stopPropagation();
    if (!value) return;
    navigator.clipboard.writeText(value)
      .then(() => {
        setCopiedItem(`${classId}-${type}`);
        setTimeout(() => setCopiedItem(null), 2000);
      })
      .catch((err) => console.error("Failed to copy:", err));
  };

  const handleOpenLink = (link, e) => {
    e.stopPropagation();
    if (link) window.open(link, "_blank", "noopener,noreferrer");
  };

  const shortenLink = (link) => {
    if (!link) return "";
    return link.length > 40 ? link.substring(0, 40) + "..." : link;
  };

  // ================= Export Excel =================
  const handleExportExcel = () => {
    if (!filteredClasses || filteredClasses.length === 0) {
      alert("Không có dữ liệu để export!");
      return;
    }

    const data = filteredClasses.map((cls) => {
      const info = extractClassInfo(cls);
      
      // ✅ PHÂN TÍCH THÔNG TIN RECURRENCE
      let recurrenceInfo = "";
      if (info.recurrence_description) {
        recurrenceInfo = info.recurrence_description;
      } else if (cls.recurrence && Array.isArray(cls.recurrence) && cls.recurrence.length > 0) {
        recurrenceInfo = cls.recurrence[0];
      } else if (cls.recurringEventId) {
        recurrenceInfo = "Recurring Instance";
      }
      
      return {
        "Calendar": info.calendar_name,
        "Subject": cls.summary || "",
        "Class Name": info.classname || "",
        "Teacher": info.teacher,
        "Program": info.program,
        "Zoom Link": info.zoom_link,
        "Meeting ID": info.meeting_id,
        "Passcode": info.passcode,
        "Start Time": new Date(cls.start?.dateTime || cls.start).toLocaleString("vi-VN"),
        "End Time": new Date(cls.end?.dateTime || cls.end).toLocaleString("vi-VN"),
        "Recurrence": recurrenceInfo,
        "Timezone": cls.start?.timeZone || cls.end?.timeZone || "Asia/Ho_Chi_Minh",
        "Event ID": cls.id || "",
        "Calendar Source": info.calendar_source
      };
    });

    const worksheet = XLSX.utils.json_to_sheet(data);
    
    // ✅ ĐIỀU CHỈNH ĐỘ RỘNG CỘT
    const colWidths = [
      { wch: 15 }, // Calendar
      { wch: 30 }, // Subject
      { wch: 20 }, // Class Name
      { wch: 20 }, // Teacher
      { wch: 20 }, // Program
      { wch: 40 }, // Zoom Link
      { wch: 15 }, // Meeting ID
      { wch: 10 }, // Passcode
      { wch: 25 }, // Start Time
      { wch: 25 }, // End Time
      { wch: 30 }, // Recurrence
      { wch: 20 }, // Timezone
      { wch: 40 }, // Event ID
      { wch: 15 }, // Calendar Source
    ];
    worksheet['!cols'] = colWidths;

    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Classes Schedule");

    const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
    const blob = new Blob([excelBuffer], { type: "application/octet-stream" });
    
    const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    saveAs(blob, `ClassSchedule_${timestamp}.xlsx`);
    
    console.log(`✅ Exported ${data.length} classes to Excel`);
  };

  // ✅ HÀM ĐỊNH DẠNG THỜI GIAN
  const formatDateTime = (dateTime) => {
    if (!dateTime) return "N/A";
    try {
      return new Date(dateTime).toLocaleString("vi-VN", {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
    } catch {
      return dateTime;
    }
  };

  // ✅ THỐNG KÊ
  const stats = useMemo(() => {
    const oddCount = filteredClasses.filter(cls => {
      const info = extractClassInfo(cls);
      return info.calendar_source === 'odd';
    }).length;
    
    const evenCount = filteredClasses.filter(cls => {
      const info = extractClassInfo(cls);
      return info.calendar_source === 'even';
    }).length;
    
    return {
      total: filteredClasses.length,
      odd: oddCount,
      even: evenCount
    };
  }, [filteredClasses]);

  return (
    <div className={styles.tableContainer}>
      {/* ================= STATS & FILTERS ================= */}
      <div className={styles.headerSection}>
        <div className={styles.stats}>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Total:</span>
            <span className={styles.statValue}>{stats.total}</span>
          </div>
          <div className={`${styles.statItem} ${styles.statOdd}`}>
            <span className={styles.statLabel}>📘 Odd:</span>
            <span className={styles.statValue}>{stats.odd}</span>
          </div>
          <div className={`${styles.statItem} ${styles.statEven}`}>
            <span className={styles.statLabel}>📗 Even:</span>
            <span className={styles.statValue}>{stats.even}</span>
          </div>
        </div>

        <div className={styles.filters}>
          <input
            type="text"
            name="name"
            placeholder="Tìm theo tên lớp"
            value={filters.name}
            onChange={handleFilterChange}
            className={styles.filterInput}
          />
          <input
            type="text"
            name="program"
            placeholder="Tìm theo môn học"
            value={filters.program}
            onChange={handleFilterChange}
            className={styles.filterInput}
          />
          <input
            type="text"
            name="teacher"
            placeholder="Tìm theo giáo viên"
            value={filters.teacher}
            onChange={handleFilterChange}
            className={styles.filterInput}
          />
          <select
            name="calendar"
            value={filters.calendar}
            onChange={handleFilterChange}
            className={styles.filterSelect}
          >
            <option value="all">Tất cả Calendar</option>
            <option value="odd">📘 Calendar Lẻ</option>
            <option value="even">📗 Calendar Chẵn</option>
          </select>
        </div>
      </div>

      {/* ================= TABLE ================= */}
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.colCalendar}>Calendar</th>
              <th className={styles.colSubject}>Subject</th>
              <th className={styles.colClassName}>Class Name</th>
              <th className={styles.colTeacher}>Teacher</th>
              <th className={styles.colProgram}>Program</th>
              <th className={styles.colZoom}>Zoom</th>
              <th className={styles.colMeetingID}>Meeting ID</th>
              <th className={styles.colPasscode}>Passcode</th>
              <th className={styles.colStart}>Start</th>
              <th className={styles.colEnd}>End</th>
              <th className={styles.colRecurrence}>Recurrence</th>
              <th className={styles.colActions}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredClasses.length === 0 ? (
              <tr>
                <td colSpan="12" className={styles.noData}>
                  📭 No classes found. Try different filters or create a new class.
                </td>
              </tr>
            ) : (
              filteredClasses.map((cls) => {
                const info = extractClassInfo(cls);
                
                // ✅ CHECK RECURRENCE
                const hasRecurrence = info.recurrence_description || 
                                     (cls.recurrence && Array.isArray(cls.recurrence) && cls.recurrence.length > 0) ||
                                     cls.recurringEventId;
                
                return (
                  <tr 
                    key={cls.id} 
                    className={`${styles.tableRow} ${
                      info.calendar_source === 'odd' ? styles.rowOdd : styles.rowEven
                    }`}
                  >
                    {/* CALENDAR COLUMN */}
                    <td className={styles.calendarCell}>
                      <div className={`${styles.calendarBadge} ${
                        info.calendar_source === 'odd' ? styles.badgeOdd : styles.badgeEven
                      }`}>
                        {info.calendar_badge}
                      </div>
                    </td>
                    
                    {/* SUBJECT */}
                    <td>
                      <div className={styles.subjectCell}>
                        <span className={styles.subjectText}>{cls.summary}</span>
                        {hasRecurrence && (
                          <span className={styles.recurrenceIcon} title="Recurring Event">🔄</span>
                        )}
                      </div>
                    </td>
                    
                    {/* CLASS NAME */}
                    <td>{info.classname || "N/A"}</td>
                    
                    {/* TEACHER */}
                    <td>
                      <div className={styles.teacherCell}>
                        <span>{info.teacher}</span>
                      </div>
                    </td>
                    
                    {/* PROGRAM */}
                    <td>{info.program}</td>
                    
                    {/* ZOOM LINK */}
                    <td>
                      {info.zoom_link ? (
                        <div className={styles.zoomLinkContainer}>
                          <span 
                            className={styles.zoomLinkText} 
                            title={info.zoom_link}
                            onClick={(e) => handleOpenLink(info.zoom_link, e)}
                          >
                            {shortenLink(info.zoom_link)}
                          </span>
                          <div className={styles.buttonGroup}>
                            <button
                              className={`${styles.iconButton} ${styles.copyButton} ${
                                copiedItem === `${cls.id}-zoom` ? styles.copied : ""
                              }`}
                              onClick={(e) => handleCopy(cls.id, info.zoom_link, "zoom", e)}
                              title="Copy Zoom link"
                            >
                              {copiedItem === `${cls.id}-zoom` ? "✅" : "📋"}
                            </button>
                            <button
                              className={`${styles.iconButton} ${styles.openButton}`}
                              onClick={(e) => handleOpenLink(info.zoom_link, e)}
                              title="Open Zoom link"
                            >
                              🔗
                            </button>
                          </div>
                        </div>
                      ) : (
                        <span className={styles.naText}>N/A</span>
                      )}
                    </td>
                    
                    {/* MEETING ID */}
                    <td>
                      {info.meeting_id ? (
                        <div className={styles.meetingIdContainer}>
                          <span>{info.meeting_id}</span>
                          <button
                            className={`${styles.iconButton} ${styles.copyButton} ${
                              copiedItem === `${cls.id}-meeting` ? styles.copied : ""
                            }`}
                            onClick={(e) => handleCopy(cls.id, info.meeting_id, "meeting", e)}
                            title="Copy Meeting ID"
                          >
                            {copiedItem === `${cls.id}-meeting` ? "✅" : "📋"}
                          </button>
                        </div>
                      ) : (
                        <span className={styles.naText}>N/A</span>
                      )}
                    </td>
                    
                    {/* PASSCODE */}
                    <td>
                      {info.passcode ? (
                        <div className={styles.passcodeContainer}>
                          <span>{info.passcode}</span>
                          <button
                            className={`${styles.iconButton} ${styles.copyButton} ${
                              copiedItem === `${cls.id}-passcode` ? styles.copied : ""
                            }`}
                            onClick={(e) => handleCopy(cls.id, info.passcode, "passcode", e)}
                            title="Copy Passcode"
                          >
                            {copiedItem === `${cls.id}-passcode` ? "✅" : "📋"}
                          </button>
                        </div>
                      ) : (
                        <span className={styles.naText}>N/A</span>
                      )}
                    </td>
                    
                    {/* START TIME */}
                    <td className={styles.timeCell}>
                      {formatDateTime(cls.start?.dateTime || cls.start)}
                    </td>
                    
                    {/* END TIME */}
                    <td className={styles.timeCell}>
                      {formatDateTime(cls.end?.dateTime || cls.end)}
                    </td>
                    
                    {/* RECURRENCE INFO */}
                    <td>
                      {info.recurrence_description ? (
                        <span className={styles.recurrenceText} title={info.recurrence_description}>
                          🔁 {info.recurrence_description.length > 20 
                            ? info.recurrence_description.substring(0, 20) + "..."
                            : info.recurrence_description}
                        </span>
                      ) : hasRecurrence ? (
                        <span className={styles.recurrenceIconSmall} title="Recurring Event">🔄</span>
                      ) : (
                        <span className={styles.naText}>-</span>
                      )}
                    </td>
                    
                    {/* ACTIONS */}
                    <td className={styles.actions}>
                      <div className={styles.actionButtons}>
                        <button 
                          className={`${styles.actionButton} ${styles.editBtn}`} 
                          onClick={() => onEdit(cls)}
                          title="Edit"
                        >
                          ✏️
                        </button>
                        <button 
                          className={`${styles.actionButton} ${styles.deleteBtn}`} 
                          onClick={() => onDelete(cls.id)}
                          title="Delete"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ================= FOOTER & EXPORT ================= */}
      <div className={styles.footer}>
        <div className={styles.footerStats}>
          Showing <strong>{filteredClasses.length}</strong> of <strong>{classes.length}</strong> classes
          {filters.calendar !== 'all' && (
            <span className={styles.filterNote}>
              • Filtered by: {filters.calendar === 'odd' ? '📘 Calendar Lẻ' : '📗 Calendar Chẵn'}
            </span>
          )}
        </div>
        <div className={styles.exportSection}>
          <button 
            className={`${styles.exportButton} ${styles.btnWarning}`} 
            onClick={handleExportExcel}
            disabled={filteredClasses.length === 0}
          >
            📥 Export Excel ({filteredClasses.length})
          </button>
        </div>
      </div>
    </div>
  );
}