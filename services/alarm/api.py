"""
TwinOps Alarms & Rules REST API Endpoints (ISA-18.2)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.alarm.engine import alarm_engine
from services.common.canonical import CanonicalTelemetryMessage
from services.common.database import AlarmModel, AlarmRuleModel, get_db_session

router = APIRouter(prefix="/api/v1", tags=["alarms"])


# Pydantic Schemas
class AlarmAckRequest(BaseModel):
    user_id: str
    comment: str | None = None


class AlarmShelveRequest(BaseModel):
    user_id: str
    duration_minutes: float = Field(default=60.0, ge=1.0)
    reason: str | None = None


class AlarmRuleCreate(BaseModel):
    id: str
    asset_id: str | None = None
    asset_type_id: str | None = None
    metric: str
    rule_type: str = "threshold"
    severity: str = "high"
    threshold: float
    comparison: str = ">"
    delay_s: float = 0.0
    hysteresis: float = 0.0
    enabled: bool = True
    message_template: str


class AlarmSummaryResponse(BaseModel):
    total_active: int
    by_severity: dict[str, int]
    by_state: dict[str, int]
    flood_active: bool
    flood_suppressed_count: int


@router.get("/alarms")
async def list_alarms(
    state: str | None = Query(None, description="active, acked, cleared, shelved"),
    severity: str | None = Query(None, description="critical, high, medium, low"),
    asset_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List alarms with ISA-18.2 state and severity filters."""
    query = select(AlarmModel)

    if state:
        query = query.where(AlarmModel.state == state)
    if severity:
        query = query.where(AlarmModel.severity == severity)
    if asset_id:
        query = query.where(AlarmModel.asset_id == asset_id)

    query = query.order_by(desc(AlarmModel.raised_at)).offset(offset).limit(limit)
    res = await db.execute(query)
    alarms = res.scalars().all()

    items = []
    for a in alarms:
        items.append(
            {
                "id": a.id,
                "asset_id": a.asset_id,
                "metric": a.metric,
                "severity": a.severity,
                "rule_id": a.rule_id,
                "message": a.message,
                "value": a.value,
                "state": a.state,
                "raised_at": a.raised_at.isoformat() if a.raised_at else None,
                "acked_by": a.acked_by,
                "acked_at": a.acked_at.isoformat() if a.acked_at else None,
                "cleared_at": a.cleared_at.isoformat() if a.cleared_at else None,
                "shelved_until": a.shelved_until.isoformat() if a.shelved_until else None,
                "comment": a.comment,
            }
        )

    return {"total": len(items), "alarms": items}


@router.get("/alarms/summary", response_model=AlarmSummaryResponse)
async def get_alarm_summary(
    db: AsyncSession = Depends(get_db_session),
) -> AlarmSummaryResponse:
    """Get active alarm counts, breakdown by severity and state, and flood status."""
    res_active = await db.execute(
        select(AlarmModel.severity, func.count(AlarmModel.id))
        .where(AlarmModel.state.in_(["active", "acked"]))
        .group_by(AlarmModel.severity)
    )
    by_severity = {sev: count for sev, count in res_active.all()}

    res_state = await db.execute(
        select(AlarmModel.state, func.count(AlarmModel.id)).group_by(AlarmModel.state)
    )
    by_state = {st: count for st, count in res_state.all()}

    total_active = sum(by_severity.values())

    return AlarmSummaryResponse(
        total_active=total_active,
        by_severity=by_severity,
        by_state=by_state,
        flood_active=alarm_engine.flood_tracker.flood_active,
        flood_suppressed_count=alarm_engine.flood_tracker.suppressed_count,
    )


