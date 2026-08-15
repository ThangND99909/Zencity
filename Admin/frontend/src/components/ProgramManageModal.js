// frontend/src/components/ProgramManageModal.js
import { useState, useEffect } from "react";
import styles from "./ProgramManageModal.module.css";
import { getPrograms, createProgram, updateProgram, deleteProgram } from "../services/api";
import ModalShell from "./ModalShell";
import ConfirmationDialog from "./ConfirmationDialog";

export default function ProgramManageModal({ isOpen, onClose, onProgramsUpdate }) {
  const [programs, setPrograms] = useState([]);
  const [newProgramName, setNewProgramName] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState(""); // 'success' | 'error'
  const [programToDelete, setProgramToDelete] = useState(null);

  // Load programs khi modal mở
  useEffect(() => {
    if (isOpen) {
      loadPrograms();
    }
  }, [isOpen]);

  const loadPrograms = async () => {
    setLoading(true);
    try {
      const data = await getPrograms();
      setPrograms(data);
      setMessage("");
    } catch (error) {
      setMessage("❌ Lỗi tải danh sách chương trình: " + error.message);
      setMessageType("error");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddProgram = async () => {
    if (!newProgramName.trim()) {
      setMessage("⚠️ Vui lòng nhập tên chương trình");
      setMessageType("error");
      return;
    }

    setLoading(true);
    try {
      const newProgram = await createProgram(newProgramName);
      setPrograms([...programs, newProgram]);
      setNewProgramName("");
      setMessage("✅ Thêm chương trình thành công");
      setMessageType("success");
      // Notify parent component
      onProgramsUpdate && onProgramsUpdate();
      
      // Clear message after 2 seconds
      setTimeout(() => setMessage(""), 2000);
    } catch (error) {
      setMessage("❌ " + error.message);
      setMessageType("error");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleEditProgram = (program) => {
    setEditingId(program.id);
    setEditingName(program.name);
  };

  const handleSaveEdit = async () => {
    if (!editingName.trim()) {
      setMessage("⚠️ Vui lòng nhập tên chương trình");
      setMessageType("error");
      return;
    }

    setLoading(true);
    try {
      const updated = await updateProgram(editingId, editingName);
      setPrograms(programs.map(p => p.id === editingId ? updated : p));
      setEditingId(null);
      setEditingName("");
      setMessage("✅ Cập nhật chương trình thành công");
      setMessageType("success");
      onProgramsUpdate && onProgramsUpdate();
      
      setTimeout(() => setMessage(""), 2000);
    } catch (error) {
      setMessage("❌ " + error.message);
      setMessageType("error");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteProgram = async (id) => {
    setLoading(true);
    try {
      await deleteProgram(id);
      setPrograms(programs.filter(p => p.id !== id));
      setMessage("✅ Xóa chương trình thành công");
      setMessageType("success");
      onProgramsUpdate && onProgramsUpdate();
      
      setTimeout(() => setMessage(""), 2000);
      setProgramToDelete(null);
    } catch (error) {
      setMessage("❌ " + error.message);
      setMessageType("error");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditingName("");
    setNewProgramName("");
    setMessage("");
    onClose();
  };

  if (!isOpen) return null;

  return (
    <ModalShell
      title="Quản lý chương trình"
      onClose={handleCancel}
      closeOnBackdrop
      panelClassName={styles.modalContent}
    >
        <div className={styles.modalHeader}>
          <h2>📚 Quản lý chương trình</h2>
          <button className={styles.closeBtn} onClick={handleCancel} aria-label="Đóng cửa sổ quản lý chương trình">×</button>
        </div>

        {/* Message */}
        {message && (
          <div role={messageType === "error" ? "alert" : "status"} className={`${styles.message} ${styles[messageType]}`}>
            {message}
          </div>
        )}

        {/* Add New Program */}
        <div className={styles.section}>
          <h3>➕ Thêm chương trình mới</h3>
          <div className={styles.addForm}>
            <input
              type="text"
              aria-label="Tên chương trình mới"
              placeholder="Nhập tên chương trình (vd: ASUS)"
              value={newProgramName}
              onChange={(e) => setNewProgramName(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleAddProgram()}
              disabled={loading}
              className={styles.input}
            />
            <button
              onClick={handleAddProgram}
              disabled={loading || !newProgramName.trim()}
              className={styles.btnAdd}
            >
              {loading ? "⏳..." : "Thêm"}
            </button>
          </div>
        </div>

        {/* Programs List */}
        <div className={styles.section}>
          <h3>Danh sách chương trình ({programs.length})</h3>
          <div className={styles.programsList}>
            {loading && programs.length === 0 ? (
              <div className={styles.loadingText}>⏳ Đang tải...</div>
            ) : programs.length === 0 ? (
              <div className={styles.emptyText}>📭 Không có chương trình nào</div>
            ) : (
              programs.map((program) => (
                <div key={program.id} className={styles.programItem}>
                  {editingId === program.id ? (
                    <div className={styles.editForm}>
                      <input
                        type="text"
                        aria-label={`Tên chương trình ${program.name}`}
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        className={styles.input}
                        autoFocus
                      />
                      <button
                        onClick={handleSaveEdit}
                        disabled={loading}
                        className={styles.btnSave}
                      >
                        💾 Lưu
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        disabled={loading}
                        className={styles.btnCancel}
                      >
                        ❌ Hủy
                      </button>
                    </div>
                  ) : (
                    <div className={styles.programContent}>
                      <div className={styles.programName}>{program.name}</div>
                      <div className={styles.programId}>ID: {program.id}</div>
                      <div className={styles.programActions}>
                        <button
                          onClick={() => handleEditProgram(program)}
                          disabled={loading}
                          className={styles.btnEdit}
                          title="Chỉnh sửa"
                          aria-label={`Chỉnh sửa chương trình ${program.name}`}
                        >
                          ✏️
                        </button>
                        <button
                          onClick={() => setProgramToDelete(program)}
                          disabled={loading}
                          className={styles.btnDelete}
                          title="Xoá"
                          aria-label={`Xóa chương trình ${program.name}`}
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Footer */}
        <div className={styles.modalFooter}>
          <button onClick={handleCancel} className={styles.btnClose}>
            ❌ Đóng
          </button>
        </div>
      <ConfirmationDialog
        isOpen={Boolean(programToDelete)}
        title="Xóa chương trình"
        message={`Bạn có chắc muốn xóa chương trình “${programToDelete?.name || ""}”?`}
        confirmLabel="Xóa chương trình"
        tone="danger"
        busy={loading}
        onCancel={() => setProgramToDelete(null)}
        onConfirm={() => handleDeleteProgram(programToDelete.id)}
      />
    </ModalShell>
  );
}
