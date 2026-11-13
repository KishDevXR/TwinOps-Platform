# ==============================================================================
# TwinOps Cloud Production Dockerfile
# Unified Python FastAPI Gateway + All 7 Microservices + Simulator + Web 3D Dist
# ==============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000


WORKDIR /app

# Install system dependencies (curl for health check / debugging)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies using pinned requirements.txt
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and prebuilt frontend distribution
COPY README.md pyproject.toml ./
COPY simulator/ ./simulator/
COPY services/ ./services/
COPY ml/ ./ml/
COPY docs/ ./docs/
COPY web/dist/ ./web/dist/

# Expose standard container web port
EXPOSE 8000

# Launch the unified gateway (serves all APIs, WebSockets, background simulator, and 3D UI)
CMD ["python", "-m", "services.gateway"]

