"""
TwinOps Telemetry Microservice Application.
FastAPI entrypoint for telemetry ingestion and time-series queries.
Ref: docs/04_architecture.md §2
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.common.database import async_session_factory, init_db, seed_pilot_data
from services.telemetry.api import ingest_service
from services.telemetry.api import router as telemetry_router
from services.telemetry.mqtt_consumer import TelemetryMqttConsumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("twinops.telemetry.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: Initialize DB and seed baseline
    logger.info("Initializing database schema...")
    await init_db()
    async with async_session_factory() as session:
        await seed_pilot_data(session)
    logger.info("Database schema initialized and pilot data verified.")

    # 2. Start telemetry flusher
    ingest_service.start()

    # 3. Optionally start MQTT consumer
    mqtt_consumer = TelemetryMqttConsumer(ingest_service)
    mqtt_consumer.start()

    yield

    # Shutdown
    logger.info("Shutting down telemetry microservice...")
    mqtt_consumer.stop()
    await ingest_service.stop()
    logger.info("Telemetry microservice shutdown complete.")


app = FastAPI(
    title="TwinOps Telemetry Service",
    description="High-throughput time-series telemetry ingestion and analytics API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for web frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount telemetry API router
app.include_router(telemetry_router)


@app.get("/healthz")
async def health_check():
    return {
        "status": "healthy",
        "service": "telemetry",
        "version": "1.0.0",
        "buffered_records": len(ingest_service.buffer),
        "total_ingested": ingest_service.total_records_ingested,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.telemetry.main:app", host="0.0.0.0", port=8001, reload=True)
