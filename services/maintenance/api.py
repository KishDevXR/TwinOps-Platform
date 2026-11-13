"""
TwinOps Maintenance REST API Endpoints (CMMS)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.common.database import (
    PMPlanModel,
    SparePartModel,
    WorkOrderModel,
    get_db_session,
)
from services.maintenance.service import maintenance_service

router = APIRouter(prefix="/api/v1", tags=["maintenance"])


# Pydantic Schemas
class WorkOrderCreate(BaseModel):
    asset_id: str
    title: str
    description: str | None = None
    type: str = "corrective"
    priority: str = "medium"
    source: str = "manual"
    assignee: str | None = None
    due_at: datetime | None = None
    checklist: list[dict[str, Any]] | None = None


class WorkOrderAssign(BaseModel):
    assignee: str


class WorkOrderComplete(BaseModel):
    checklist: list[dict[str, Any]] | None = None
    parts_used: list[dict[str, Any]] | None = None
    labour_minutes: int = Field(default=0, ge=0)


class PMPlanCreate(BaseModel):
    asset_id: str
    name: str
    trigger_type: str = "meter"  # calendar, meter
    interval_days: int | None = None
    interval_hours: int | None = None
    checklist: list[str] = []


class SparePartConsume(BaseModel):
    qty: int = Field(default=1, ge=1)
    work_order_id: int | None = None


class SparePartRestock(BaseModel):
    qty: int = Field(default=1, ge=1)


class MobileSyncBatch(BaseModel):
    batch: list[dict[str, Any]]


# --- WORK ORDERS ---


@router.get("/work-orders")
async def list_work_orders(
    status: str | None = Query(None, description="open, assigned, in_progress, completed, closed"),
    asset_id: str | None = Query(None),
    priority: str | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List work orders with optional filtering."""
    query = select(WorkOrderModel)
    if status:
        query = query.where(WorkOrderModel.status == status)
    if asset_id:
        query = query.where(WorkOrderModel.asset_id == asset_id)
    if priority:
        query = query.where(WorkOrderModel.priority == priority)
    if type:
        query = query.where(WorkOrderModel.type == type)

    query = query.order_by(desc(WorkOrderModel.created_at)).offset(offset).limit(limit)
    res = await db.execute(query)
    orders = res.scalars().all()

    items = []
    for wo in orders:
        items.append(
            {
                "id": wo.id,
                "asset_id": wo.asset_id,
                "title": wo.title,
                "description": wo.description,
                "type": wo.type,
                "priority": wo.priority,
                "status": wo.status,
                "assignee": wo.assignee,
                "source": wo.source,
                "due_at": wo.due_at.isoformat() if wo.due_at else None,
                "started_at": wo.started_at.isoformat() if wo.started_at else None,
                "completed_at": wo.completed_at.isoformat() if wo.completed_at else None,
                "closed_at": wo.closed_at.isoformat() if wo.closed_at else None,
                "checklist": wo.checklist,
                "parts_used": wo.parts_used,
                "labour_minutes": wo.labour_minutes,
                "created_at": wo.created_at.isoformat() if wo.created_at else None,
            }
        )
    return {"total": len(items), "work_orders": items}


@router.get("/work-orders/{id}")
async def get_work_order(id: int, db: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """Get single work order detail."""
    res = await db.execute(select(WorkOrderModel).where(WorkOrderModel.id == id))
    wo = res.scalar_one_or_none()
    if not wo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order #{id} not found"
        )
    return {
        "id": wo.id,
        "asset_id": wo.asset_id,
        "title": wo.title,
        "description": wo.description,
        "type": wo.type,
        "priority": wo.priority,
        "status": wo.status,
        "assignee": wo.assignee,
        "source": wo.source,
        "due_at": wo.due_at.isoformat() if wo.due_at else None,
        "started_at": wo.started_at.isoformat() if wo.started_at else None,
        "completed_at": wo.completed_at.isoformat() if wo.completed_at else None,
        "closed_at": wo.closed_at.isoformat() if wo.closed_at else None,
        "checklist": wo.checklist,
        "parts_used": wo.parts_used,
        "labour_minutes": wo.labour_minutes,
        "created_at": wo.created_at.isoformat() if wo.created_at else None,
    }


@router.post("/work-orders", status_code=status.HTTP_201_CREATED)
async def create_work_order(
    req: WorkOrderCreate, db: AsyncSession = Depends(get_db_session)
) -> dict[str, Any]:
    """Create a new work order (TC-MNT-01)."""
    wo = await maintenance_service.create_work_order(
        asset_id=req.asset_id,
        title=req.title,
        description=req.description,
        type=req.type,
        priority=req.priority,
        source=req.source,
        assignee=req.assignee,
        due_at=req.due_at,
        checklist=req.checklist,
        session=db,
    )
    await db.commit()
    return {"id": wo.id, "status": wo.status}


@router.post("/work-orders/{id}/assign")
async def assign_work_order(
    id: int, req: WorkOrderAssign, db: AsyncSession = Depends(get_db_session)
) -> dict[str, Any]:
    """Assign work order to a technician."""
    wo = await maintenance_service.assign_work_order(id, req.assignee, session=db)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await db.commit()
    return {"id": wo.id, "status": wo.status, "assignee": wo.assignee}


