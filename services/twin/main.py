"""
TwinOps Digital Twin Microservice Application.
FastAPI entrypoint for live digital twin states, derived KPIs, and WebSockets.
Ref: docs/04_architecture.md §2, docs/05_design_document.md §4, 5
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from services.common.database import AssetModel, async_session_factory, init_db, seed_pilot_data
from services.twin.api import router as twin_router
from services.twin.api import state_store, ws_router
from services.twin.mqtt_consumer import TwinMqttConsumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("twinops.twin.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: Initialize DB and populate twin state cache
    logger.info("Initializing database schema for Twin service...")
    await init_db()
    async with async_session_factory() as session:
        await seed_pilot_data(session)
        # Load asset records into in-memory state store
        res = await session.execute(select(AssetModel))
        assets = res.scalars().all()
        state_store.initialize_from_assets(
            [
                {
                    "id": a.id,
                    "name": a.name,
                    "type_id": a.type_id,
                    "criticality": a.criticality,
                    "position": a.position or {},
                    "lifecycle_state": a.lifecycle_state,
                }
                for a in assets
            ],
            site="PUNE-01",
        )
    logger.info("Twin service state store loaded.")

    # 2. Start MQTT consumer for live twin updates
    mqtt_consumer = TwinMqttConsumer(state_store)
    mqtt_consumer.start()

    # 3. Background task to detect stale/offline assets (TC-TWN-08)
    stop_event = asyncio.Event()

    async def _stale_monitor_loop():
        while not stop_event.is_set():
            try:
                stale_ids = state_store.check_stale_assets(timeout_seconds=15.0)
                if stale_ids:
                    logger.debug(f"Marked {len(stale_ids)} assets as stale/offline: {stale_ids}")
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stale monitor loop: {e}")

    monitor_task = asyncio.create_task(_stale_monitor_loop())

    yield

    # Shutdown
    logger.info("Shutting down Twin service...")
    stop_event.set()
    monitor_task.cancel()
    mqtt_consumer.stop()
    logger.info("Twin service shutdown complete.")


app = FastAPI(
    title="TwinOps Twin Service",
    description="Real-Time Digital Twin, Derived KPIs, and WebSocket Streaming",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount twin router & websocket router
app.include_router(twin_router)
app.include_router(ws_router)


@app.get("/healthz")
async def health_check():
    return {
        "status": "healthy",
        "service": "twin",
        "version": "1.0.0",
        "tracked_twins": len(state_store.get_all_twins()),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.twin.main:app", host="0.0.0.0", port=8003, reload=True)
