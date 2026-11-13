"""
TwinOps Alarms & Rules Engine Microservice Entrypoint
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.alarm.api import router as alarm_router
from services.alarm.engine import alarm_engine
from services.alarm.mqtt_consumer import AlarmMqttConsumer
from services.common.database import get_async_session, init_db, seed_pilot_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("twinops.alarm")

mqtt_consumer = AlarmMqttConsumer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Alarms & Rules Engine database...")
    await init_db()
    async with get_async_session() as session:
        await seed_pilot_data(session)

    # Preload active rules
    await alarm_engine.load_rules()

    # Start MQTT consumer background task
    consumer_task = asyncio.create_task(mqtt_consumer.start())
    logger.info("Alarms & Rules Engine ready.")

    yield

    logger.info("Shutting down Alarms service...")
    await mqtt_consumer.stop()
    consumer_task.cancel()


app = FastAPI(
    title="TwinOps Alarms & Rules Engine Service",
    description="ISA-18.2 compliant industrial alarm management and threshold evaluation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alarm_router)


@app.get("/healthz", tags=["health"])
async def health_check():
    return {
        "service": "twinops-alarm",
        "status": "healthy",
        "active_rules": len(alarm_engine.rules),
        "flood_active": alarm_engine.flood_tracker.flood_active,
    }


if __name__ == "__main__":
    uvicorn.run("services.alarm.main:app", host="0.0.0.0", port=8004, reload=True)
