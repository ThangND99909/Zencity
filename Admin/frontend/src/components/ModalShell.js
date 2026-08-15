import { useEffect, useId, useRef } from "react";
import styles from "./ModalShell.module.css";

const modalStack = [];

const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "a[href]",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export default function ModalShell({
  children,
  title,
  description,
  onClose,
  panelClassName = "",
  closeOnBackdrop = false,
  initialFocusRef,
}) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const modalId = Symbol("modal");
    modalStack.push(modalId);
    const previousFocus = document.activeElement;
    const panel = panelRef.current;
    const focusTarget = initialFocusRef?.current || panel?.querySelector(FOCUSABLE_SELECTOR) || panel;
    focusTarget?.focus({ preventScroll: true });

    const handleKeyDown = (event) => {
      if (modalStack[modalStack.length - 1] !== modalId) return;
      if (event.key === "Escape" && onCloseRef.current) {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const focusable = [...panel.querySelectorAll(FOCUSABLE_SELECTOR)];
      if (focusable.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      const stackIndex = modalStack.indexOf(modalId);
      if (stackIndex >= 0) modalStack.splice(stackIndex, 1);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus?.({ preventScroll: true });
    };
  }, [initialFocusRef]);

  return (
    <div
      className={styles.overlay}
      data-modal="true"
      onMouseDown={(event) => {
        if (closeOnBackdrop && event.target === event.currentTarget) onClose?.();
      }}
    >
      <div
        ref={panelRef}
        className={`${styles.panel} ${panelClassName}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <span id={titleId} className={styles.srOnly}>{title}</span>
        {description && <span id={descriptionId} className={styles.srOnly}>{description}</span>}
        {children}
      </div>
    </div>
  );
}
