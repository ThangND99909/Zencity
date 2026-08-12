// frontend/src/pages/AdminSchedule.js
import { useEffect, useState, useRef } from "react";
import { getClasses, addClass, updateClass, deleteClass } from "../services/api";
import ClassTable from "../components/ClassTable";
import CalendarView from "../components/CalendarView";
import styles from "./AdminSchedule.module.css";
import LoadingOverlay from '../components/LoadingOverlay';
import PasscodeModal from "../components/PasscodeModal";

const CORRECT_PASSCODE = "1234"; // 🔐 Thay đổi passcode của bạn tại đây

export default function AdminSchedule() {
  const [classes, setClasses] = useState([]);
  const [showCalendar, setShowCalendar] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingType, setLoadingType] = useState('default');
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [calendarFilter] = useState('both'); // 'odd', 'even', 'both'
  const [isPasscodeVerified, setIsPasscodeVerified] = useState(false);
  const [showPasscodeModal, setShowPasscodeModal] = useState(true);

  // ✅ THÊM REF CHO CALENDAR VIEW
  const calendarViewRef = useRef(null);
  const createInFlightRef = useRef(false);

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
    // Giả lập delay để tạo cảm giác như đang kiểm tra
    await new Promise(resolve => setTimeout(resolve, 500));
    
    if (inputPasscode === CORRECT_PASSCODE) {
      setIsPasscodeVerified(true);
      setShowPasscodeModal(false);
      return { success: true, message: "Passcode chính xác" };
    } else {
      return { success: false, message: "Passcode không chính xác" };
    }
  };

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
    if (type === "error") {
      setError(message);
      setSuccess(null);
    } else {
      setSuccess(message);
      setError(null);
    }
    setTimeout(() => {
      setError(null);
      setSuccess(null);
    }, 5000);
  };

  

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
        showMessage("Class added successfully! 🎉", "success");
      }, 400);
      return createResponse;
    } catch (err) {
      showMessage("Failed to add class: " + err.message);
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
    try {
      showLoading('delete');
      console.log("🔥 HANDLE DELETE CALLED - FULL DATA:", eventData);
      
      // **FIX: Xử lý cả string và object**
      let eventId;
      let deleteMode = 'this';
      let alreadyConfirmed = false;
      
      if (typeof eventData === 'string') {
        // Trường hợp cũ: chỉ có ID
        eventId = eventData;
        console.log("⚠️ Legacy string format, using default deleteMode: 'this'");
      } else if (typeof eventData === 'object') {
        // Trường hợp mới: có object với deleteMode
        eventId = eventData.id;
        deleteMode = eventData.deleteMode || 'this';
        alreadyConfirmed = eventData._confirmed === true;
        
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
      
      // Xác nhận với người dùng dựa trên mode
      let confirmationMessage = "";
      
      switch(deleteMode) {
        case 'all':
          confirmationMessage = "Bạn có chắc muốn xóa TOÀN BỘ chuỗi sự kiện lặp lại?";
          break;
        case 'following':
          confirmationMessage = "Bạn có chắc muốn xóa sự kiện này VÀ TẤT CẢ sự kiện sau nó trong chuỗi?";
          break;
        default:
          confirmationMessage = "Bạn có chắc chắn muốn xóa sự kiện này?";
      }
      
      if (!alreadyConfirmed && !window.confirm(confirmationMessage)) {
        return;
      }
      
      // Gọi API xóa với mode tương ứng
      const result = await deleteClass(eventId, deleteMode);
      
      console.log("🗑️ Delete result:", result);

      // ⚡ Làm mới ở nền, không chặn UI chờ tải lại (mục 1)
      refreshClassesInBackground(calendarFilter);

      // Hiển thị thông báo thành công
      showMessage("✅ Đã xóa sự kiện thành công!", "success");
      
    } catch (err) {
      console.error("❌ Delete error:", err);
      showMessage("Failed to delete class: " + err.message);
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
        showMessage("Classes refreshed successfully!", "success");
      }, 100); // Delay 100ms
      
    } catch (err) {
      showMessage("Refresh failed: " + err.message, "error");
    }
  };

  return (
    <div className={styles.container}>
      {/* 🔐 Passcode Modal */}
      <PasscodeModal 
        isOpen={showPasscodeModal} 
        onSubmit={handlePasscodeSubmit}
      />

      {/* Ẩn toàn bộ giao diện khi chưa xác thực passcode */}
      {!isPasscodeVerified ? (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: '#f5f5f5',
          zIndex: 998,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center'
        }}>
          <div style={{ textAlign: 'center', color: '#999' }}>
            <h2>Vui lòng nhập passcode để tiếp tục</h2>
          </div>
        </div>
      ) : (
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
            <h1 className={styles.mainTitle}>Admin Schedule Management</h1>
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
            {showCalendar ? "Hide Calendar" : "Show Calendar"}
          </button>

          <button className={`${styles.btn} ${styles.btnRefresh}`} onClick={handleRefresh}>
            <span className={`${styles.buttonIcon} ${styles.refreshIcon}`} aria-hidden="true">↻</span>
            Refresh
          </button>
        </div>
      </header>

      {success && (
        <div className={`${styles.elegantNotify} ${styles.elegantSuccess}`}>
          <div className={styles.elegantIcon}>✓</div>
          <div className={styles.elegantText}>{success}</div>
          <div className={styles.elegantSubtext}>Đã hoàn thành</div>
          <button className={styles.elegantClose} onClick={() => setSuccess(null)}>
            ×
          </button>
        </div>
      )}

      {error && (
        <div className={`${styles.elegantNotify} ${styles.elegantError}`}>
          <div className={styles.elegantIcon}>⚠</div>
          <div className={styles.elegantText}>{error}</div>
          <div className={styles.elegantSubtext}>Vui lòng kiểm tra lại</div>
          <button className={styles.elegantClose} onClick={() => setError(null)}>
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
                <div className={styles.emptyBox}>No classes found. Create your first class!</div>
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
