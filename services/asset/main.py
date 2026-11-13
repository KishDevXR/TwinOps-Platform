"""
TwinOps Asset Management Microservice Application.
FastAPI entrypoint for equipment hierarchy, twin metadata, and registry management.
Ref: docs/04_architecture.md §2, docs/05_design_document.md §5
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.asset.api import router as asset_router
from services.common.database import async_session_factory, init_db, seed_pilot_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("twinops.asset.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema for Asset service...")
    await init_db()
    async with async_session_factory() as session:
        await seed_pilot_data(session)
    logger.info("Asset service database ready.")
    yield
    logger.info("Asset service shutting down...")


app = FastAPI(
    title="TwinOps Asset Service",
    description="ISA-95 Equipment Hierarchy and Asset Registry Microservice",
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

# Mount asset router
app.include_router(asset_router)


@app.get("/healthz")
async def health_check():
    return {"status": "healthy", "service": "asset", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.asset.main:app", host="0.0.0.0", port=8002, reload=True)
