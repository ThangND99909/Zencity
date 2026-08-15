import ModalShell from "./ModalShell";
import styles from "./ConfirmationDialog.module.css";

export default function ConfirmationDialog({
  isOpen,
  title,
  message,
  confirmLabel = "Xác nhận",
  cancelLabel = "Hủy",
  tone = "default",
  busy = false,
  onConfirm,
  onCancel,
}) {
  if (!isOpen) return null;
  return (
    <ModalShell title={title} onClose={busy ? undefined : onCancel} panelClassName={styles.dialog}>
      <h2>{title}</h2>
      <div className={styles.message}>{message}</div>
      <div className={styles.actions}>
        <button type="button" className={styles.cancel} onClick={onCancel} disabled={busy}>{cancelLabel}</button>
        <button
          type="button"
          className={tone === "danger" ? styles.danger : styles.confirm}
          onClick={onConfirm}
          disabled={busy}
        >
          {busy ? "Đang xử lý..." : confirmLabel}
        </button>
      </div>
    </ModalShell>
  );
}
