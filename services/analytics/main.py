"""
TwinOps Analytics, Anomaly Detection & RUL Microservice Entrypoint
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.analytics.api import router as analytics_router
from services.analytics.engine import analytics_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("twinops.analytics")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Analytics, Anomaly & RUL models...")
    # Pre-initialize states for pilot rotating equipment (Pumps, Spindles, Compressors)
    for asset_id in ["PUMP-01", "PUMP-02", "CNC-01", "CNC-02", "COMP-01"]:
        analytics_engine._get_or_create_state(asset_id)
    logger.info("Analytics models loaded and ready.")
    yield
    logger.info("Shutting down Analytics service...")


app = FastAPI(
    title="TwinOps Analytics & Machine Learning Service",
    description="OEE formulation, Isolation Forest anomaly scoring, and Weibull RUL prediction",
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

app.include_router(analytics_router)


@app.get("/healthz", tags=["health"])
async def health_check():
    return {
        "service": "twinops-analytics",
        "status": "healthy",
        "tracked_assets": len(analytics_engine.states),
    }


if __name__ == "__main__":
    uvicorn.run("services.analytics.main:app", host="0.0.0.0", port=8006, reload=True)
