"""
TwinOps Maintenance / CMMS Microservice Entrypoint
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.common.database import get_async_session, init_db, seed_pilot_data
from services.maintenance.api import router as maintenance_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("twinops.maintenance")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Maintenance CMMS database...")
    await init_db()
    async with get_async_session() as session:
        await seed_pilot_data(session)
    logger.info("Maintenance CMMS service ready.")
    yield
    logger.info("Shutting down Maintenance CMMS service...")


app = FastAPI(
    title="TwinOps Maintenance CMMS Service",
    description="Work order management, PM plans, spare parts inventory, and offline mobile sync",
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

app.include_router(maintenance_router)


@app.get("/healthz", tags=["health"])
async def health_check():
    return {"service": "twinops-maintenance", "status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.maintenance.main:app", host="0.0.0.0", port=8005, reload=True)
