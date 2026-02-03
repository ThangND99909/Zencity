FROM node:18-alpine AS frontend
WORKDIR /app/frontend
COPY Admin/frontend/package*.json ./
RUN npm install
COPY Admin/frontend/src ./src
COPY Admin/frontend/public ./public
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# Copy Python requirements
COPY Admin/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY Admin/backend /app/backend
WORKDIR /app/backend

# Copy built frontend từ stage 1
COPY --from=frontend /app/frontend/build /app/frontend/build

# Expose port
EXPOSE 8000

# Run backend
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