@router.get("/alarms/{alarm_id}")
async def get_alarm_detail(
    alarm_id: int, db: AsyncSession = Depends(get_db_session)
) -> dict[str, Any]:
    """Retrieve details for a single alarm."""
    res = await db.execute(select(AlarmModel).where(AlarmModel.id == alarm_id))
    a = res.scalar_one_or_none()
    if not a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Alarm {alarm_id} not found"
        )

    return {
        "id": a.id,
        "asset_id": a.asset_id,
        "metric": a.metric,
        "severity": a.severity,
        "rule_id": a.rule_id,
        "message": a.message,
        "value": a.value,
        "state": a.state,
        "raised_at": a.raised_at.isoformat() if a.raised_at else None,
        "acked_by": a.acked_by,
        "acked_at": a.acked_at.isoformat() if a.acked_at else None,
        "cleared_at": a.cleared_at.isoformat() if a.cleared_at else None,
        "shelved_until": a.shelved_until.isoformat() if a.shelved_until else None,
        "comment": a.comment,
    }


@router.post("/alarms/{alarm_id}/ack")
async def acknowledge_alarm(
    alarm_id: int,
    req: AlarmAckRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Acknowledge an alarm (TC-ALM-04)."""
    alarm = await alarm_engine.acknowledge_alarm(
        alarm_id=alarm_id,
        user_id=req.user_id,
        comment=req.comment,
        session=db,
    )
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Alarm {alarm_id} not found"
        )
    await db.commit()
    return {
        "id": alarm.id,
        "state": alarm.state,
        "acked_by": alarm.acked_by,
        "acked_at": alarm.acked_at.isoformat() if alarm.acked_at else None,
        "comment": alarm.comment,
    }


@router.post("/alarms/{alarm_id}/shelve")
async def shelve_alarm(
    alarm_id: int,
    req: AlarmShelveRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Shelve an alarm for a duration in minutes (TC-ALM-05)."""
    alarm = await alarm_engine.shelve_alarm(
        alarm_id=alarm_id,
        user_id=req.user_id,
        duration_minutes=req.duration_minutes,
        reason=req.reason,
        session=db,
    )
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Alarm {alarm_id} not found"
        )
    await db.commit()
    return {
        "id": alarm.id,
        "state": alarm.state,
        "shelved_by": alarm.shelved_by,
        "shelved_until": alarm.shelved_until.isoformat() if alarm.shelved_until else None,
        "comment": alarm.comment,
    }


@router.post("/alarms/{alarm_id}/unshelve")
async def unshelve_alarm(
    alarm_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Un-shelve an alarm before its timer expires."""
    alarm = await alarm_engine.unshelve_alarm(alarm_id=alarm_id, session=db)
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Alarm {alarm_id} not found"
        )
    await db.commit()
    return {
        "id": alarm.id,
        "state": alarm.state,
        "shelved_until": None,
    }


@router.get("/alarm-rules")
async def list_alarm_rules(
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """List all configured alarm rules."""
    res = await db.execute(select(AlarmRuleModel))
    rules = res.scalars().all()
    return [
        {
            "id": r.id,
            "asset_id": r.asset_id,
            "asset_type_id": r.asset_type_id,
            "metric": r.metric,
            "rule_type": r.rule_type,
            "severity": r.severity,
            "threshold": r.threshold,
            "comparison": r.comparison,
            "delay_s": r.delay_s,
            "hysteresis": r.hysteresis,
            "enabled": r.enabled,
            "message_template": r.message_template,
        }
        for r in rules
    ]


@router.post("/alarm-rules", status_code=status.HTTP_201_CREATED)
async def create_alarm_rule(
    req: AlarmRuleCreate, db: AsyncSession = Depends(get_db_session)
) -> dict[str, Any]:
    """Create a new alarm rule."""
    rule = AlarmRuleModel(**req.model_dump())
    db.add(rule)
    await db.commit()
    await alarm_engine.load_rules(db)
    return {"id": rule.id, "status": "created"}


@router.post("/alarm-rules/evaluate")
async def evaluate_telemetry_batch(
    payload: CanonicalTelemetryMessage,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Directly evaluate a telemetry payload and return newly triggered alarms."""
    raised = await alarm_engine.evaluate_telemetry(payload, session=db)
    await db.commit()
    return {
        "evaluated_asset": payload.asset_id,
        "alarms_raised": [
            {
                "id": a.id,
                "metric": a.metric,
                "severity": a.severity,
                "message": a.message,
                "value": a.value,
            }
            for a in raised
        ],
    }
