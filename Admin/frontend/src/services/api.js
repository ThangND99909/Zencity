// frontend/src/services/api.js
import axios from "axios";

// 🕐 Helper retry khi backend Render đang "ngủ"
const safeFetch = async (fn, retries = 3, delay = 5000) => {
  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (error) {
      // Nếu là lỗi kết nối (Render sleep)
      if (error.message.includes("Cannot connect to server") || error.code === "ECONNABORTED") {
        console.warn(`⚙️ Backend đang khởi động... thử lại sau ${delay / 1000}s (${i + 1}/${retries})`);
        if (i < retries - 1) {
          await new Promise(res => setTimeout(res, delay));
          continue;
        }
      }
      throw error;
    }
  }
};
//const API_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
const API_URL = process.env.REACT_APP_BACKEND_URL || "https://zencity-backend.onrender.com";

// Tạo axios instance với config mặc định
const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 90000, // 90 seconds timeout
  headers: {
    'Content-Type': 'application/json',
  }
});

// Request interceptor để log requests
apiClient.interceptors.request.use(
  (config) => {
    console.log(`🚀 ${config.method?.toUpperCase()} ${config.url}`, config.data || config.params);
    return config;
  },
  (error) => {
    console.error('❌ Request error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor để xử lý errors
apiClient.interceptors.response.use(
  (response) => {
    console.log(`✅ ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error('❌ Response error:', error.response?.data || error.message);
    
    // Xử lý các loại error phổ biến
    if (error.response) {
      // Server trả về error status (4xx, 5xx)
      const serverError = error.response.data;
      error.message = serverError.detail || serverError.message || `Server error: ${error.response.status}`;
    } else if (error.request) {
      // Request được gửi nhưng không nhận được response
      error.message = "Cannot connect to server. Please check your connection.";
    } else {
      // Something happened in setting up the request
      error.message = error.message || "Unknown error occurred";
    }
    
    return Promise.reject(error);
  }
);

export const getClasses = async (calendarId = "primary") => {
  try {
    return await safeFetch(async () => {
    const res = await apiClient.get(`/classes`, {
      params: { calendar_id: calendarId, include_recurrence: true},
    });
    return res.data;
    });
  } catch (error) {
    console.error("Get classes error:", error);
    throw new Error(`Failed to fetch classes: ${error.message}`);
  }
};

export const addClass = async (data) => {
  try {
    return await safeFetch(async () => {
    console.log("📤 Sending class data to backend:", data);
    const res = await apiClient.post(`/classes`, data);
    return res.data;
    });
  } catch (error) {
    console.error("Add class error:", error);
    throw error;
  }
};

export const updateClass = async (id, data) => {
  try {
    
    // QUAN TRỌNG: Lấy edit_mode từ ĐÚNG nơi
    const editMode = data.edit_mode || data.editMode || 'this';
    
    const importantKeys = ['_is_editing_from_instance','_remaining_count', '_instance_index', 'master_event_id'];
    importantKeys.forEach(key => {
      if (data[key] !== undefined) {
        console.log(`   - ${key}: ${data[key]}`);
      }
    });
    // Tạo query params
    const params = new URLSearchParams();
    params.append('edit_mode', editMode);
    if (data._is_editing_from_instance !== undefined) {
      params.append('_is_editing_from_instance', data._is_editing_from_instance);
    }
    
    
    const url = `/classes/${id}${params.toString() ? '?' + params.toString() : ''}`;
    console.log("🔗 Final URL:", url);
    
    // Gửi request
    console.log("🚀 Sending PUT request...");
    const res = await apiClient.put(url, data);
    
    console.log("✅ Update successful");
    return res.data;
    
  } catch (error) {
    console.error("❌ Update error:", error);
    throw error;
  }
};

export const deleteClass = async (id, deleteMode = 'this') => {
  try {
    console.log("📤 API DELETE REQUEST:", {
      id,
      deleteMode,
      url: `/classes/${id}`,
      params: { delete_mode: deleteMode }
    });
    
    // Gửi deleteMode trong query params
    const response = await apiClient.delete(`/classes/${id}`, {
      params: { 
        delete_mode: deleteMode 
      }
    });
    
    console.log(`✅ Delete successful:`, response.data);
    return response.data;
    
  } catch (error) {
    console.error("Delete class error:", error);
    
    // Detailed error message
    const errorMessage = error.response?.data?.detail || 
                        error.response?.data?.message || 
                        error.message || 
                        "Failed to delete class";
    
    throw new Error(errorMessage);
  }
};

// 🆕 HÀM ĐƠN GIẢN CHO CHECK CONFLICT (KHÔNG AI)
export const checkScheduleConflict = async (teacher, start, end, excludeEventId = null) => {
  try {
    console.log("🔍 Checking schedule conflict (non-AI)...");
    
    const res = await apiClient.post(`/check-conflict`, {
      teacher: teacher,
      start: start,
      end: end,
      exclude_event_id: excludeEventId
    }, {
      timeout: 10000  // Giảm timeout vì không dùng AI
    });
    
    console.log("✅ Conflict check result:", res.data);
    return res.data;
    
  } catch (error) {
    console.error("❌ Conflict check failed:", error);
    
    // Fallback đơn giản (KHÔNG AI)
    return {
      has_conflict: false,
      conflicts: [],
      message: "Không thể kiểm tra xung đột, vui lòng kiểm tra thủ công",
      error: error.message
    };
  }
};

// Health check function để test connection
export const healthCheck = async () => {
  try {
    return await safeFetch(async () => {
    const res = await apiClient.get(`/health`);
    return res.data;
    });
  } catch (error) {
    console.error("Health check error:", error);
    throw new Error(`Backend connection failed: ${error.message}`);
  }
};

export const getEvent = async (eventId, calendarId = "primary") => {
  try {
    const res = await apiClient.get(`/classes/${eventId}`, {  // ✅ DÙNG /classes/ thay vì /events/
      params: { calendar_id: calendarId }
    });
    return res.data;
  } catch (error) {
    console.error("Get event error:", error);
    throw new Error(`Failed to fetch event: ${error.message}`);
  }
};

// 🆕 HÀM SUGGEST SIMPLE (KHÔNG AI) - nếu bạn cần giữ tính năng này
export const suggestClass = async (teacher, duration_hours) => {
  try {
    // Simple fallback: đề xuất ngày mai 9:00 AM
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    
    const endTime = new Date(tomorrow);
    endTime.setHours(tomorrow.getHours() + duration_hours);
    
    return {
      start: tomorrow.toISOString(),
      end: endTime.toISOString(),
      note: "Manual scheduling (AI disabled)"
    };
  } catch (error) {
    console.error("Suggest class error:", error);
    throw new Error(`Scheduling failed: ${error.message}`);
  }
};

export const getTimezones = async () => {
  try {
    console.log("🕐 Fetching timezones from backend...");
    const res = await apiClient.get(`/timezones`);
    console.log("✅ Timezones fetched successfully");
    return res.data;
  } catch (error) {
    console.error("❌ Error fetching timezones, using fallback:", error);
    // Fallback to hardcoded timezones
    return {
      timezones: [
        { value: "Asia/Ho_Chi_Minh", label: "🇻🇳 Giờ Việt Nam (UTC+7)" },
        { value: "America/Chicago", label: "🇺🇸 Giờ miền Trung - Chicago (UTC-6/-5)" },
        { value: "America/New_York", label: "🇺🇸 Giờ miền Đông - New York (UTC-5/-4)" },
        { value: "America/Los_Angeles", label: "🇺🇸 Giờ miền Tây - Los Angeles (UTC-8/-7)" },
        { value: "Europe/London", label: "🇬🇧 Giờ London (UTC+0/+1)" },
        { value: "Europe/Paris", label: "🇫🇷 Giờ Paris (UTC+1/+2)" },
        { value: "Asia/Tokyo", label: "🇯🇵 Giờ Tokyo (UTC+9)" },
        { value: "Australia/Sydney", label: "🇦🇺 Giờ Sydney (UTC+10/+11)" },
      ]
    };
  }
};

// ============================================================
// ================= PROGRAM MANAGEMENT API ===================
// ============================================================

export const getPrograms = async () => {
  try {
    console.log("📚 Fetching programs from backend...");
    const res = await apiClient.get(`/programs`);
    console.log("✅ Programs fetched successfully:", res.data.data);
    return res.data.data || [];
  } catch (error) {
    console.error("❌ Error fetching programs:", error);
    throw new Error(`Failed to fetch programs: ${error.message}`);
  }
};

export const createProgram = async (name) => {
  try {
    console.log("➕ Creating program:", name);
    const res = await apiClient.post(`/programs`, { name });
    console.log("✅ Program created:", res.data.data);
    return res.data.data;
  } catch (error) {
    console.error("❌ Error creating program:", error);
    throw new Error(error.response?.data?.detail || `Failed to create program: ${error.message}`);
  }
};

export const updateProgram = async (programId, name) => {
  try {
    console.log("✏️ Updating program:", programId, name);
    const res = await apiClient.put(`/programs/${programId}`, { name });
    console.log("✅ Program updated:", res.data.data);
    return res.data.data;
  } catch (error) {
    console.error("❌ Error updating program:", error);
    throw new Error(error.response?.data?.detail || `Failed to update program: ${error.message}`);
  }
};

export const deleteProgram = async (programId) => {
  try {
    console.log("🗑️ Deleting program:", programId);
    const res = await apiClient.delete(`/programs/${programId}`);
    console.log("✅ Program deleted");
    return res.data;
  } catch (error) {
    console.error("❌ Error deleting program:", error);
    throw new Error(error.response?.data?.detail || `Failed to delete program: ${error.message}`);
  }
};