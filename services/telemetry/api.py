"""
TwinOps Telemetry REST API.
Exposes time-series queries and batch ingestion endpoints.
Ref: docs/05_design_document.md §5
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.common.canonical import CanonicalTelemetryMessage
from services.common.database import IS_SQLITE, TelemetryModel, get_db_session
from services.telemetry.ingest import ingest_service

router = APIRouter(prefix="/api/v1", tags=["telemetry"])



class TelemetryPointResponse(BaseModel):
    ts: datetime
    asset_id: str
    metric: str
    value: float
    quality: int


class TelemetryAggregatePoint(BaseModel):
    bucket: str
    asset_id: str
    metric: str
    avg: float
    min: float
    max: float
    count: int


class IngestBatchResponse(BaseModel):
    status: str
    records_received: int
    buffered_count: int


@router.post(
    "/telemetry/ingest", response_model=IngestBatchResponse, status_code=status.HTTP_202_ACCEPTED
)
async def ingest_telemetry_batch(messages: list[CanonicalTelemetryMessage]):
    """
    Ingest a batch of Canonical Telemetry messages into the ingestion buffer.
    """
    if not messages:
        raise HTTPException(status_code=400, detail="Empty messages batch")

    await ingest_service.ingest_batch(messages)
    return IngestBatchResponse(
        status="accepted", records_received=len(messages), buffered_count=len(ingest_service.buffer)
    )


@router.get("/telemetry/stats")
async def get_telemetry_stats():
    """Retrieve telemetry ingestion buffer and throughput metrics."""
    return {
        "total_records_ingested": ingest_service.total_records_ingested,
        "total_batches_flushed": ingest_service.total_batches_flushed,
        "current_buffer_length": len(ingest_service.buffer),
        "last_flush_ts": ingest_service.last_flush_ts.isoformat()
        if ingest_service.last_flush_ts
        else None,
    }


@router.get("/assets/{asset_id}/telemetry")
async def get_asset_telemetry(
    asset_id: str,
    metric: str | None = Query(None, description="Metric name to filter, e.g. spindle_temp_c"),
    from_ts: datetime | None = Query(None, alias="from", description="ISO-8601 start timestamp"),
    to_ts: datetime | None = Query(None, alias="to", description="ISO-8601 end timestamp"),
    agg: Literal["raw", "1m", "1h"] | None = Query("raw", description="Aggregation bucket window"),
    limit: int = Query(1000, le=10000, description="Max raw points to return"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Query historical and recent telemetry for an asset.
    Supports raw point queries and 1-minute / 1-hour rollups.
    """
    # Flush pending in-memory buffer so the latest points are visible
    if len(ingest_service.buffer) > 0:
        await ingest_service.flush()

    if agg == "raw" or agg is None:
        query = select(TelemetryModel).where(TelemetryModel.asset_id == asset_id)
        if metric:
            query = query.where(TelemetryModel.metric == metric)
        if from_ts:
            query = query.where(TelemetryModel.ts >= from_ts)
        if to_ts:
            query = query.where(TelemetryModel.ts <= to_ts)

        query = query.order_by(TelemetryModel.ts.asc()).limit(limit)
        res = await session.execute(query)
        rows = res.scalars().all()

        return [
            TelemetryPointResponse(
                ts=r.ts, asset_id=r.asset_id, metric=r.metric, value=r.value, quality=r.quality
            )
            for r in rows
        ]

    # Aggregated 1m / 1h rollup
    bucket_fmt = "%Y-%m-%dT%H:%M:00Z" if agg == "1m" else "%Y-%m-%dT%H:00:00Z"

    if IS_SQLITE:
        bucket_expr = func.strftime(bucket_fmt, TelemetryModel.ts)
    else:
        # Timescale / PostgreSQL time_bucket
        interval = "1 minute" if agg == "1m" else "1 hour"
        bucket_expr = func.to_char(
            func.time_bucket(interval, TelemetryModel.ts), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'
        )

    agg_query = select(
        bucket_expr.label("bucket"),
        TelemetryModel.asset_id,
        TelemetryModel.metric,
        func.avg(TelemetryModel.value).label("avg_val"),
        func.min(TelemetryModel.value).label("min_val"),
        func.max(TelemetryModel.value).label("max_val"),
        func.count(TelemetryModel.id).label("val_count"),
    ).where(TelemetryModel.asset_id == asset_id)

    if metric:
        agg_query = agg_query.where(TelemetryModel.metric == metric)
    if from_ts:
        agg_query = agg_query.where(TelemetryModel.ts >= from_ts)
    if to_ts:
        agg_query = agg_query.where(TelemetryModel.ts <= to_ts)

    agg_query = (
        agg_query.group_by("bucket", TelemetryModel.asset_id, TelemetryModel.metric)
        .order_by(bucket_expr.asc())
        .limit(limit)
    )

    res = await session.execute(agg_query)
    rows = res.all()

    return [
        TelemetryAggregatePoint(
            bucket=str(r[0]),
            asset_id=r[1],
            metric=r[2],
            avg=round(float(r[3]), 3),
            min=round(float(r[4]), 3),
            max=round(float(r[5]), 3),
            count=int(r[6]),
        )
        for r in rows
    ]
