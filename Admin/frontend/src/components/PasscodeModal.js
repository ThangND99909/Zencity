import { useState, useEffect } from "react";
import styles from "./PasscodeModal.module.css";

export default function PasscodeModal({ isOpen, onSubmit }) {
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    // Reset khi modal mở
    if (isOpen) {
      setPasscode("");
      setError("");
    }
  }, [isOpen]);

  const handleInputChange = (e) => {
    const value = e.target.value.replace(/[^0-9]/g, ""); // Chỉ cho phép số
    setPasscode(value);
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

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !isLoading) {
      handleSubmit(e);
    }
  };

  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent}>
        <h2>Nhập Passcode</h2>
        <p>Vui lòng nhập passcode để truy cập Lịch Admin</p>
        
      <form onSubmit={handleSubmit} className={styles.form}>
          <input
            type="password"
            placeholder="🔐 Nhập mã bảo vệ (4-6 số)"
            value={passcode}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            maxLength="6"
            disabled={isLoading}
            autoFocus
            className={error ? styles.inputError : ""}
          />
          
          {error && <div className={styles.errorMessage}>{error}</div>}
          
          <button 
            type="submit" 
            disabled={isLoading || passcode.length === 0}
            className={styles.submitButton}
          >
            {isLoading ? "Đang kiểm tra..." : "Xác nhận"}
          </button>
        </form>
      </div>
    </div>
  );
}
