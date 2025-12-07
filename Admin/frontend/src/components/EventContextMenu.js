// frontend/src/components/EventContextMenu.js
import React, { useEffect, useRef } from "react";
import styles from "./EventContextMenu.module.css";

export default function EventContextMenu({
  position = { x: 0, y: 0 },
  event = null,
  isRecurring = false,
  onClose,
  onDelete,
  onEdit,
  onViewDetails
}) {
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('contextmenu', handleClickOutside);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('contextmenu', handleClickOutside);
    };
  }, [onClose]);

  if (!event || !position.x || !position.y) return null;

  const handleDeleteClick = () => {
    onDelete(event);
    onClose();
  };

  const handleEditClick = () => {
    onEdit(event);
    onClose();
  };

  const handleViewDetailsClick = () => {
    onViewDetails(event);
    onClose();
  };

  return (
    <div 
      ref={menuRef}
      className={styles.contextMenu}
      style={{
        top: `${position.y}px`,
        left: `${position.x}px`,
      }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className={styles.contextMenuHeader}>
        📅 {event.name}
        <div className={styles.contextMenuSubtitle}>
          {event.teacher} • {new Date(event.start?.dateTime || event.start).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
      
      <div className={styles.contextMenuDivider}></div>
      
      <div 
        className={styles.contextMenuItem}
        onClick={handleViewDetailsClick}
      >
        👁️ Xem chi tiết
      </div>
      
      <div 
        className={styles.contextMenuItem}
        onClick={handleEditClick}
      >
        ✏️ Chỉnh sửa
      </div>
      
      <div 
        className={`${styles.contextMenuItem} ${styles.deleteItem}`}
        onClick={handleDeleteClick}
      >
        🗑️ Xóa sự kiện
      </div>
      
      {isRecurring && (
        <div className={styles.recurringNote}>
          ⚠️ Sự kiện lặp lại
        </div>
      )}
    </div>
  );
}