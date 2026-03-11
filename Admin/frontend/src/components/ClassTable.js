// frontend/src/components/ClassTable.js
import React, { useState, useMemo } from "react";
import styles from "./ClassTable.module.css";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";
import { parseZoomInfo } from "../utils/sanitizeDescription";

// Modal component để hiển thị chi tiết sự kiện lặp lại
const RecurrenceModal = ({ events, onClose }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  
  // Phân trang cho modal
  const paginatedEvents = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    return events.slice(start, end);
  }, [events, currentPage, pageSize]);
  
  const totalPages = Math.ceil(events.length / pageSize);
  
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
  
  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h3>Chi tiết sự kiện lặp lại</h3>
          <button className={styles.closeButton} onClick={onClose}>×</button>
        </div>
        
        <div className={styles.modalBody}>
          <table className={styles.modalTable}>
            <thead>
              <tr>
                <th>STT</th>
                <th>Thời gian bắt đầu</th>
                <th>Thời gian kết thúc</th>
                <th>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {paginatedEvents.map((event, index) => (
                <tr key={event.id}>
                  <td>{(currentPage - 1) * pageSize + index + 1}</td>
                  <td>{formatDateTime(event.start?.dateTime || event.start)}</td>
                  <td>{formatDateTime(event.end?.dateTime || event.end)}</td>
                  <td>
                    <span className={event.status === 'cancelled' ? styles.cancelled : styles.active}>
                      {event.status === 'cancelled' ? 'Đã hủy' : 'Hoạt động'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {/* Phân trang cho modal */}
          <div className={styles.pagination}>
            <div className={styles.paginationInfo}>
              Hiển thị {paginatedEvents.length} / {events.length} sự kiện
            </div>
            <div className={styles.paginationControls}>
              <select 
                value={pageSize} 
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className={styles.pageSizeSelect}
              >
                <option value={10}>10 / trang</option>
                <option value={20}>20 / trang</option>
                <option value={50}>50 / trang</option>
                <option value={100}>100 / trang</option>
              </select>
              
              <button 
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className={styles.pageButton}
              >
                ←
              </button>
              <span className={styles.pageInfo}>
                Trang {currentPage} / {totalPages}
              </span>
              <button 
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className={styles.pageButton}
              >
                →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function ClassTable({ classes, onEdit, onDelete, calendarFilter }) {
  const [copiedItem, setCopiedItem] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [selectedRecurringEvents, setSelectedRecurringEvents] = useState(null);

  // --- Bộ lọc ---
  const [filters, setFilters] = useState({
    name: "",
    program: "",
    teacher: "",
    calendar: "all"
  });

  const handleFilterChange = (e) => {
    setFilters({ ...filters, [e.target.name]: e.target.value });
    setCurrentPage(1); // Reset về trang 1 khi filter
  };

  const handleClearFilter = (name) => {
    setFilters({ ...filters, [name]: "" });
    setCurrentPage(1);
  };

  // Trích xuất thông tin từ description và các field trực tiếp
  const extractClassInfo = (cls) => {
    const rawDescription = cls.description || "";
    const { zoomLink, meetingId, passcode, program, teacher, classname } = parseZoomInfo(rawDescription);

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
      calendar_source: calendarInfo.source,
      calendar_name: calendarInfo.name,
      calendar_color: calendarInfo.color,
      calendar_badge: calendarInfo.badge,
      recurrence: cls.recurrence,
      recurringEventId: cls.recurringEventId,
      recurrence_description: cls.recurrence_description || ""
    };
  };

  // ================= NHÓM CÁC SỰ KIỆN LẶP LẠI =================
  const groupedClasses = useMemo(() => {
    // Nhóm các sự kiện theo recurringEventId
    const recurringGroups = new Map();
    const nonRecurring = [];
    
    classes.forEach(cls => {
      if (cls.status === "cancelled") return;
      
      if (cls.recurringEventId) {
        if (!recurringGroups.has(cls.recurringEventId)) {
          recurringGroups.set(cls.recurringEventId, []);
        }
        recurringGroups.get(cls.recurringEventId).push(cls);
      } else {
        nonRecurring.push(cls);
      }
    });
    
    // Tạo đại diện cho mỗi nhóm (lấy event đầu tiên)
    const recurringRepresentatives = Array.from(recurringGroups.entries()).map(([recurringId, events]) => {
      // Sắp xếp events theo thời gian
      events.sort((a, b) => {
        const timeA = new Date(a.start?.dateTime || a.start).getTime();
        const timeB = new Date(b.start?.dateTime || b.start).getTime();
        return timeA - timeB;
      });
      
      // Lấy event đầu tiên làm đại diện
      const representative = { ...events[0] };
      // Thêm metadata để biết đây là đại diện của nhóm
      representative._isRecurringGroup = true;
      representative._recurringEvents = events;
      representative._recurringCount = events.length;
      representative._nextOccurrence = events[0];
      representative._lastOccurrence = events[events.length - 1];
      
      return representative;
    });
    
    // Kết hợp non-recurring và recurring representatives
    return [...nonRecurring, ...recurringRepresentatives];
  }, [classes]);

  // ================= Lọc lớp =================
  const filteredClasses = useMemo(() => {
    let result = groupedClasses.filter((cls) => {
      if (calendarFilter && calendarFilter !== 'both') {
        const calendarSource = cls._calendar_source || 'odd';
        if (calendarFilter !== calendarSource) return false;
      }
      
      const info = extractClassInfo(cls);
      const matchName = (cls.summary || "").toLowerCase().includes(filters.name.toLowerCase());
      const matchProgram = (info.program || "").toLowerCase().includes(filters.program.toLowerCase());
      const matchTeacher = (info.teacher || "").toLowerCase().includes(filters.teacher.toLowerCase());
      
      let matchCalendar = true;
      if (filters.calendar && filters.calendar !== 'all') {
        matchCalendar = info.calendar_source === filters.calendar;
      }
      
      return matchName && matchProgram && matchTeacher && matchCalendar;
    });

    // SẮP XẾP THEO THỜI GIAN BẮT ĐẦU
    result.sort((a, b) => {
      const timeA = new Date(a.start?.dateTime || a.start).getTime();
      const timeB = new Date(b.start?.dateTime || b.start).getTime();
      return timeA - timeB;
    });

    return result;
  }, [groupedClasses, filters, calendarFilter]);

  // ================= PHÂN TRANG =================
  const paginatedClasses = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    return filteredClasses.slice(start, end);
  }, [filteredClasses, currentPage, pageSize]);

  const totalPages = Math.ceil(filteredClasses.length / pageSize);

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

  const handleRowClick = (cls) => {
    if (cls._isRecurringGroup && cls._recurringEvents) {
      setSelectedRecurringEvents(cls._recurringEvents);
    }
  };

  // ================= Export Excel =================
  const handleExportExcel = () => {
    if (!filteredClasses || filteredClasses.length === 0) {
      alert("Không có dữ liệu để export!");
      return;
    }

    const data = filteredClasses.map((cls) => {
      const info = extractClassInfo(cls);
      
      let recurrenceInfo = "";
      if (cls._isRecurringGroup) {
        recurrenceInfo = `Lặp lại (${cls._recurringCount} lần)`;
      } else if (info.recurrence_description) {
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
    
    const colWidths = [
      { wch: 15 }, { wch: 30 }, { wch: 20 }, { wch: 20 }, { wch: 20 },
      { wch: 40 }, { wch: 15 }, { wch: 10 }, { wch: 25 }, { wch: 25 },
      { wch: 30 }, { wch: 20 }, { wch: 40 }, { wch: 15 },
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

  // ================= THỐNG KÊ =================
  const stats = useMemo(() => {
    const oddCount = filteredClasses.filter(cls => {
      const info = extractClassInfo(cls);
      return info.calendar_source === 'odd';
    }).length;
    
    const evenCount = filteredClasses.filter(cls => {
      const info = extractClassInfo(cls);
      return info.calendar_source === 'even';
    }).length;
    
    const recurringCount = filteredClasses.filter(cls => cls._isRecurringGroup).length;
    const totalInstances = groupedClasses.reduce((total, cls) => {
      if (cls._isRecurringGroup) {
        return total + cls._recurringCount;
      }
      return total + 1;
    }, 0);
    
    return {
      total: filteredClasses.length,
      odd: oddCount,
      even: evenCount,
      recurring: recurringCount,
      totalInstances: totalInstances
    };
  }, [filteredClasses, groupedClasses]);

  return (
    <div className={styles.tableContainer}>
      {/* ================= STATS & FILTERS ================= */}
      <div className={styles.headerSection}>
        <div className={styles.stats}>
          {/*
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Total groups:</span>
            <span className={styles.statValue}>{stats.total}</span>
          </div>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Total instances:</span>
            <span className={styles.statValue}>{stats.totalInstances}</span>
          </div>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Recurring groups:</span>
            <span className={styles.statValue}>{stats.recurring}</span>
          </div>
          */}
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
          <div className={styles.filterInputWrapper}>
            <input
              type="text"
              name="name"
              placeholder="Tìm theo tên lớp"
              value={filters.name}
              onChange={handleFilterChange}
              className={styles.filterInput}
            />
            {filters.name && (
              <button className={styles.filterClearBtn} onClick={() => handleClearFilter("name")}>✕</button>
            )}
          </div>
          <div className={styles.filterInputWrapper}>
            <input
              type="text"
              name="program"
              placeholder="Tìm theo chương trình"
              value={filters.program}
              onChange={handleFilterChange}
              className={styles.filterInput}
            />
            {filters.program && (
              <button className={styles.filterClearBtn} onClick={() => handleClearFilter("program")}>✕</button>
            )}
          </div>
          <div className={styles.filterInputWrapper}>
            <input
              type="text"
              name="teacher"
              placeholder="Tìm theo giáo viên"
              value={filters.teacher}
              onChange={handleFilterChange}
              className={styles.filterInput}
            />
            {filters.teacher && (
              <button className={styles.filterClearBtn} onClick={() => handleClearFilter("teacher")}>✕</button>
            )}
          </div>
          <select
            name="calendar"
            value={filters.calendar}
            onChange={handleFilterChange}
            className={styles.filterSelect}
          >
            <option value="all">Tất cả Calendar</option>
            <option value="odd">📘 Calendar Lẻ (Giờ lẻ: 1,3,5...)</option>
            <option value="even">📗 Calendar Chẵn (Giờ chẵn: 2,4,6...)</option>
          </select>
        </div>
      </div>

      {/* ================= TABLE ================= */}
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.colCalendar}>Lịch</th>
              <th className={styles.colSubject}>Tiêu Đề</th>
              <th className={styles.colClassName}>Tên Lớp</th>
              <th className={styles.colTeacher}>Giáo Viên</th>
              <th className={styles.colProgram}>Chương Trình</th>
              <th className={styles.colZoom}>Link</th>
              <th className={styles.colMeetingID}>Meeting ID</th>
              <th className={styles.colPasscode}>Passcode</th>
              <th className={styles.colStart}>Start</th>
              <th className={styles.colEnd}>End</th>
              <th className={styles.colRecurrence}>Lặp Lại</th>
            </tr>
          </thead>
          <tbody>
            {paginatedClasses.length === 0 ? (
              <tr>
                <td colSpan="11" className={styles.noData}>
                  📭 No classes found. Try different filters.
                </td>
              </tr>
            ) : (
              paginatedClasses.map((cls) => {
                const info = extractClassInfo(cls);
                
                return (
                  <tr 
                    key={cls.id} 
                    className={`${styles.tableRow} ${
                      info.calendar_source === 'odd' ? styles.rowOdd : styles.rowEven
                    } ${cls._isRecurringGroup ? styles.recurringGroup : ''}`}
                    onClick={() => handleRowClick(cls)}
                    style={{ cursor: cls._isRecurringGroup ? 'pointer' : 'default' }}
                  >
                    <td className={styles.calendarCell}>
                      <div className={`${styles.calendarBadge} ${
                        info.calendar_source === 'odd' ? styles.badgeOdd : styles.badgeEven
                      }`}>
                        {info.calendar_badge}
                      </div>
                    </td>
                    
                    <td>
                      <div className={styles.subjectCell}>
                        <span className={styles.subjectText}>{cls.summary}</span>
                        {cls._isRecurringGroup && (
                          <span className={styles.recurrenceGroupBadge} title={`Nhóm lặp lại (${cls._recurringCount} lần)`}>
                            🔄 {cls._recurringCount}
                          </span>
                        )}
                      </div>
                    </td>
                    
                    <td>{info.classname || "N/A"}</td>
                    
                    <td>
                      <div className={styles.teacherCell}>
                        <span>{info.teacher}</span>
                      </div>
                    </td>
                    
                    <td>{info.program}</td>
                    
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
                    
                    <td className={styles.timeCell}>
                      {formatDateTime(cls.start?.dateTime || cls.start)}
                    </td>
                    
                    <td className={styles.timeCell}>
                      {formatDateTime(cls.end?.dateTime || cls.end)}
                    </td>
                    
                    <td>
                      {cls._isRecurringGroup ? (
                        <div className={styles.recurrenceInfo}>
                          <span className={styles.recurrenceCount}>
                            🔁 {cls._recurringCount} lần
                          </span>
                          <span className={styles.recurrenceRange}>
                            {formatDateTime(cls._nextOccurrence?.start?.dateTime || cls._nextOccurrence?.start)}
                            {" → "}
                            {formatDateTime(cls._lastOccurrence?.start?.dateTime || cls._lastOccurrence?.start)}
                          </span>
                        </div>
                      ) : info.recurrence_description ? (
                        <span className={styles.recurrenceText} title={info.recurrence_description}>
                          🔁 {info.recurrence_description.length > 20 
                            ? info.recurrence_description.substring(0, 20) + "..."
                            : info.recurrence_description}
                        </span>
                      ) : (
                        <span className={styles.naText}>-</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ================= PHÂN TRANG ================= */}
      <div className={styles.pagination}>
        <div className={styles.paginationInfo}>
          Hiển thị {paginatedClasses.length} / {filteredClasses.length} nhóm sự kiện
        </div>
        <div className={styles.paginationControls}>
          <select 
            value={pageSize} 
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setCurrentPage(1);
            }}
            className={styles.pageSizeSelect}
          >
            <option value={10}>10 / trang</option>
            <option value={20}>20 / trang</option>
            <option value={50}>50 / trang</option>
            <option value={100}>100 / trang</option>
          </select>
          
          <button 
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className={styles.pageButton}
          >
            ←
          </button>
          <span className={styles.pageInfo}>
            Trang {currentPage} / {totalPages}
          </span>
          <button 
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className={styles.pageButton}
          >
            →
          </button>
        </div>
      </div>

      {/* ================= FOOTER & EXPORT ================= */}
      <div className={styles.footer}>
        <div className={styles.footerStats}>
          Showing <strong>{filteredClasses.length}</strong> groups 
          (total <strong>{stats.totalInstances}</strong> instances)
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
            📥 Export Excel ({filteredClasses.length} groups)
          </button>
        </div>
      </div>

      {/* ================= MODAL HIỂN THỊ SỰ KIỆN LẶP LẠI ================= */}
      {selectedRecurringEvents && (
        <RecurrenceModal 
          events={selectedRecurringEvents}
          onClose={() => setSelectedRecurringEvents(null)}
        />
      )}
    </div>
  );
}