@router.post("/work-orders/{id}/start")
async def start_work_order(id: int, db: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """Start work order (transitions to in_progress)."""
    wo = await maintenance_service.start_work_order(id, session=db)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await db.commit()
    return {
        "id": wo.id,
        "status": wo.status,
        "started_at": wo.started_at.isoformat() if wo.started_at else None,
    }


@router.post("/work-orders/{id}/complete")
async def complete_work_order(
    id: int, req: WorkOrderComplete, db: AsyncSession = Depends(get_db_session)
) -> dict[str, Any]:
    """Complete work order and record parts consumed & checklist (TC-MNT-02)."""
    wo = await maintenance_service.complete_work_order(
        work_order_id=id,
        checklist=req.checklist,
        parts_used=req.parts_used,
        labour_minutes=req.labour_minutes,
        session=db,
    )
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await db.commit()
    return {
        "id": wo.id,
        "status": wo.status,
        "completed_at": wo.completed_at.isoformat() if wo.completed_at else None,
        "labour_minutes": wo.labour_minutes,
    }


@router.post("/work-orders/{id}/close")
async def close_work_order(id: int, db: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """Close completed work order (TC-MNT-01)."""
    wo = await maintenance_service.close_work_order(id, session=db)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await db.commit()
    return {
        "id": wo.id,
        "status": wo.status,
        "closed_at": wo.closed_at.isoformat() if wo.closed_at else None,
    }


@router.post("/work-orders/sync")
async def sync_mobile_offline(
    req: MobileSyncBatch, db: AsyncSession = Depends(get_db_session)
) -> dict[str, Any]:
    """Mobile offline synchronization endpoint (TC-MNT-07)."""
    res = await maintenance_service.sync_mobile_offline_batch(req.batch, session=db)
    await db.commit()
    return res


# --- PREVENTIVE MAINTENANCE PLANS ---


@router.get("/pm-plans")
async def list_pm_plans(
    asset_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """List all PM plans."""
    query = select(PMPlanModel)
    if asset_id:
        query = query.where(PMPlanModel.asset_id == asset_id)
    res = await db.execute(query)
    plans = res.scalars().all()
    return [
        {
            "id": p.id,
            "asset_id": p.asset_id,
            "name": p.name,
            "trigger_type": p.trigger_type,
            "interval_days": p.interval_days,
            "interval_hours": p.interval_hours,
            "last_meter_hours": p.last_meter_hours,
            "checklist": p.checklist,
            "last_done": p.last_done.isoformat() if p.last_done else None,
        }
        for p in plans
    ]


@router.post("/pm-plans/evaluate-calendar")
async def evaluate_calendar_pm_plans(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Trigger calendar PM evaluation (TC-MNT-03)."""
    created = await maintenance_service.evaluate_calendar_pm(session=db)
    await db.commit()
    return {
        "created_work_orders": [
            {"id": wo.id, "asset_id": wo.asset_id, "title": wo.title} for wo in created
        ]
    }


@router.post("/pm-plans/evaluate-meter")
async def evaluate_meter_pm_plans(
    asset_id: str = Query(...),
    run_hours: float = Query(...),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Trigger meter PM evaluation (TC-MNT-04)."""
    created = await maintenance_service.evaluate_meter_pm(
        asset_id=asset_id, current_meter_hours=run_hours, session=db
    )
    await db.commit()
    return {
        "created_work_orders": [
            {"id": wo.id, "asset_id": wo.asset_id, "title": wo.title} for wo in created
        ]
    }


# --- SPARE PARTS INVENTORY ---


@router.get("/parts")
async def list_spare_parts(
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """List all spare parts."""
    res = await db.execute(select(SparePartModel))
    parts = res.scalars().all()
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "qty": p.qty,
            "reorder_level": p.reorder_level,
            "location": p.location,
            "unit_cost": p.unit_cost,
        }
        for p in parts
    ]


@router.post("/parts/{code}/consume")
async def consume_spare_part(
    code: str,
    req: SparePartConsume,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Deduct spare parts from inventory."""
    res = await db.execute(select(SparePartModel).where(SparePartModel.code == code))
    part = res.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Part {code} not found")

    part.qty = max(0, part.qty - req.qty)
    await db.commit()
    return {"code": part.code, "remaining_qty": part.qty}


@router.get("/parts/reorder-alerts")
async def get_reorder_alerts() -> list[dict[str, Any]]:
    """Get active spare parts reorder alerts (TC-MNT-06)."""
    return [
        {
            "part_id": a.part_id,
            "code": a.code,
            "name": a.name,
            "current_qty": a.current_qty,
            "reorder_level": a.reorder_level,
            "triggered_at": a.triggered_at.isoformat(),
        }
        for a in maintenance_service.reorder_alerts
    ]


# --- METRICS ---


@router.get("/maintenance/metrics")
async def get_maintenance_metrics(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get CMMS maintenance KPIs including MTTR, open orders, and PM vs CM count."""
    mttr_hours = await maintenance_service.calculate_mttr_hours(session=db)

    res_open = await db.execute(
        select(func.count(WorkOrderModel.id)).where(
            WorkOrderModel.status.in_(["open", "assigned", "in_progress", "on_hold"])
        )
    )
    open_count = res_open.scalar() or 0

    res_types = await db.execute(
        select(WorkOrderModel.type, func.count(WorkOrderModel.id)).group_by(WorkOrderModel.type)
    )
    by_type = {t: count for t, count in res_types.all()}

    return {
        "mttr_hours": round(mttr_hours, 2),
        "open_work_orders": open_count,
        "orders_by_type": by_type,
    }
