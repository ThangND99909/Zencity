import styles from './LoadingOverlay.module.css';

const LoadingOverlay = ({ isLoading, type = 'default', message }) => {
  if (!isLoading) return null;

  const config = {
    classes: {
      icon: "📚",
      defaultMessage: "Đang tải danh sách lớp...",
      color: "#3b82f6"
    },
    add: {
      icon: "➕",
      defaultMessage: "Đang thêm lớp học mới...",
      color: "#10b981"
    },
    update: {
      icon: "✏️",
      defaultMessage: "Đang cập nhật thông tin...",
      color: "#f59e0b"
    },
    delete: {
      icon: "🗑️",
      defaultMessage: "Đang xóa sự kiện...",
      color: "#ef4444"
    },
    default: {
      icon: "🔄",
      defaultMessage: "Đang xử lý...",
      color: "#6b7280"
    }
  };

  const { icon, defaultMessage, color } = config[type] || config.default;
  const displayMessage = message || defaultMessage;

  return (
    <div className={styles.overlay}>
      <div className={styles.card} style={{ borderTopColor: color }}>
        <div className={styles.icon}>{icon}</div>
        <div className={styles.message}>{displayMessage}</div>
        <div className={styles.spinner} style={{ borderTopColor: color }}></div>
      </div>
    </div>
  );
};

export default LoadingOverlay;
