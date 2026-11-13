"""
TwinOps Unified Cloud Gateway & Standalone Server
Mounts all microservice routers, initializes databases, launches background plant simulation,
and serves the React-Three-Fiber frontend from 'web/dist'.

Enables 1-click deployment on 100% free cloud tiers (Render, Hugging Face Spaces, Koyeb, Fly.io).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from services.alarm.api import router as alarm_router
from services.alarm.engine import alarm_engine
from services.analytics.api import router as analytics_router
from services.asset.api import router as asset_router
from services.common.database import get_async_session, init_db, seed_pilot_data
from services.copilot.api import router as copilot_router
from services.maintenance.api import router as maintenance_router
from services.telemetry.api import router as telemetry_router
from services.telemetry.ingest import ingest_service
from services.twin.api import router as twin_router
from services.twin.api import state_store, ws_router
from simulator.plant import VirtualPlant

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("twinops.gateway")

WEB_DIST = Path("web/dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing TwinOps Unified Platform...")
    # 1. Initialize SQLite / TimescaleDB
    await init_db()
    async with get_async_session() as session:
        await seed_pilot_data(session)

    # 2. Preload rules & start telemetry flusher
    await alarm_engine.load_rules()
    ingest_service.start()

    # 3. Background simulator loop feeding live digital twin
    stop_event = asyncio.Event()
    plant = VirtualPlant(site="PUNE-01")

    async def _simulation_clock_loop():
        logger.info("Starting background plant simulation engine (interval=1.0s)...")
        while not stop_event.is_set():
            try:
                for machine in plant.list_machines():
                    msg = machine.step(1.0)
                    if msg:
                        # Feed ingest buffer & twin state store
                        await ingest_service.ingest_message(msg)
                        await state_store.update_from_telemetry(msg)
                        await alarm_engine.evaluate_telemetry(msg)
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in plant simulation loop: {e}")
                await asyncio.sleep(1.0)

    sim_task = asyncio.create_task(_simulation_clock_loop())
    logger.info("TwinOps Unified Platform is ready.")

    yield

    logger.info("Shutting down TwinOps Platform...")
    stop_event.set()
    sim_task.cancel()
    await ingest_service.stop()


app = FastAPI(
    title="TwinOps Unified Platform",
    description="Digital-Twin Asset Management Platform for Industrial Plants",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all domain microservice routers
app.include_router(asset_router)
app.include_router(telemetry_router)
app.include_router(twin_router)
app.include_router(ws_router)
app.include_router(alarm_router)
app.include_router(maintenance_router)
app.include_router(analytics_router)
app.include_router(copilot_router)


@app.get("/healthz", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "twinops-unified-gateway",
        "version": "2.0.0",
        "tracked_twins": len(state_store.get_all_twins()),
        "active_rules": len(alarm_engine.rules),
    }


# Mount Static Frontend if built
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Allow API routes to be handled by routers
        file_path = WEB_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(WEB_DIST / "index.html")


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("services.gateway:app", host="0.0.0.0", port=port, reload=False)
