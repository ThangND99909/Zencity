// frontend/src/pages/AdminSchedule.js
import { useEffect, useState, useRef } from "react";
import {
  getClasses,
  addClass,
  updateClass,
  deleteClass,
  verifyPasscode,
  verifySession,
  getAuthToken,
  clearAuthToken,
} from "../services/api";
import ClassTable from "../components/ClassTable";
import CalendarView from "../components/CalendarView";
import styles from "./AdminSchedule.module.css";
import LoadingOverlay from '../components/LoadingOverlay';
import PasscodeModal from "../components/PasscodeModal";
import ConfirmationDialog from "../components/ConfirmationDialog";

export default function AdminSchedule() {
  const [classes, setClasses] = useState([]);
  const [showCalendar, setShowCalendar] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingType, setLoadingType] = useState('default');
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [calendarFilter] = useState('both'); // 'odd', 'even', 'both'
  const [isPasscodeVerified, setIsPasscodeVerified] = useState(() => Boolean(getAuthToken()));
  const [showPasscodeModal, setShowPasscodeModal] = useState(() => !getAuthToken());
  const [pendingDelete, setPendingDelete] = useState(null);

  // ✅ THÊM REF CHO CALENDAR VIEW
  const calendarViewRef = useRef(null);
  const createInFlightRef = useRef(false);
  const messageTimerRef = useRef(null);

  // Hàm show loading
  const showLoading = (type = 'default', customMessage = '') => {
    setLoadingType(type);
    if (customMessage) {
      setLoadingMessage(customMessage);
    }
    setLoading(true);
  };

  const hideLoading = () => {
    setLoading(false);
    setLoadingMessage('');
  };

  // 🔐 Xử lý xác thực passcode
  const handlePasscodeSubmit = async (inputPasscode) => {
    try {
      await verifyPasscode(inputPasscode);
      setIsPasscodeVerified(true);
      setShowPasscodeModal(false);
      return { success: true, message: "Passcode chính xác" };
    } catch (authError) {
      return { success: false, message: authError.message || "Không thể đăng nhập" };
    }
  };

  const handleLogout = () => {
    clearAuthToken();
    setClasses([]);
    setIsPasscodeVerified(false);
    setShowPasscodeModal(true);
  };

  useEffect(() => {
    const requireAuth = () => {
      setIsPasscodeVerified(false);
      setShowPasscodeModal(true);
    };
    window.addEventListener("zencity:auth-required", requireAuth);
    return () => window.removeEventListener("zencity:auth-required", requireAuth);
  }, []);

  useEffect(() => {
    if (!getAuthToken()) return;
    verifySession().then((valid) => {
      if (!valid) {
        setIsPasscodeVerified(false);
        setShowPasscodeModal(true);
      }
    });
  }, []);

  // ⚡ Cache key cho localStorage
  const getCacheKey = (filter) => `zencity_classes_${filter}`;
  const CACHE_TTL_MS = 60 * 1000; // 60 giây — khớp với backend

  // 🧹 Xóa cache localStorage của 1 filter — gọi sau khi ghi để không hiển thị dữ liệu cũ
  const invalidateLocalCache = (filter = calendarFilter) => {
    try {
      localStorage.removeItem(getCacheKey(filter));
    } catch (_) {}
  };

  /**
   * Tải danh sách lớp.
   * @param {string} filter  odd | even | both
   * @param {object} options
   *   - force: bỏ qua cache localStorage, luôn fetch dữ liệu mới (dùng sau khi ghi / bấm Refresh)
   *   - background: không hiện loading overlay và không set error (làm mới im lặng ở nền)
   */
  const loadClasses = async (filter = calendarFilter, { force = false, background = false } = {}) => {
    try {
      if (!background) setError(null);

      // ⚡ Hiển thị cache ngay lập tức nếu còn hợp lệ (bỏ qua khi force)
      if (!force) {
        const cacheKey = getCacheKey(filter);
        try {
          const cached = JSON.parse(localStorage.getItem(cacheKey) || 'null');
          if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
            setClasses(cached.data);
            // Vẫn fetch mới ở nền nhưng không show loading
            getClasses(filter).then(fresh => {
              setClasses(fresh);
              localStorage.setItem(cacheKey, JSON.stringify({ data: fresh, ts: Date.now() }));
            }).catch(() => {}); // lỗi nền thì bỏ qua
            return;
          }
        } catch (_) {}
      }

      // Không có cache hợp lệ (hoặc force) → fetch
      if (!background) showLoading('classes');
      const data = await getClasses(filter);
      setClasses(data);
      try {
        localStorage.setItem(getCacheKey(filter), JSON.stringify({ data, ts: Date.now() }));
      } catch (_) {}
    } catch (err) {
      // Ở chế độ nền: ghi đã thành công, chỉ log lỗi làm mới, không làm phiền người dùng
      if (!background) setError("Failed to load classes: " + err.message);
      console.error("Load classes error:", err);
    } finally {
      if (!background) hideLoading();
    }
  };

  // 🔄 Làm mới danh sách ở nền sau khi ghi: không hiện overlay, luôn lấy dữ liệu mới
  const refreshClassesInBackground = (filter = calendarFilter) => {
    invalidateLocalCache(filter);
    loadClasses(filter, { force: true, background: true });
  };

  // 🔐 Chỉ load data khi đã xác thực passcode
  useEffect(() => {
    if (isPasscodeVerified) {
      loadClasses();
    }
  }, [isPasscodeVerified]);

  const showMessage = (message, type = "error") => {
    if (messageTimerRef.current) clearTimeout(messageTimerRef.current);
    if (type === "error") {
      setError(message);
      setSuccess(null);
    } else {
      setSuccess(message);
      setError(null);
    }
    messageTimerRef.current = setTimeout(() => {
      setError(null);
      setSuccess(null);
    }, 5000);
  };

  useEffect(() => () => {
    if (messageTimerRef.current) clearTimeout(messageTimerRef.current);
  }, []);

  

  const handleAdd = async (data) => {
    if (createInFlightRef.current) {
      throw new Error("A class creation request is already in progress");
    }

    createInFlightRef.current = true;
    try {
      showLoading('add');
      const createResponse = await addClass({
        name: data.name,
        classname: data.classname || "",
        teacher: data.teacher || "",
        zoom_link: data.zoom_link || "",
        program: data.program || "",
        start: data.start,
        end: data.end,
        meeting_id: data.meeting_id || "",
        passcode: data.passcode || "",
        recurrence: data.recurrence || "",
        repeat_count: data.repeat_count || 1,
        byday: data.byday || [],
        bymonthday: data.bymonthday || [],
        bymonth: data.bymonth || [],
        timezone: data.timezone || "Asia/Ho_Chi_Minh"
      });
      // ⚡ Không chặn UI để chờ tải lại: ẩn overlay ngay sau khi ghi xong,
      //    danh sách được làm mới ở nền (mục 1 tối ưu hiệu năng cảm nhận).
      refreshClassesInBackground(calendarFilter);

      // ✅ SHOW CALENDAR TỚI TRƯỚC ĐỂ ĐỢI RENDER
      if (!showCalendar) {
        setShowCalendar(true);
      }
      
      // ✅ SAU ĐÓ GỌI SCROLL (ĐỢI STATE UPDATE VÀ CALENDAR REFRESH)
      setTimeout(() => {
        if (calendarViewRef.current && createResponse) {
          console.log("📞 Calling scrollToEvent from handleAdd");
          // ✅ PROPERLY EXTRACT START TIME FROM API RESPONSE
          let eventStartTime = null;
          
          // Handle Google Calendar format {dateTime: "...", date: "..."}
          if (createResponse.start && typeof createResponse.start === 'object') {
            eventStartTime = createResponse.start.dateTime || createResponse.start.date;
          } else if (createResponse.start && typeof createResponse.start === 'string') {
            eventStartTime = createResponse.start;
          } else if (data.start) {
            // Fallback to original data
            eventStartTime = data.start;
          }
          
          console.log("📍 Using event start time for scroll:", eventStartTime);
          if (eventStartTime) {
            calendarViewRef.current.scrollToEvent(eventStartTime);
          } else {
            console.warn("⚠️ Could not extract event start time from response");
          }
        }
      }, 300); // Increased delay to ensure loadClasses completes
      
      setTimeout(() => {
        showMessage("Đã thêm lớp học thành công!", "success");
      }, 400);
      return createResponse;
    } catch (err) {
      showMessage("Không thể thêm lớp học: " + err.message);
      throw err;
    } finally {
      createInFlightRef.current = false;
      hideLoading();
    }
  };

  // frontend/src/pages/AdminSchedule.js

  const handleUpdate = async (data) => {
    try {
      showLoading('update');
      const id = data.id;
      const editMode = data.edit_mode || data.editMode || 'this';
      
      
      Object.keys(data).forEach(key => {
        if (key.startsWith('_') || key.includes('mode') || key.includes('instance')) {
          console.log(`   - ${key}: ${JSON.stringify(data[key])}`);
        }
      });

      // GOOGLE CALENDAR: If 'all' mode on instance, use master ID
      const targetId = id;
      
      
      // ĐẢM BẢO EDIT_MODE ĐƯỢC TRUYỀN ĐÚNG
      const updateData = {
        ...data,
        edit_mode: editMode  // CRITICAL! Đảm bảo tên đúng
      };
      
      

      // Call API with edit_mode
      await updateClass(targetId, updateData);

      // ⚡ Làm mới ở nền, không chặn UI chờ tải lại (mục 1)
      refreshClassesInBackground(calendarFilter);

      // Success message theo mode
      let message = "Cập nhật thành công!";
      if (editMode === 'following') {
        message = "Đã cập nhật sự kiện này và các sự kiện tiếp theo!";
      }
      
      showMessage(message, "success");
      
    } catch (err) {
      console.error("❌ Update error details:", {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status
      });
      showMessage("Lỗi cập nhật: " + err.message);
    } finally {
      hideLoading();
    }
  };

  const handleDelete = async (eventData) => {
    const requestedMode = typeof eventData === "object" ? (eventData.deleteMode || "this") : "this";
    const alreadyConfirmed = typeof eventData === "object" && eventData._confirmed === true;
    if (!alreadyConfirmed) {
      const messages = {
        all: "Bạn có chắc muốn xóa toàn bộ chuỗi sự kiện lặp lại?",
        following: "Bạn có chắc muốn xóa sự kiện này và tất cả sự kiện tiếp theo trong chuỗi?",
        this: "Bạn có chắc muốn xóa sự kiện này?",
      };
      setPendingDelete({ eventData, message: messages[requestedMode] || messages.this });
      return;
    }
    try {
      showLoading('delete');
      // **FIX: Xử lý cả string và object**
      let eventId;
      let deleteMode = 'this';
      
      if (typeof eventData === 'string') {
        // Trường hợp cũ: chỉ có ID
        eventId = eventData;
        console.log("⚠️ Legacy string format, using default deleteMode: 'this'");
      } else if (typeof eventData === 'object') {
        // Trường hợp mới: có object với deleteMode
        eventId = eventData.id;
        deleteMode = eventData.deleteMode || 'this';
        
        console.log("✅ Object format detected:", {
          eventId,
          deleteMode,
          hasRecurrence: eventData.recurrence,
          hasRecurringEventId: eventData.recurringEventId
        });
      }
      
      if (!eventId) {
        showMessage("Cannot delete: Missing ID");
        return;
      }
      
      console.log("🎯 FINAL DELETE PARAMS:", { eventId, deleteMode });
      
      // Gọi API xóa với mode tương ứng
      const result = await deleteClass(eventId, deleteMode);
      
      console.log("🗑️ Delete result:", result);

      // ⚡ Làm mới ở nền, không chặn UI chờ tải lại (mục 1)
      refreshClassesInBackground(calendarFilter);

      // Hiển thị thông báo thành công
      showMessage("✅ Đã xóa sự kiện thành công!", "success");
      
    } catch (err) {
      console.error("❌ Delete error:", err);
      showMessage("Không thể xóa sự kiện: " + err.message);
    } finally {
      hideLoading();
    }
  };

  const handleRefresh = async () => {
    try {
      // Bấm Refresh → luôn lấy dữ liệu mới (bỏ qua cache localStorage cũ)
      invalidateLocalCache(calendarFilter);
      await loadClasses(calendarFilter, { force: true });

      // Delay một chút để loading ẩn đi rồi mới hiển thị thông báo
      setTimeout(() => {
        showMessage("Đã làm mới dữ liệu!", "success");
      }, 100); // Delay 100ms
      
    } catch (err) {
      showMessage("Không thể làm mới dữ liệu: " + err.message, "error");
    }
  };

  return (
    <div className={styles.container}>
      {/* 🔐 Passcode Modal */}
      <PasscodeModal 
        isOpen={showPasscodeModal} 
        onSubmit={handlePasscodeSubmit}
      />
      <ConfirmationDialog
        isOpen={Boolean(pendingDelete)}
        title="Xác nhận xóa sự kiện"
        message={pendingDelete?.message}
        confirmLabel="Xóa sự kiện"
        tone="danger"
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          const value = pendingDelete.eventData;
          setPendingDelete(null);
          handleDelete(typeof value === "object" ? { ...value, _confirmed: true } : { id: value, _confirmed: true });
        }}
      />

      {isPasscodeVerified && (
        <>
      <LoadingOverlay 
        isLoading={loading}
        type={loadingType}
        message={loadingMessage}
      />
      <header className={styles.headerWithLogo}>
        <div className={styles.headerBrand}>
          <div className={styles.logoShell}>
            <img src="/assets/logo.png" alt="Zen City Academy" className={styles.logo} />
          </div>
          <div className={styles.headerCopy}>
            <span className={styles.headerEyebrow}>Zen City Academy</span>
            <h1 className={styles.mainTitle}>Quản lý lịch học</h1>
            <p className={styles.headerSubtitle}>Quản lý chương trình và lịch học tập trung</p>
          </div>
        </div>

        <div className={styles.headerActions}>
          <button
            className={`${styles.btn} ${styles.btnToggleCalendar}`}
            onClick={() => {
              setShowCalendar(!showCalendar);
            }}
          >
            <span className={styles.buttonIcon} aria-hidden="true">▦</span>
            {showCalendar ? "Ẩn lịch" : "Hiện lịch"}
          </button>

          <button className={`${styles.btn} ${styles.btnRefresh}`} onClick={handleRefresh}>
            <span className={`${styles.buttonIcon} ${styles.refreshIcon}`} aria-hidden="true">↻</span>
            Làm mới
          </button>
          <button className={`${styles.btn} ${styles.btnLogout}`} onClick={handleLogout}>
            Đăng xuất
          </button>
        </div>
      </header>

      {success && (
        <div role="status" aria-live="polite" className={`${styles.elegantNotify} ${styles.elegantSuccess}`}>
          <div className={styles.elegantIcon}>✓</div>
          <div className={styles.elegantText}>{success}</div>
          <div className={styles.elegantSubtext}>Đã hoàn thành</div>
          <button aria-label="Đóng thông báo" className={styles.elegantClose} onClick={() => setSuccess(null)}>
            ×
          </button>
        </div>
      )}

      {error && (
        <div role="alert" aria-live="assertive" className={`${styles.elegantNotify} ${styles.elegantError}`}>
          <div className={styles.elegantIcon}>⚠</div>
          <div className={styles.elegantText}>{error}</div>
          <div className={styles.elegantSubtext}>Vui lòng kiểm tra lại</div>
          <button aria-label="Đóng thông báo" className={styles.elegantClose} onClick={() => setError(null)}>
            ×
          </button>
        </div>
      )}
      
      <div className={styles.mainContent}>
        {showCalendar ? (
          <div className={styles.calendarWrapper}>
            <CalendarView
              ref={calendarViewRef}
              events={classes}
              onCreateEvent={(event) => event.id ? handleUpdate(event) : handleAdd(event)}
              onDeleteEvent={handleDelete}
              calendarFilter={calendarFilter}
            />
          </div>
        ) : (
          <div className={styles.tableWrapper}>
            <div>
              {classes.length === 0 ? (
                <div className={styles.emptyBox}>Chưa có lớp học. Hãy tạo lớp đầu tiên!</div>
              ) : (
                <ClassTable 
                  classes={classes} 
                  onDelete={handleDelete} 
                  calendarFilter={calendarFilter}
                />
              )}
            </div>
          </div>
        )}
      </div>

        </>
      )}
    </div>
  );
}
