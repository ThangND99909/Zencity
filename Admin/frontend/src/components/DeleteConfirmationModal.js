// frontend/src/components/DeleteConfirmationModal.js
import React, { useState } from "react";
import styles from "./DeleteConfirmationModal.module.css";

export default function DeleteConfirmationModal({
  event,
  onConfirm,
  onCancel,
  isRecurring = false
}) {
  const [deleteMode, setDeleteMode] = useState('this');

  console.log("🔍 DELETE MODAL DEBUG:", {
    eventName: event?.name,
    isRecurring: isRecurring,
    currentDeleteMode: deleteMode,
    hasRecurrence: event?.recurrence,
    hasRecurringEventId: event?.recurringEventId
  });

  const handleConfirm = () => {
    console.log("✅ CONFIRMING DELETE WITH MODE:", deleteMode);
    console.log("📋 EVENT DATA:", {
      id: event?.id,
      name: event?.name,
      recurrence: event?.recurrence,
      recurringEventId: event?.recurringEventId
    });
    onConfirm(deleteMode);
  };

  if (!event) return null;

  return (
    <div className={styles.deleteConfirmOverlay}>
      <div className={styles.deleteConfirmBox}>
        <div className={styles.deleteConfirmHeader}>
          🗑️ Xóa sự kiện
        </div>
        
        <div className={styles.deleteConfirmEventInfo}>
          <h4>{event.name}</h4>
          <p><strong>Giáo viên:</strong> {event.teacher}</p>
          <p><strong>Thời gian:</strong> {
            new Date(event.start?.dateTime || event.start).toLocaleString('vi-VN')
          }</p>
          {isRecurring && (
            <p><strong>⚠️ Đây là sự kiện lặp lại</strong></p>
          )}
        </div>
        
        {isRecurring ? (
          <div className={styles.deleteOptions}>
            <p><strong>Chọn cách xóa:</strong></p>
            
            <label className={styles.deleteOption}>
              <input 
                type="radio" 
                name="deleteMode" 
                value="this"
                checked={deleteMode === 'this'}
                onChange={() => setDeleteMode('this')}
              />
              <div className={styles.deleteOptionLabel}>
                <span className={styles.deleteOptionTitle}>Sự kiện này</span>
                <span className={styles.deleteOptionDesc}>
                  Chỉ xóa sự kiện đang chọn
                </span>
              </div>
            </label>
            
            <label className={styles.deleteOption}>
              <input 
                type="radio" 
                name="deleteMode" 
                value="following"
                checked={deleteMode === 'following'}
                onChange={() => setDeleteMode('following')}
              />
              <div className={styles.deleteOptionLabel}>
                <span className={styles.deleteOptionTitle}>Sự kiện này và các sự kiện tiếp theo</span>
                <span className={styles.deleteOptionDesc}>
                  Xóa sự kiện này và tất cả sự kiện sau nó trong chuỗi
                </span>
              </div>
            </label>
            
            <label className={styles.deleteOption}>
              <input 
                type="radio" 
                name="deleteMode" 
                value="all"
                checked={deleteMode === 'all'}
                onChange={() => setDeleteMode('all')}
              />
              <div className={styles.deleteOptionLabel}>
                <span className={styles.deleteOptionTitle}>Tất cả sự kiện</span>
                <span className={styles.deleteOptionDesc}>
                  Xóa toàn bộ chuỗi sự kiện lặp lại
                </span>
              </div>
            </label>
          </div>
        ) : (
          <div className={styles.nonRecurringWarning}>
            <p>Bạn có chắc chắn muốn xóa sự kiện này không?</p>
          </div>
        )}
        
        <div className={styles.deleteConfirmActions}>
          <button 
            className={`${styles.deleteConfirmBtn} ${styles.cancel}`}
            onClick={onCancel}
          >
            Hủy
          </button>
          <button 
            className={`${styles.deleteConfirmBtn} ${styles.delete}`}
            onClick={handleConfirm}
          >
            {deleteMode === 'all' ? 'Xóa tất cả' : 'Xóa'}
          </button>
        </div>
      </div>
    </div>
  );
}