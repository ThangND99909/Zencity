import React, { useState, useMemo } from "react";
import styles from "./ClassTable.module.css";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";
import { parseZoomInfo } from "../utils/sanitizeDescription";

export default function ClassTable({ classes, onEdit, onDelete }) {
  const [copiedItem, setCopiedItem] = useState(null);

  // --- Bộ lọc ---
  const [filters, setFilters] = useState({
    name: "",
    program: "",
    teacher: "",
  });

  const handleFilterChange = (e) => {
    setFilters({ ...filters, [e.target.name]: e.target.value });
  };

  // Trích xuất thông tin từ description và các field trực tiếp
  const extractClassInfo = (cls) => {
    const rawDescription = cls.description || "";
    const { zoomLink, meetingId, passcode, program, teacher, classname } = parseZoomInfo(rawDescription);

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
    };
  };

  // ================= Lọc lớp =================
  const filteredClasses = useMemo(() => {
    return classes.filter((cls) => {
      // ✅ FILTER QUAN TRỌNG: Loại bỏ events đã bị xóa
      if (cls.status === "cancelled") return false;
      
      const info = extractClassInfo(cls);
      const matchName = cls.summary.toLowerCase().includes(filters.name.toLowerCase());
      const matchProgram = info.program.toLowerCase().includes(filters.program.toLowerCase());
      const matchTeacher = info.teacher.toLowerCase().includes(filters.teacher.toLowerCase());
      return matchName && matchProgram && matchTeacher;
    });
  }, [classes, filters]);

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
    if (!classes || classes.length === 0) return;

    const data = classes.map((cls) => {
      const info = extractClassInfo(cls);
      return {
        Name: cls.summary || "",
        ClassName: info.classname || "",
        Teacher: info.teacher,
        ZoomLink: info.zoom_link,
        MeetingID: info.meeting_id,
        Passcode: info.passcode,
        Program: info.program,
        Start: cls.start?.dateTime || "",
        End: cls.end?.dateTime || "",
      };
    });

    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Classes");

    const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
    const blob = new Blob([excelBuffer], { type: "application/octet-stream" });
    saveAs(blob, "ClassList.xlsx");
  };

  return (
    <div className={styles.tableContainer}>
      {/* ================= Filter Inputs ================= */}
      <div className={styles.filters}>
        <input
          type="text"
          name="name"
          placeholder="Tìm theo tên lớp"
          value={filters.name}
          onChange={handleFilterChange}
        />
        <input
          type="text"
          name="program"
          placeholder="Tìm theo môn học"
          value={filters.program}
          onChange={handleFilterChange}
        />
        <input
          type="text"
          name="teacher"
          placeholder="Tìm theo giáo viên"
          value={filters.teacher}
          onChange={handleFilterChange}
        />
      </div>

      {/* ================= Table ================= */}
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Subject</th>
            <th>Class Name</th>
            <th>Teacher</th>
            <th>Zoom Link</th>
            <th>Meeting ID</th>
            <th>Passcode</th>
            <th>Program</th>
            <th>Start</th>
            <th>End</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filteredClasses.map((cls) => {
            const info = extractClassInfo(cls);
            return (
              <tr key={cls.id}>
                <td>{cls.summary}</td>
                <td>{info.classname || "N/A"}</td>
                <td>{info.teacher}</td>
                <td>
                  {info.zoom_link ? (
                    <div className={styles.zoomLinkContainer}>
                      <span title={info.zoom_link}>{shortenLink(info.zoom_link)}</span>
                      <button
                        className={`${styles.copyButton} ${copiedItem === `${cls.id}-zoom` ? styles.copied : ""}`}
                        onClick={(e) => handleCopy(cls.id, info.zoom_link, "zoom", e)}
                        title="Copy Zoom link"
                      >
                        {copiedItem === `${cls.id}-zoom` ? "✅" : "📋"}
                      </button>
                      <button
                        className={styles.openButton}
                        onClick={(e) => handleOpenLink(info.zoom_link, e)}
                        title="Open Zoom link"
                      >
                        🔗
                      </button>
                    </div>
                  ) : "N/A"}
                </td>
                <td>
                  {info.meeting_id ? (
                    <div className={styles.meetingIdContainer}>
                      <span>{info.meeting_id}</span>
                      <button
                        className={`${styles.copyButton} ${copiedItem === `${cls.id}-meeting` ? styles.copied : ""}`}
                        onClick={(e) => handleCopy(cls.id, info.meeting_id, "meeting", e)}
                        title="Copy Meeting ID"
                      >
                        {copiedItem === `${cls.id}-meeting` ? "✅" : "📋"}
                      </button>
                    </div>
                  ) : "N/A"}
                </td>
                <td>
                  {info.passcode ? (
                    <div className={styles.passcodeContainer}>
                      <span>{info.passcode}</span>
                      <button
                        className={`${styles.copyButton} ${copiedItem === `${cls.id}-passcode` ? styles.copied : ""}`}
                        onClick={(e) => handleCopy(cls.id, info.passcode, "passcode", e)}
                        title="Copy Passcode"
                      >
                        {copiedItem === `${cls.id}-passcode` ? "✅" : "📋"}
                      </button>
                    </div>
                  ) : "N/A"}
                </td>
                <td>{info.program}</td>
                <td>
                  {new Date(cls.start.dateTime).toLocaleString("vi-VN", {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                  })}
                </td>
                <td>
                  {new Date(cls.end.dateTime).toLocaleString("vi-VN", {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                  })}
                </td>
                <td className={styles.actions}>
                  <button className={styles.editBtn} onClick={() => onEdit(cls)}>✏️</button>
                  <button className={styles.deleteBtn} onClick={() => onDelete(cls.id)}>🗑️</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* ================= Export Button ================= */}
      <div style={{ textAlign: "right", marginTop: "10px" }}>
        <button className={`${styles.btn} ${styles.btnWarning}`} onClick={handleExportExcel}>
          📥 Export Excel
        </button>
      </div>
    </div>
  );
}
