# backend/log_config.py
"""Cấu hình logging tập trung + cầu nối cho các lệnh print() cũ.

Mục tiêu: giảm chi phí I/O do log dày đặc ở production mà KHÔNG phải sửa
toàn bộ call-site print() (giữ nguyên hành vi, tránh rủi ro).

Cách dùng ở production:
    - Đặt biến môi trường LOG_LEVEL=WARNING  → chỉ in cảnh báo/lỗi (giảm I/O tối đa).
    - Mặc định INFO  → các print() thông tin (mức DEBUG) sẽ bị ẩn, chỉ giữ WARNING/ERROR.
    - LOG_LEVEL=DEBUG  → hiện đầy đủ trace như print() trước đây (dùng khi debug).
"""
import logging
import os

_CONFIGURED = False


def setup_logging():
    """Cấu hình root logger một lần duy nhất (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _CONFIGURED = True


def make_print(name):
    """Trả về hàm thay thế print() cho một module.

    Suy ra severity từ tiền tố emoji quen thuộc trong codebase để log đúng mức:
      ❌ / ‼️ / 🔥  → error
      ⚠️            → warning
      còn lại       → debug (bị ẩn ở mức INFO/WARNING, không tốn I/O ở production)
    """
    setup_logging()
    logger = logging.getLogger(name)

    def _print(*args, sep=" ", **_ignored):
        msg = sep.join(str(a) for a in args)
        stripped = msg.lstrip()
        if stripped.startswith(("❌", "‼️", "🔥")):
            logger.error(msg)
        elif stripped.startswith("⚠️"):
            logger.warning(msg)
        else:
            logger.debug(msg)

    return _print
