# ==============================================================================
# TwinOps Multi-Stage Production Dockerfile
# Stage 1: Build the React-Three-Fiber Web 3D Viewer Frontend
# Stage 2: Unified Python FastAPI Gateway + All 7 Microservices + Simulator
# ==============================================================================

FROM node:20-slim AS frontend-builder
WORKDIR /app/web

# Install frontend dependencies
COPY web/package.json web/package-lock.json* ./
RUN npm ci || npm install

# Copy web source and build production bundle
COPY web/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Production Python Runtime
# ==============================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies using pinned requirements.txt
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY README.md pyproject.toml ./
COPY simulator/ ./simulator/
COPY services/ ./services/
COPY ml/ ./ml/
COPY docs/ ./docs/

# Copy built frontend assets from Stage 1 into web/dist
COPY --from=frontend-builder /app/web/dist ./web/dist

# Expose standard container web port
EXPOSE 8000

# Launch the unified gateway (serves all APIs, WebSockets, background simulator, and 3D UI)
CMD ["python", "services/gateway.py"]
