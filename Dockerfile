# ==============================================================================
# TwinOps Multi-Stage Production Dockerfile
# Stage 1: Build the React-Three-Fiber Web 3D Viewer Frontend
# Stage 2: Unified Python FastAPI Gateway + All 7 Microservices + Simulator
# ==============================================================================

FROM node:20-slim AS frontend-builder
WORKDIR /app/web

# Install frontend dependencies
COPY web/package.json web/package-lock.json* ./
RUN npm ci

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

# Install system dependencies (build-essential, curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir numpy scikit-learn scipy python-docx matplotlib

# Copy application source code
COPY simulator/ ./simulator/
COPY services/ ./services/
COPY ml/ ./ml/
COPY docs/ ./docs/

# Copy built frontend assets from Stage 1 into web/dist
COPY --from=frontend-builder /app/web/dist ./web/dist

# Expose standard container web port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Launch the unified gateway (serves all APIs, WebSockets, background simulator, and 3D UI)
CMD ["python", "services/gateway.py"]
