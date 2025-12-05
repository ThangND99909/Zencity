project/
│
├─ backend/
│   ├─ app.py               # FastAPI backend
│   ├─ google_calendar.py   # wrapper gọi Google Calendar API
│   └─ ai_agent.py          # optional, cho gợi ý/kiểm tra xung đột lịch
│
├─ frontend/
│   ├─ src/
│   │   ├─ App.js           # main React component
│   │   ├─ pages/
│   │   │   └─ AdminSchedule.js
│   │   ├─ components/
│   │   │   ├─ ClassForm.js
│   │   │   ├─ ClassTable.js
│   │   │   └─ CalendarView.js
│   │   └─ services/
│   │       └─ api.js       # gọi backend API
│   └─ package.json
│
└─ requirements.txt

# run backend
uvicorn app:app --reload
# Chạy với port cụ thể
uvicorn app:app --reload --port=8000

# Chạy với host cụ thể
uvicorn app:app --reload --host=0.0.0.0

# Chạy không reload (production)
uvicorn app:app --host=0.0.0.0 --port=8000

# run frontend
cd ...
npm start
