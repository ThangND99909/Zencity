import { useState, useEffect, useRef } from "react";
import styles from "./PasscodeModal.module.css";
import ModalShell from "./ModalShell";

export default function PasscodeModal({ isOpen, onSubmit }) {
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    // Reset khi modal mở
    if (isOpen) {
      setPasscode("");
      setError("");
    }
  }, [isOpen]);

  const handleInputChange = (e) => {
    setPasscode(e.target.value);
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (passcode.length === 0) {
      setError("Vui lòng nhập passcode");
      return;
    }

    setIsLoading(true);
    try {
      const result = await onSubmit(passcode);
      if (!result.success) {
        setError(result.message || "Passcode không chính xác");
        setPasscode("");
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <ModalShell
      title="Đăng nhập quản trị"
      description="Nhập passcode để truy cập lịch quản trị"
      panelClassName={styles.modalContent}
      initialFocusRef={inputRef}
    >
        <h2>Nhập Passcode</h2>
        <p>Vui lòng nhập passcode để truy cập Lịch Admin</p>
        
      <form onSubmit={handleSubmit} className={styles.form}>
          <input
            type="text"
            name="username"
            value="admin"
            readOnly
            tabIndex={-1}
            autoComplete="username"
            className={styles.srOnly}
            aria-hidden="true"
          />
          <input
            ref={inputRef}
            type="password"
            aria-label="Passcode quản trị"
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "passcode-error" : undefined}
            autoComplete="current-password"
            placeholder="🔐 Nhập mã truy cập"
            value={passcode}
            onChange={handleInputChange}
            maxLength="64"
            disabled={isLoading}
            autoFocus
            className={error ? styles.inputError : ""}
          />
          
          {error && <div id="passcode-error" role="alert" className={styles.errorMessage}>{error}</div>}
          
          <button 
            type="submit" 
            disabled={isLoading || passcode.length === 0}
            className={styles.submitButton}
          >
            {isLoading ? "Đang kiểm tra..." : "Xác nhận"}
          </button>
        </form>
    </ModalShell>
  );
}
