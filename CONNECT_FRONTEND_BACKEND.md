# 🔗 KẾT NỐI FRONTEND & BACKEND - HƯỚNG DẪN CHI TIẾT

## ✅ Bạn Đã Đạt Được:

```
✓ Backend: https://zencity-backend.onrender.com
✓ Frontend: https://c3514afb.zencity-smartcalendar.pages.dev
```

Bây giờ cần kết nối chúng lại. 3 bước:

---

## 🔧 Bước 1: Cập nhật CORS trên Backend

**Đã xong!** ✅ Vừa cập nhật file `app.py` để chấp nhận requests từ Cloudflare domain của bạn.

Commit & push:
```bash
cd Admin/backend
git add app.py
git commit -m "Update CORS for Cloudflare frontend"
git push
```

Render sẽ tự động redeploy.

---

## 🌐 Bước 2: Cập nhật Environment Variables trên Cloudflare

### **Cách 1: Qua Dashboard Cloudflare (Nhanh nhất)**

1. Vào: https://dash.cloudflare.com
2. Pages → zencity-smartcalendar
3. Settings → Environment variables
4. Click "Production" (hoặc "Add environment variables")
5. Thêm/Cập nhật:

```
Name:  REACT_APP_BACKEND_URL
Value: https://zencity-backend.onrender.com
```

6. Click "Save and Deploy"
7. Deploy will start automatically

### **Cách 2: Cập nhật Frontend Code (Nếu cần fallback)**

File: `Admin/frontend/src/services/api.js` - Đã sẵn config này:

```javascript
const API_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
```

Nó sẽ tự động lấy URL từ environment variable!

---

## 🧪 Bước 3: Test Kết Nối

### **Test 1: Browser Console**

1. Mở: https://c3514afb.zencity-smartcalendar.pages.dev
2. Nhấn F12 → Console tab
3. Chạy lệnh này:

```javascript
fetch('https://zencity-backend.onrender.com/api/events')
  .then(r => r.json())
  .then(d => console.log('✅ Backend connected!', d))
  .catch(e => console.error('❌ Error:', e))
```

Nếu thấy data hoặc 200 status → ✅ Kết nối thành công!

### **Test 2: Check Network Tab**

1. F12 → Network tab
2. Reload trang
3. Filter by "XHR" hoặc "Fetch"
4. Tìm request tới `/api/` endpoints
5. Check status code (nên là 200, 201, etc.)

### **Test 3: Try Using App**

1. Thử tạo class/event mới
2. Check Console cho logs
3. Kiểm tra Network tab cho requests

---

## 📋 Checklist - Kết Nối

- [ ] Backend CORS cập nhật ✅ (đã làm)
- [ ] Push changes lên GitHub
- [ ] Render auto-redeploy backend
- [ ] Cập nhật env var trên Cloudflare Dashboard
- [ ] Cloudflare auto-redeploy frontend
- [ ] Test fetch từ console ✓
- [ ] Test thực tế trên app ✓

---

## ⚠️ Nếu Vẫn Không Kết Nối (Troubleshooting)

### Lỗi 1: CORS error "Access-Control-Allow-Origin"
```
Solution:
1. Kiểm tra CORS config trong app.py
2. Xác nhận Cloudflare domain đúng
3. Backend phải allow origins của bạn
4. Restart backend service
```

### Lỗi 2: 404 Not Found
```
Solution:
1. Check backend URL: https://zencity-backend.onrender.com
2. Kiểm tra endpoint tồn tại (/api/events, /api/classes, etc.)
3. Xem backend logs trên Render dashboard
```

### Lỗi 3: Connection Timeout
```
Solution:
1. Backend có đang chạy không? (Render might be sleeping)
2. Render free tier tự động sleep sau 15 min không dùng
3. Fix: Upgrade Render hoặc thêm uptime monitor
4. Hoặc ping backend 1 request mỗi 10 phút
```

### Lỗi 4: Network Error
```
Solution:
1. Check internet connection
2. Backend URL có typo không?
3. REACT_APP_BACKEND_URL env var set không?
4. Xem browser DevTools Network tab
```

---

## 🔗 Quick Links

- **Cloudflare Dashboard:** https://dash.cloudflare.com/pages
- **Render Dashboard:** https://dashboard.render.com
- **Frontend Live:** https://c3514afb.zencity-smartcalendar.pages.dev
- **Backend Live:** https://zencity-backend.onrender.com

---

## 💡 Sau Khi Kết Nối Thành Công

### Mỗi lần update code:

**Frontend:**
```bash
git add .
git commit -m "message"
git push
# Cloudflare auto-redeploy (2-5 min)
```

**Backend:**
```bash
git add .
git commit -m "message"
git push
# Render auto-redeploy (1-2 min)
```

**Environment Variables:**
- Update trên Cloudflare Dashboard → Save & Deploy
- Không cần push code

---

## 📊 Architecture Sau Kết Nối

```
┌─────────────────────────────────────────────────────┐
│ User Browser                                        │
│ https://c3514afb.zencity-smartcalendar.pages.dev  │
└──────────────────┬──────────────────────────────────┘
                   │ (CORS allowed)
                   ↓
┌─────────────────────────────────────────────────────┐
│ Cloudflare Pages (Frontend)                         │
│ React app + FullCalendar                            │
└──────────────────┬──────────────────────────────────┘
                   │ API Calls
                   ↓
┌─────────────────────────────────────────────────────┐
│ Render (Backend)                                    │
│ https://zencity-backend.onrender.com               │
│ FastAPI + Google Calendar API                      │
└─────────────────────────────────────────────────────┘
```

---

## ✨ Kết Luận

Sau khi hoàn thành 3 bước trên, frontend và backend sẽ kết nối seamlessly!

- ✅ Frontend hiển thị lịch từ Google Calendar
- ✅ Có thể tạo/sửa/xóa events
- ✅ Auto-deploy hoạt động cho cả 2
- ✅ HTTPS hoàn toàn

**You're almost there!** 🚀

