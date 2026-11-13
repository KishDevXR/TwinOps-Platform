"""
TwinOps Analytics REST API Endpoints (ANL-01, ANL-02, ANL-03, ANL-05)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from services.analytics.engine import analytics_engine
from services.analytics.logistics import LOGISTICS_METRICS, calculate_logistics_kpis
from services.analytics.oee import (
    OEEResult,
    calculate_downtime_pareto,
    calculate_oee,
)
from services.common.database import TelemetryModel, async_session_factory

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# Schemas
class OEERequest(BaseModel):
    planned_time_s: float = Field(..., gt=0, description="Planned production time in seconds")
    operating_time_s: float = Field(..., ge=0, description="Actual operating time in seconds")
    ideal_cycle_time_s: float = Field(
        ..., gt=0, description="Theoretical minimum time per piece in seconds"
    )
    total_count: int = Field(..., ge=0, description="Total units produced")
    good_count: int = Field(..., ge=0, description="Conforming units produced")
    energy_kwh: float | None = None


class DowntimeEventItem(BaseModel):
    reason: str
    duration_minutes: float = Field(..., ge=0)


class DowntimeParetoRequest(BaseModel):
    events: list[DowntimeEventItem]


class AnomalyScoreRequest(BaseModel):
    asset_id: str
    window: dict[str, list[float]]


# --- ENDPOINTS ---


@router.post("/oee", response_model=OEEResult)
async def compute_oee(req: OEERequest) -> OEEResult:
    """
    Calculate SEMI E10 / ISO 22400 standard OEE metrics (TC-ANL-01).
    """
    try:
        return calculate_oee(
            planned_time_s=req.planned_time_s,
            operating_time_s=req.operating_time_s,
            ideal_cycle_time_s=req.ideal_cycle_time_s,
            total_count=req.total_count,
            good_count=req.good_count,
            energy_kwh=req.energy_kwh,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/assets/{asset_id}/oee")
async def get_asset_live_oee(asset_id: str) -> dict[str, Any]:
    """Retrieve default/live OEE estimate for pilot asset."""
    # Standard 8-hour shift nominal values
    res = calculate_oee(
        planned_time_s=28800.0,
        operating_time_s=25200.0,
        ideal_cycle_time_s=60.0,
        total_count=400,
        good_count=390,
        energy_kwh=118.0,
    )
    return {
        "asset_id": asset_id,
        "availability_pct": res.availability_pct,
        "performance_pct": res.performance_pct,
        "quality_pct": res.quality_pct,
        "oee_pct": res.oee_pct,
        "energy_per_part_kwh": res.energy_per_part_kwh,
    }


@router.post("/anomaly/score")
async def score_telemetry_window(req: AnomalyScoreRequest) -> dict[str, Any]:
    """Score a 5-minute sliding window using Isolation Forest (TC-ANL-02)."""
    state = analytics_engine._get_or_create_state(req.asset_id)
    score, contribs, is_persistent = state.anomaly_detector.score_window(req.window)
    return {
        "asset_id": req.asset_id,
        "anomaly_score": score,
        "is_persistent_anomaly": is_persistent,
        "contributing_signals": contribs,
    }


@router.get("/assets/{asset_id}/anomaly")
async def get_asset_anomaly(asset_id: str) -> dict[str, Any]:
    """Get live anomaly score and top contributors for an asset."""
    return analytics_engine.get_asset_anomaly(asset_id)


@router.get("/assets/{asset_id}/rul")
async def get_asset_rul(asset_id: str) -> dict[str, Any]:
    """Get Remaining Useful Life (RUL) prediction for rotating asset (TC-ANL-04)."""
    pred = analytics_engine.get_asset_rul(asset_id)
    return {
        "asset_id": pred.asset_id,
        "current_health_index": pred.current_health_index,
        "estimated_rul_hours": pred.estimated_rul_hours,
        "confidence_interval_hours": pred.confidence_interval_hours,
        "critical_threshold": pred.critical_threshold,
        "current_value": pred.current_value,
        "degradation_rate_per_hour": pred.degradation_rate_per_hour,
        "projected_failure_hours": pred.projected_failure_timestamp_hours,
    }


@router.post("/pareto/downtime")
async def get_downtime_pareto(req: DowntimeParetoRequest) -> list[dict[str, Any]]:
    """Compute 80/20 downtime Pareto distribution."""
    events = [e.model_dump() for e in req.events]
    return calculate_downtime_pareto(events)


@router.get("/logistics/kpis")
async def get_logistics_kpis(hours: float = Query(8.0, gt=0, le=168)) -> dict[str, Any]:
    """Dock and forklift KPIs over the last `hours` (LOG-03)."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    async with async_session_factory() as session:
        res = await session.execute(
            select(
                TelemetryModel.ts,
                TelemetryModel.asset_id,
                TelemetryModel.metric,
                TelemetryModel.value,
            )
            .where(TelemetryModel.metric.in_(LOGISTICS_METRICS), TelemetryModel.ts >= since)
            .order_by(TelemetryModel.ts)
        )
        rows = [tuple(r) for r in res.all()]
    return {"period_hours": hours, "assets": calculate_logistics_kpis(rows)}
