# Smart Calendar Sync

Smart Calendar Sync is a full-stack application that allows seamless synchronization of events across devices. It provides a Google Calendar-like interface, supports recurring events, conflict checking, and optional AI-powered suggestions for scheduling.

---

## Features

- Sync events across multiple devices (laptop, tablet, smartphone)
- Google Calendar integration
- Recurring event management
- Conflict detection and resolution
- Optional AI agent for smart suggestions
- Admin-friendly schedule management
- Modern React frontend with modular components

---

## Project Structure

project/
│
├─ backend/
│ ├─ app.py # FastAPI backend
│ ├─ google_calendar.py # Wrapper for Google Calendar API
│ ├─ calendar_crud.py
│ ├─ check_conflict.py
│ ├─ recurrence_helper.py
│ ├─ recurrence_utils.py
│ ├─ service_account.json # Google service account credentials
│ └─ ai_agent.py # Optional AI agent for suggestions/conflict checks
│
├─ frontend/
│ ├─ src/
│ │ ├─ App.js # Main React component
│ │ ├─ index.js
│ │ ├─ pages/
│ │ │ ├─ AdminSchedule.module.css
│ │ │ └─ AdminSchedule.js
│ │ ├─ components/
│ │ │ ├─ ClassForm.js
│ │ │ ├─ ClassForm.module.css
│ │ │ ├─ ClassTable.js
│ │ │ ├─ ClassTable.module.css
│ │ │ ├─ DeleteConfirmationModal.js
│ │ │ ├─ DeleteConfirmationModal.module.css
│ │ │ ├─ EditRecurringModal.js
│ │ │ ├─ EditRecurringModal.module.css
│ │ │ ├─ EventContextMenu.js
│ │ │ ├─ EventContextMenu.module.css
│ │ │ ├─ LoadingOverlay.js
│ │ │ ├─ LoadingOverlay.module.css
│ │ │ ├─ CalendarView.module.css
│ │ │ └─ CalendarView.js
│ │ └─ services/
│ │ └─ api.js # Backend API calls
│ │ └─ styles/
│ │ └─ global.js
│ │ └─ utils/
│ │ └─ sanitizeDescription.js
│ └─ package.json
│
└─ requirements.txt

yaml
Copy code

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm or yarn
- Google service account with Calendar API access
- Internet connection for syncing

---

## Backend Setup

1. Navigate to the backend folder:

```bash

cài đặt Cloudflare:
winget install --id Cloudflare.cloudflared


# Terminal 1 - Backend
cd backend
cloudflared tunnel --url http://localhost:8000
Backend link (ví dụ: https://zen-backend.trycloudflare.com) → Cấu hình trong .env.production để frontend kết nối

# Terminal 2 - Frontend
cd frontend
npm install -g serve
npm run build
serve -s build -l 3001
cloudflared tunnel --url http://localhost:3001
Frontend link (ví dụ: https://zen-frontend.trycloudflare.com) → Chia sẻ link này cho người dùng khác

CLI deploy pro: npx wrangler pages deploy ./build --project-name zencity-smartcalendar

cd project/backend
Install dependencies:

bash
Copy code
pip install -r requirements.txt
Run backend (development mode): cd Admin -> cd backend

bash
Copy code
uvicorn app:app --reload
Run on specific port:

bash
Copy code
uvicorn app:app --reload --port=8000
Run on specific host:

bash
Copy code
uvicorn app:app --reload --host=0.0.0.0
Production mode (no reload):

bash
Copy code
uvicorn app:app --host=0.0.0.0 --port=8000
Frontend Setup
Navigate to the frontend folder:

bash
Copy code
cd Admin/frontend
Install dependencies:

bash
Copy code
npm install
# or
yarn install
Run the frontend:

bash
Copy code
npm start
# or
yarn start
The frontend should be accessible at http://localhost:3000

Configuration
Place your Google service account JSON in backend/service_account.json.

Configure API credentials in google_calendar.py if necessary.

Update frontend api.js with the backend URL if different from localhost.

Deployment Notes
Use Uvicorn with host 0.0.0.0 for production deployment.

Use build frontend for production:

bash
Copy code
cd frontend
npm run build

Ensure CORS is configured properly in app.py if serving frontend separately.

License
MIT License. See LICENSE file for details.


