// frontend/src/components/EditRecurringModal.js
import { useState } from "react";
import styles from "./EditRecurringModal.module.css";

export default function EditRecurringModal({
  event,
  onConfirm,
  onCancel
}) {
  const [editMode, setEditMode] = useState('this');

  const handleConfirm = () => {
    onConfirm(editMode);
  };

  if (!event) return null;

  return (
    <div className={styles.editRecurringOverlay}>
      <div className={styles.editRecurringBox}>
        <div className={styles.editOptions}>
          <p><strong>Chọn cách chỉnh sửa:</strong></p>
          
          <label className={styles.editOption}>
            <input 
              type="radio" 
              name="editMode" 
              value="this"
              checked={editMode === 'this'}
              onChange={() => setEditMode('this')}
            />
            <div className={styles.editOptionLabel}>
              <span className={styles.editOptionTitle}>Chỉ sự kiện này</span>
              <span className={styles.editOptionDesc}>
                Chỉ cập nhật sự kiện đang chọn
              </span>
            </div>
          </label>
          
          <label className={styles.editOption}>
            <input 
              type="radio" 
              name="editMode" 
              value="following"
              checked={editMode === 'following'}
              onChange={() => setEditMode('following')}
            />
            <div className={styles.editOptionLabel}>
              <span className={styles.editOptionTitle}>Sự kiện này và các sự kiện tiếp theo</span>
              <span className={styles.editOptionDesc}>
                Cập nhật sự kiện này và tất cả sự kiện sau nó trong chuỗi
              </span>
            </div>
          </label>
          
          
        </div>
        
        <div className={styles.warningNote}>
          ⚠️ <strong>Lưu ý:</strong> Việc chỉnh sửa múi giờ hoặc lịch lặp có thể ảnh hưởng đến nhiều sự kiện.
        </div>
        
        <div className={styles.editRecurringActions}>
          <button 
            className={`${styles.editRecurringBtn} ${styles.cancel}`}
            onClick={onCancel}
          >
            Hủy
          </button>
          <button 
            className={`${styles.editRecurringBtn} ${styles.confirm}`}
            onClick={handleConfirm}
          >
            Tiếp tục chỉnh sửa
          </button>
        </div>
      </div>
    </div>
  );
}
