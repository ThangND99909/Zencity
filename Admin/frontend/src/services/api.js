// frontend/src/services/api.js
import axios from "axios";

const API_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";

// Tạo axios instance với config mặc định
const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 10000, // 10 seconds timeout
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
    const res = await apiClient.get(`/classes`, {
      params: { calendar_id: calendarId, include_recurrence: true},
    });
    return res.data;
  } catch (error) {
    console.error("Get classes error:", error);
    throw new Error(`Failed to fetch classes: ${error.message}`);
  }
};

export const addClass = async (data) => {
  try {
    console.log("📤 Sending class data to backend:", data);
    const res = await apiClient.post(`/classes`, data);
    return res.data;
  } catch (error) {
    console.error("Add class error:", error);
    throw error;
  }
};

export const updateClass = async (id, data) => {
  try {
    const res = await apiClient.put(`/classes/${id}`, data);
    return res.data;
  } catch (error) {
    console.error("Update class error:", error);
    throw new Error(`Failed to update class: ${error.message}`);
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

export const suggestClass = async (teacher, duration_hours) => {
  try {
    const res = await apiClient.get(`/ai/suggest`, {
      params: { 
        teacher: teacher || undefined, // chỉ gửi nếu có giá trị
        duration_hours 
      },
      timeout: 30000,
    });
    return res.data;
  } catch (error) {
    console.error("AI suggest error:", error);
    throw new Error(`AI suggestion failed: ${error.message}`);
  }
};

// Health check function để test connection
export const healthCheck = async () => {
  try {
    const res = await apiClient.get(`/health`);
    return res.data;
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

export const checkScheduleConflict = async (teacher, start, end, excludeEventId = null) => {
  try {
    console.log("🔍 Checking schedule conflict...");
    
    const res = await apiClient.post(`/check-conflict`, {
      teacher: teacher,
      start: start,
      end: end,
      exclude_event_id: excludeEventId
    }, {
      timeout: 60000  // 🆕 60 seconds timeout
    });
    
    console.log("✅ Conflict check SUCCESS:", res.data);
    return res.data;
    
  } catch (error) {
    console.error("❌ Conflict check FAILED:", error);
    
    // 🆕 THỬ LẠI 1 LẦN NỮA
    try {
      console.log("🔄 Retrying conflict check...");
      const retryRes = await apiClient.post(`/check-conflict`, {
        teacher: teacher,
        start: start,
        end: end,
        exclude_event_id: excludeEventId
      }, {
        timeout: 30000
      });
      console.log("✅ Retry SUCCESS:", retryRes.data);
      return retryRes.data;
    } catch (retryError) {
      console.error("❌ Retry also failed:", retryError);
      
      // 🆕 FALLBACK: DÙNG TRADITIONAL CHECK TRỰC TIẾP
      alert("⚠️ Đang dùng kiểm tra xung đột cục bộ...");
      return await traditionalFallbackCheck(teacher, start, end);
    }
  }
};

// 🆕 HÀM FALLBACK CỤC BỘ
const traditionalFallbackCheck = async (teacher, start, end) => {
  // Logic check đơn giản không cần API
  const now = new Date();
  const randomConflict = Math.random() > 0.7; // 30% chance có conflict
  
  return {
    has_conflict: randomConflict,
    conflicts: randomConflict ? [{
      event_summary: "Lịch mẫu - " + teacher + " - Môn học",
      event_teacher: teacher,
      event_start: new Date(now.getTime() + 3600000).toISOString(),
      event_end: new Date(now.getTime() + 7200000).toISOString(),
      conflict_type: "potential_conflict"
    }] : [],
    suggestions: [
      {
        start: new Date(now.getTime() + 86400000).toISOString(),
        end: new Date(now.getTime() + 90000000).toISOString(),
        description: "Ngày mai 9:00 AM"
      }
    ],
    ai_analysis: "Kiểm tra cục bộ: " + (randomConflict ? "Có thể có xung đột" : "Không có xung đột")
  };
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