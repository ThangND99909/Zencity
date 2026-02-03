# Dependencies Documentation

## Backend (Python) - `requirements.txt`

### Core Dependencies
- **fastapi** (^0.104.1) - Modern web framework for building APIs
- **uvicorn** (^0.24.0) - ASGI server for running FastAPI applications
- **pydantic** (^2.5.0) - Data validation using Python type annotations
- **pydantic-settings** (^2.1.0) - Settings management for Pydantic

### Google APIs
- **google-api-python-client** (^1.12.5) - Client library for Google APIs
- **google-auth** (^2.25.2) - Authentication library for Google APIs
- **google-auth-httplib2** (^0.2.0) - HTTP transport for google-auth
- **google-auth-oauthlib** (^1.2.0) - OAuth 2.0 support for Google APIs
- **google-generativeai** (^0.3.0) - Google Gemini AI API for schedule suggestions

### Utilities
- **pytz** (^2023.3) - Timezone library for handling timezones
- **python-dotenv** (^1.0.0) - Load environment variables from .env files
- **httplib2** (^0.22.0) - HTTP client library
- **requests** (^2.31.0) - HTTP library for making requests

## Frontend (React/JavaScript) - `package.json`

### Core
- **react** (^18.2.0) - React library
- **react-dom** (^18.2.0) - React DOM rendering
- **react-scripts** (5.0.1) - Create React App build scripts

### Calendar & Scheduling
- **@fullcalendar/react** (^6.1.8) - React wrapper for FullCalendar
- **@fullcalendar/daygrid** (^6.1.8) - Day/week/month view plugin
- **@fullcalendar/timegrid** (^6.1.8) - Time-based view plugin
- **@fullcalendar/list** (^6.1.8) - List view plugin
- **@fullcalendar/interaction** (^6.1.8) - Event interaction plugin

### HTTP & Data
- **axios** (^1.6.0) - HTTP client for API requests
- **xlsx** (^0.18.5) - Excel file reading/writing support
- **file-saver** (^2.0.5) - Browser file download support

### Utilities
- **moment-timezone** (^0.6.0) - Timezone support in JavaScript (from root package.json)

---

## Production Deployment Checklist

### Before Deploying:
- [ ] All Python packages installed: `pip install -r requirements.txt`
- [ ] Frontend built: `cd Admin/frontend && npm run build`
- [ ] Environment variables configured in `.env` file:
  - `GEMINI_API_KEY` - Google Generative AI API key
  - Google Calendar service account JSON configured
  - Backend URL configured in frontend API service
- [ ] Google Calendar API enabled and service account created
- [ ] CORS settings configured appropriately for production domain

### Production Server Recommendation:
- Use **gunicorn** as production server wrapper for Uvicorn:
  ```bash
  pip install gunicorn
  gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app
  ```

### Docker (Optional):
- All dependencies can be containerized using Docker with these versions

---

## Version Notes

- **Python 3.8+** required for all Python dependencies
- **Node.js 16+** required for frontend dependencies
- All versions are pinned to specific versions for production stability
- Consider updating minor versions periodically for security patches

