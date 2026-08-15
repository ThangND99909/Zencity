// frontend/src/components/ClassTable.js
import React, { useState, useMemo, useEffect, useCallback } from "react";
import styles from "./ClassTable.module.css";
import { parseZoomInfo } from "../utils/sanitizeDescription";
import { getPrograms } from "../services/api";
import DeleteConfirmationModal from "./DeleteConfirmationModal";

const ALL_PROGRAMS = "__all_programs__";

const getProgramHeaderStyle = (programName = "") => {
  const hash = Array.from(programName).reduce(
    (value, character) => ((value * 31) + character.charCodeAt(0)) >>> 0,
    0
  );
  const hue = hash % 360;
  return {
    "--program-color-start": `hsl(${hue}, 62%, 30%)`,
    "--program-color-end": `hsl(${(hue + 24) % 360}, 68%, 48%)`
  };
};

export default function ClassTable({ classes, onDelete, calendarFilter }) {
  const [copiedItem, setCopiedItem] = useState(null);
  const [eventToDelete, setEventToDelete] = useState(null);
  const [weekOffset, setWeekOffset] = useState(0);
  const [programsMap, setProgramsMap] = useState({}); // Map programId -> programName
  const [selectedProgram, setSelectedProgram] = useState(ALL_PROGRAMS);

  // ✅ LOAD PROGRAMS TO MAP ID TO NAME
  useEffect(() => {
    const loadPrograms = async () => {
      try {
        const data = await getPrograms();
        const map = {};
        data.forEach(p => {
          map[p.id] = p.name;
        });
        setProgramsMap(map);
      } catch (error) {
        console.error("❌ Failed to load programs:", error);
      }
    };
    loadPrograms();
  }, []);

  // ✅ HELPER FUNCTION: GET PROGRAM NAME FROM ID
  const getProgramName = useCallback((programId) => {
    if (!programId) return "N/A";
    return programsMap[programId] || programId; // Return name if found, otherwise return ID
  }, [programsMap]);

  // Trích xuất thông tin từ description và các field trực tiếp
  const extractClassInfo = useCallback((cls) => {
    const rawDescription = cls.description || "";
    const { zoomLink, meetingId, passcode, program, teacher, classname } = parseZoomInfo(rawDescription);
    const plainDescription = rawDescription
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/p>/gi, "\n")
      .replace(/<\/?[^>]+(>|$)/g, "")
      .trim();
    const roomLine = plainDescription
      .split("\n")
      .map((line) => line.trim())
      .find((line) => /^Room\b/i.test(line));

    const calendarSource = cls._calendar_source || 
                          (cls.calendar_id ? (cls.calendar_id.includes('even') ? 'even' : 'odd') : 'odd');
    
    const calendarInfo = {
      source: calendarSource,
      name: calendarSource === 'odd' ? '📘 Calendar Lẻ' : '📗 Calendar Chẵn'
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
      zoom_room: cls.zoom_room || cls.room || roomLine || cls.summary || "",
      program: getProgramName(cls.program || program || ""),
      calendar_source: calendarInfo.source,
      calendar_name: calendarInfo.name,
      recurrence: cls.recurrence,
      recurringEventId: cls.recurringEventId,
      recurrence_description: cls.recurrence_description || ""
    };
  }, [getProgramName]);

  // ⚡ Memo hóa kết quả extractClassInfo theo cls.id để không parse regex lặp lại
  //    nhiều lần cho cùng một lớp trong mỗi render.
  const infoById = useMemo(() => {
    const map = new Map();
    classes.forEach((cls) => {
      if (cls?.id) map.set(cls.id, extractClassInfo(cls));
    });
    return map;
  }, [classes, extractClassInfo]);

  const getInfo = useCallback(
    (cls) => (cls?.id && infoById.get(cls.id)) || extractClassInfo(cls),
    [infoById, extractClassInfo]
  );

  // ================= TUẦN HIỆN TẠI =================
  const weekBounds = useMemo(() => {
    const now = new Date();
    const day = now.getDay(); // 0=CN, 1=T2...
    const diffToMonday = day === 0 ? -6 : 1 - day;
    const monday = new Date(now);
    monday.setDate(now.getDate() + diffToMonday + weekOffset * 7);
    monday.setHours(0, 0, 0, 0);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    sunday.setHours(23, 59, 59, 999);
    return { start: monday, end: sunday };
  }, [weekOffset]);

  const weekLabel = useMemo(() => {
    const fmt = (d) =>
      d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
    return `${fmt(weekBounds.start)} – ${fmt(weekBounds.end)}`;
  }, [weekBounds]);

  const weekDays = useMemo(() => {
    const dayNames = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"];
    return dayNames.map((name, index) => {
      const date = new Date(weekBounds.start);
      date.setDate(weekBounds.start.getDate() + index);
      return { name, date };
    });
  }, [weekBounds]);

  const weekClasses = useMemo(() => {
    return classes.filter((cls) => {
      if (cls.status === "cancelled") return false;
      const clsStart = new Date(cls.start?.dateTime || cls.start);
      return clsStart >= weekBounds.start && clsStart <= weekBounds.end;
    });
  }, [classes, weekBounds]);

  // ================= NHÓM CÁC SỰ KIỆN LẶP LẠI =================
  const groupedClasses = useMemo(() => {
    // Nhóm các sự kiện theo recurringEventId
    const recurringGroups = new Map();
    const nonRecurring = [];
    
    weekClasses.forEach(cls => {
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
  }, [weekClasses]);

  const programOptions = useMemo(() => {
    const activeNames = new Set();
    weekClasses.forEach((cls) => {
      const info = getInfo(cls);
      if (info.program && info.program !== "N/A") activeNames.add(info.program);
    });

    const sortNames = (names) => names.sort((a, b) =>
      a.localeCompare(b, "vi", { sensitivity: "base" })
    );
    const activePrograms = sortNames(Array.from(activeNames));
    const inactivePrograms = sortNames(
      Array.from(new Set(Object.values(programsMap))).filter((name) => name && !activeNames.has(name))
    );
    return [...activePrograms, ...inactivePrograms];
  }, [programsMap, weekClasses, getInfo]);

  useEffect(() => {
    if (programOptions.length === 0) {
      setSelectedProgram(ALL_PROGRAMS);
      return;
    }
    if (!selectedProgram || (selectedProgram !== ALL_PROGRAMS && !programOptions.includes(selectedProgram))) {
      setSelectedProgram(programOptions[0]);
    }
  }, [programOptions, selectedProgram]);

  const scheduleClasses = useMemo(() => {
    return weekClasses.filter((cls) => {
      if (calendarFilter && calendarFilter !== "both") {
        const calendarSource = cls._calendar_source || "odd";
        if (calendarFilter !== calendarSource) return false;
      }

      if (selectedProgram && selectedProgram !== ALL_PROGRAMS) {
        if (getInfo(cls).program !== selectedProgram) return false;
      }

      return true;
    });
  }, [weekClasses, selectedProgram, calendarFilter, getInfo]);

  const scheduleRows = useMemo(() => {
    const rows = new Map();

    scheduleClasses.forEach((cls) => {
      const info = getInfo(cls);
      const rowKey = [
        info.program,
        info.classname,
        cls.summary || "",
        info.meeting_id || info.zoom_link || cls.id
      ].join("::");

      if (!rows.has(rowKey)) {
        rows.set(rowKey, {
          key: rowKey,
          summary: cls.summary || "",
          info,
          eventsByDay: Array.from({ length: 7 }, () => [])
        });
      }

      const start = new Date(cls.start?.dateTime || cls.start);
      const dayIndex = (start.getDay() + 6) % 7;
      rows.get(rowKey).eventsByDay[dayIndex].push(cls);
    });

    return Array.from(rows.values())
      .map((row) => ({
        ...row,
        eventsByDay: row.eventsByDay.map((events) => events.sort((a, b) =>
          new Date(a.start?.dateTime || a.start) - new Date(b.start?.dateTime || b.start)
        ))
      }))
      .sort((a, b) => (a.info.classname || a.summary).localeCompare(
        b.info.classname || b.summary,
        "vi",
        { sensitivity: "base" }
      ));
  }, [scheduleClasses, getInfo]);

  const scheduleSections = useMemo(() => {
    if (selectedProgram !== ALL_PROGRAMS) {
      return [{ program: selectedProgram, rows: scheduleRows }];
    }

    const rowsByProgram = new Map(programOptions.map((program) => [program, []]));
    scheduleRows.forEach((row) => {
      if (!rowsByProgram.has(row.info.program)) rowsByProgram.set(row.info.program, []);
      rowsByProgram.get(row.info.program).push(row);
    });
    return Array.from(rowsByProgram, ([program, rows]) => ({ program, rows }));
  }, [selectedProgram, programOptions, scheduleRows]);

  // ================= Lọc lớp =================
  const filteredClasses = useMemo(() => {
    let result = groupedClasses.filter((cls) => {
      if (calendarFilter && calendarFilter !== 'both') {
        const calendarSource = cls._calendar_source || 'odd';
        if (calendarFilter !== calendarSource) return false;
      }
      return true;
    });

    // SẮP XẾP THEO THỜI GIAN BẮT ĐẦU
    result.sort((a, b) => {
      const timeA = new Date(a.start?.dateTime || a.start).getTime();
      const timeB = new Date(b.start?.dateTime || b.start).getTime();
      return timeA - timeB;
    });

    return result;
  }, [groupedClasses, calendarFilter]);

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

  const handleDeleteClick = (event, eventInfo, e) => {
    e.stopPropagation();
    setEventToDelete({
      ...event,
      name: event.name || event.summary || eventInfo.classname,
      teacher: eventInfo.teacher
    });
  };

  const handleConfirmDelete = async (deleteMode = "this") => {
    if (!eventToDelete?.id) return;
    await onDelete?.({
      ...eventToDelete,
      deleteMode,
      _confirmed: true
    });
    setEventToDelete(null);
  };

  // ================= Export Excel =================
  // ⚡ Lazy-load xlsx & file-saver (thư viện nặng ~0.8MB) chỉ khi người dùng export,
  //    để không nằm trong bundle tải lần đầu.
  const handleExportExcel = async () => {
    if (!filteredClasses || filteredClasses.length === 0) {
      return;
    }

    const XLSX = await import("xlsx");
    const { saveAs } = await import("file-saver");

    const data = filteredClasses.map((cls) => {
      const info = getInfo(cls);

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
    const totalInstances = groupedClasses.reduce((total, cls) => {
      if (cls._isRecurringGroup) {
        return total + cls._recurringCount;
      }
      return total + 1;
    }, 0);

    return { totalInstances };
  }, [groupedClasses]);

  return (
    <div className={styles.tableContainer}>
      <div className={styles.viewToolbar}>
        <div className={styles.weekNavBar}>
          <div className={styles.weekNavLeft}>
            <button
              className={styles.weekNavBtn}
              onClick={() => setWeekOffset(o => o - 1)}
            >
              ← Tuần trước
            </button>
          </div>

          <div className={styles.weekNavCenter}>
            <button
              className={`${styles.weekNavBtn} ${weekOffset === 0 ? styles.weekTodayActive : ""}`}
              onClick={() => setWeekOffset(0)}
            >
              Tuần này
            </button>
            <span className={styles.weekRange}>📅 {weekLabel}</span>
          </div>

          <div className={styles.weekNavRight}>
            <button
              className={styles.weekNavBtn}
              onClick={() => setWeekOffset(o => o + 1)}
            >
              Tuần sau →
            </button>
          </div>
        </div>

        <div className={styles.programNavigator}>
            <label className={styles.programSelectLabel}>
              <span>Chương trình:</span>
              <select
                value={selectedProgram}
                onChange={(e) => setSelectedProgram(e.target.value)}
                className={styles.programSelect}
                disabled={programOptions.length === 0}
              >
                {programOptions.length === 0 ? (
                  <option value="">Chưa có chương trình</option>
                ) : (
                  <>
                    <option value={ALL_PROGRAMS}>Tất cả chương trình</option>
                    {programOptions.map((programName) => (
                      <option key={programName} value={programName}>{programName}</option>
                    ))}
                  </>
                )}
              </select>
            </label>
            
        </div>
      </div>
      {/* ================= TABLE ================= */}
        <div className={styles.scheduleBoards}>
        {scheduleSections.map((scheduleSection) => (
        <section
          key={scheduleSection.program || "empty"}
          className={styles.scheduleBoard}
          style={getProgramHeaderStyle(scheduleSection.program)}
        >
          <div className={styles.scheduleBoardHeader}>
            <div className={styles.scheduleProgramTitle}>
              
              <h3>{scheduleSection.program || "Chưa có chương trình"}</h3>
            </div>
          </div>

          <p className={styles.mobileScrollHint}>Vuốt ngang để xem lịch của các ngày còn lại.</p>
          <div
            className={styles.scheduleTableWrapper}
            tabIndex="0"
            aria-label={`Bảng lịch chương trình ${scheduleSection.program}. Có thể cuộn ngang để xem đầy đủ.`}
          >
            <table className={styles.scheduleTable}>
              <thead>
                <tr>
                  <th className={styles.scheduleClassColumn}>Lớp</th>
                  <th className={styles.scheduleZoomColumn}>Zoom ID</th>
                  {weekDays.map((day) => (
                    <th key={day.name} className={styles.scheduleDayColumn}>
                      <span>{day.name}</span>
                      <small>{day.date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" })}</small>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scheduleSection.rows.length === 0 ? (
                  <tr>
                    <td colSpan="9" className={styles.scheduleEmpty}>
                      <span>📭</span>
                      Không có lớp thuộc chương trình này trong tuần đã chọn.
                    </td>
                  </tr>
                ) : (
                  scheduleSection.rows.map((row) => (
                    <tr key={row.key}>
                      <td className={styles.scheduleClassCell}>
                        <strong>{row.info.classname !== "N/A" ? row.info.classname : row.summary}</strong>
                      </td>
                      <td className={styles.scheduleZoomCell}>
                        {row.info.zoom_room && (
                          <strong className={styles.scheduleZoomRoom}>{row.info.zoom_room}</strong>
                        )}
                        {row.info.meeting_id ? (
                          <button
                            type="button"
                            className={styles.scheduleCopyValue}
                            onClick={(e) => handleCopy(row.key, row.info.meeting_id, "schedule-meeting", e)}
                            title="Copy Meeting ID"
                          >
                            <span>Zoom ID: {row.info.meeting_id}</span>
                            <span>{copiedItem === `${row.key}-schedule-meeting` ? "✓" : "📋"}</span>
                          </button>
                        ) : (
                          <span className={styles.naText}>N/A</span>
                        )}
                        {row.info.passcode && <small>Pass: {row.info.passcode}</small>}
                        {row.info.zoom_link && (
                          <button
                            type="button"
                            className={styles.scheduleZoomLink}
                            onClick={(e) => handleOpenLink(row.info.zoom_link, e)}
                            title={row.info.zoom_link}
                          >
                            <span>Zoom link:</span>
                            {row.info.zoom_link}
                          </button>
                        )}
                      </td>
                      {row.eventsByDay.map((events, dayIndex) => (
                        <td key={`${row.key}-${dayIndex}`} className={styles.scheduleDayCell}>
                          {events.length > 0 && (
                            <div className={styles.scheduleDayEvents}>
                              {events.map((event) => {
                                const eventInfo = getInfo(event);
                                const start = new Date(event.start?.dateTime || event.start);
                                const end = new Date(event.end?.dateTime || event.end);
                                const timeOptions = { hour: "2-digit", minute: "2-digit", hour12: false };
                                return (
                                  <div
                                    key={event.id}
                                    className={`${styles.scheduleEvent} ${
                                      eventInfo.calendar_source === "odd" ? styles.scheduleEventOdd : styles.scheduleEventEven
                                    }`}
                                    title={`${event.summary || eventInfo.classname}\n${formatDateTime(event.start?.dateTime || event.start)}`}
                                  >
                                    <strong>
                                      {start.toLocaleTimeString("vi-VN", timeOptions)} – {end.toLocaleTimeString("vi-VN", timeOptions)}
                                    </strong>
                                    <span>{eventInfo.teacher !== "N/A" ? eventInfo.teacher : "Chưa có giáo viên"}</span>
                                    <button
                                      type="button"
                                      className={styles.scheduleDeleteButton}
                                      onClick={(e) => handleDeleteClick(event, eventInfo, e)}
                                    >
                                      XÓA
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
        ))}
        </div>


      {/* ================= FOOTER & EXPORT ================= */}
      <div className={styles.footer}>
        <div className={styles.footerStats}>
          Tuần: <strong>{weekLabel}</strong> — <strong>{filteredClasses.length}</strong> nhóm
          (tổng <strong>{stats.totalInstances}</strong> buổi)
        </div>
        <div className={styles.exportSection}>
          <button 
            className={`${styles.exportButton} ${styles.btnWarning}`} 
            onClick={handleExportExcel}
            disabled={filteredClasses.length === 0}
          >
            📥 Xuất Excel ({filteredClasses.length} nhóm)
          </button>
        </div>
      </div>

      {eventToDelete && (
        <DeleteConfirmationModal
          event={eventToDelete}
          isRecurring={Boolean(eventToDelete.recurrence || eventToDelete.recurringEventId)}
          onConfirm={handleConfirmDelete}
          onCancel={() => setEventToDelete(null)}
        />
      )}
    </div>
  );
}
