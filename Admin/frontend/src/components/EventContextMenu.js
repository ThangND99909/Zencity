// frontend/src/components/EventContextMenu.js
import { useEffect, useRef } from "react";
import styles from "./EventContextMenu.module.css";

export default function EventContextMenu({
  position = { x: 0, y: 0 },
  event = null,
  isRecurring = false,
  onClose,
  onDelete,
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
    menuRef.current?.querySelector('[role="menuitem"]')?.focus();

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
      role="menu"
      aria-label={`Tùy chọn cho ${event.name}`}
      onKeyDown={(e) => {
        const items = [...e.currentTarget.querySelectorAll('[role="menuitem"]')];
        const index = items.indexOf(document.activeElement);
        if (e.key === "Escape") onClose();
        if (e.key === "ArrowDown") {
          e.preventDefault();
          items[(index + 1) % items.length]?.focus();
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          items[(index - 1 + items.length) % items.length]?.focus();
        }
      }}
    >
      <div className={styles.contextMenuHeader}>
        📅 {event.name}
        <div className={styles.contextMenuSubtitle}>
          {event.teacher} • {new Date(event.start?.dateTime || event.start).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
      
      <div className={styles.contextMenuDivider}></div>
      
      <button
        type="button"
        role="menuitem"
        className={styles.contextMenuItem}
        onClick={handleViewDetailsClick}
      >
        👁️ Xem chi tiết
      </button>
      
      <button
        type="button"
        role="menuitem"
        className={`${styles.contextMenuItem} ${styles.deleteItem}`}
        onClick={handleDeleteClick}
      >
        🗑️ Xóa sự kiện
      </button>
      
      {isRecurring && (
        <div className={styles.recurringNote}>
          ⚠️ Sự kiện lặp lại
        </div>
      )}
    </div>
  );
}
