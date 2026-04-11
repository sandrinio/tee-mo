# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# Stage 1 — frontend build
# ---------------------------------------------------------------------------
FROM node:22-alpine AS builder-frontend
WORKDIR /build

# Copy package manifests first for layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy source + build
COPY frontend/ ./
RUN npm run build
# Output: /build/dist/

# ---------------------------------------------------------------------------
# Stage 2 — runtime (Python 3.11 + FastAPI + built frontend)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# System deps (build-essential needed by cryptography + other compiled deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend Python deps first for layer caching
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
RUN pip install --no-cache-dir -e ./backend

# Copy the built frontend from Stage 1 into /app/static/
COPY --from=builder-frontend /build/dist /app/static

# Runtime
WORKDIR /app/backend
EXPOSE 8000
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
