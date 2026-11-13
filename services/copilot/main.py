"""
TwinOps AI Maintenance Copilot Microservice (ANL-04)
Runs on port 8007.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.common.database import init_db
from services.copilot.api import router as copilot_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("twinops.copilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing TwinOps AI Maintenance Copilot Service...")
    await init_db()
    logger.info("AI Copilot Service initialized with active RAG & tool registry.")
    yield
    logger.info("Shutting down AI Copilot Service...")


app = FastAPI(
    title="TwinOps AI Maintenance Copilot Service",
    description="Natural language Q&A, diagnostic reasoning, and RAG over industrial digital twins",
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

app.include_router(copilot_router)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "copilot",
        "guardrails": "active",
        "tools_count": 9,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.copilot.main:app", host="0.0.0.0", port=8007, reload=True)
