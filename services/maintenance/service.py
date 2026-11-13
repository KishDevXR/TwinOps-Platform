"""
TwinOps Maintenance Service (CMMS)
Handles work order lifecycles, checklist executions, parts inventory management,
calendar PM triggers, meter PM triggers, condition-based maintenance, and offline sync.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.common.database import (
    PMPlanModel,
    SparePartModel,
    WorkOrderModel,
    get_async_session,
)

logger = logging.getLogger("twinops.maintenance.service")


@dataclass
class ReorderAlert:
    part_id: str
    code: str
    name: str
    current_qty: int
    reorder_level: int
    triggered_at: datetime


class MaintenanceService:
    def __init__(self):
        self.reorder_alerts: list[ReorderAlert] = []
        self._lock = asyncio.Lock()

    async def create_work_order(
        self,
        asset_id: str,
        title: str,
        description: str | None = None,
        type: str = "corrective",
        priority: str = "medium",
        source: str = "manual",
        assignee: str | None = None,
        due_at: datetime | None = None,
        checklist: list[dict[str, Any]] | None = None,
        session: AsyncSession | None = None,
    ) -> WorkOrderModel:
        """Create a new work order (TC-MNT-01)."""
        now = datetime.now(UTC)
        wo = WorkOrderModel(
            asset_id=asset_id,
            title=title,
            description=description,
            type=type,
            priority=priority,
            source=source,
            status="assigned" if assignee else "open",
            assignee=assignee,
            due_at=due_at or (now + timedelta(days=2)),
            checklist=checklist or [],
            parts_used=[],
            labour_minutes=0,
            created_at=now,
        )

        async def _save(s: AsyncSession):
            s.add(wo)
            await s.flush()
            await s.refresh(wo)
            return wo

        if session:
            return await _save(session)
        else:
            async with get_async_session() as s:
                saved_wo = await _save(s)
                await s.commit()
                return saved_wo

    async def assign_work_order(
        self, work_order_id: int, assignee: str, session: AsyncSession | None = None
    ) -> WorkOrderModel | None:
        """Assign work order to a technician."""

        async def _assign(s: AsyncSession):
            res = await s.execute(select(WorkOrderModel).where(WorkOrderModel.id == work_order_id))
            wo = res.scalar_one_or_none()
            if not wo:
                return None
            wo.assignee = assignee
            if wo.status == "open":
                wo.status = "assigned"
            return wo

        if session:
            wo = await _assign(session)
            await session.flush()
            return wo
        else:
            async with get_async_session() as s:
                wo = await _assign(s)
                await s.commit()
                if wo:
                    await s.refresh(wo)
                return wo

    async def start_work_order(
        self, work_order_id: int, session: AsyncSession | None = None
    ) -> WorkOrderModel | None:
        """Technician starts working on the work order."""
        now = datetime.now(UTC)

        async def _start(s: AsyncSession):
            res = await s.execute(select(WorkOrderModel).where(WorkOrderModel.id == work_order_id))
            wo = res.scalar_one_or_none()
            if not wo:
                return None
            wo.status = "in_progress"
            wo.started_at = now
            return wo

        if session:
            wo = await _start(session)
            await session.flush()
            return wo
        else:
            async with get_async_session() as s:
                wo = await _start(s)
                await s.commit()
                if wo:
                    await s.refresh(wo)
                return wo

    async def complete_work_order(
        self,
        work_order_id: int,
        checklist: list[dict[str, Any]] | None = None,
        parts_used: list[dict[str, Any]] | None = None,
        labour_minutes: int = 0,
        session: AsyncSession | None = None,
    ) -> WorkOrderModel | None:
        """
        Complete a work order, save checklist, deduct parts from inventory (TC-MNT-02).
        """
        now = datetime.now(UTC)

        async def _complete(s: AsyncSession):
            res = await s.execute(select(WorkOrderModel).where(WorkOrderModel.id == work_order_id))
            wo = res.scalar_one_or_none()
            if not wo:
                return None

            wo.status = "completed"
            wo.completed_at = now
            wo.labour_minutes = labour_minutes
            if checklist is not None:
                wo.checklist = checklist

            # Deduct parts from inventory (TC-MNT-02)
            if parts_used:
                wo.parts_used = parts_used
                for p in parts_used:
                    part_code = p.get("code")
                    part_id = p.get("part_id")
                    qty_used = p.get("qty", 1)

                    part_query = select(SparePartModel)
                    if part_id:
                        part_query = part_query.where(SparePartModel.id == part_id)
                    elif part_code:
                        part_query = part_query.where(SparePartModel.code == part_code)

                    part_res = await s.execute(part_query)
                    part = part_res.scalar_one_or_none()
                    if part:
                        part.qty = max(0, part.qty - qty_used)
                        logger.info(
                            "Deducted %d x %s from inventory. Remaining: %d",
                            qty_used,
                            part.code,
                            part.qty,
                        )

                        # Check reorder alert (TC-MNT-06)
                        if part.qty <= part.reorder_level:
                            alert = ReorderAlert(
                                part_id=part.id,
                                code=part.code,
                                name=part.name,
                                current_qty=part.qty,
                                reorder_level=part.reorder_level,
                                triggered_at=now,
                            )
                            self.reorder_alerts.append(alert)
                            logger.warning(
                                "REORDER ALERT: Spare part %s (%s) dropped to %d (reorder level: %d)",
                                part.code,
                                part.name,
                                part.qty,
                                part.reorder_level,
                            )

            return wo

        if session:
            wo = await _complete(session)
            await session.flush()
            return wo
        else:
            async with get_async_session() as s:
                wo = await _complete(s)
                await s.commit()
                if wo:
                    await s.refresh(wo)
                return wo

    async def close_work_order(
        self, work_order_id: int, session: AsyncSession | None = None
    ) -> WorkOrderModel | None:
        """Close work order after QA/Supervisor review (TC-MNT-01)."""
        now = datetime.now(UTC)

        async def _close(s: AsyncSession):
            res = await s.execute(select(WorkOrderModel).where(WorkOrderModel.id == work_order_id))
            wo = res.scalar_one_or_none()
            if not wo:
                return None
            wo.status = "closed"
            wo.closed_at = now
            return wo

        if session:
            wo = await _close(session)
            await session.flush()
            return wo
        else:
            async with get_async_session() as s:
                wo = await _close(s)
                await s.commit()
                if wo:
                    await s.refresh(wo)
                return wo

    async def evaluate_calendar_pm(
        self, current_time: datetime | None = None, session: AsyncSession | None = None
    ) -> list[WorkOrderModel]:
        """
        Evaluate calendar PM plans (TC-MNT-03).
        If (now - last_done).days >= interval_days: auto-create preventive work order.
        """
        now = current_time or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        created_orders: list[WorkOrderModel] = []

        async def _eval(s: AsyncSession):
            res = await s.execute(select(PMPlanModel).where(PMPlanModel.trigger_type == "calendar"))
            plans = res.scalars().all()

            for plan in plans:
                if not plan.interval_days:
                    continue

                should_trigger = False
                if plan.last_done is None:
                    should_trigger = True
                else:
                    last_done = (
                        plan.last_done
                        if plan.last_done.tzinfo
                        else plan.last_done.replace(tzinfo=UTC)
                    )
                    elapsed_days = (now - last_done).total_seconds() / 86400.0
                    if elapsed_days >= plan.interval_days:
                        should_trigger = True

                if should_trigger:
                    checklist_items = [
                        {"task": item, "completed": False} for item in (plan.checklist or [])
                    ]
                    wo = WorkOrderModel(
                        asset_id=plan.asset_id,
                        title=f"PM: {plan.name}",
                        description=f"Automated calendar preventive maintenance (Interval: {plan.interval_days} days)",
                        type="preventive",
                        priority="medium",
                        source="pm",
                        status="open",
                        due_at=now + timedelta(days=3),
                        checklist=checklist_items,
                        created_at=now,
                    )
                    s.add(wo)
                    plan.last_done = now
                    created_orders.append(wo)
                    logger.info(
                        "Created calendar PM work order for %s: %s",
                        plan.asset_id,
                        plan.name,
                    )

            await s.flush()
            return created_orders

        if session:
            return await _eval(session)
        else:
            async with get_async_session() as s:
                orders = await _eval(s)
                await s.commit()
                return orders

    async def evaluate_meter_pm(
        self, asset_id: str, current_meter_hours: float, session: AsyncSession | None = None
    ) -> list[WorkOrderModel]:
        """
        Evaluate meter-based PM plans (TC-MNT-04).
        If (current_meter_hours - last_meter_hours) >= interval_hours: auto-create PM work order.
        """
        now = datetime.now(UTC)
        created_orders: list[WorkOrderModel] = []

        async def _eval(s: AsyncSession):
            res = await s.execute(
                select(PMPlanModel).where(
                    PMPlanModel.asset_id == asset_id,
                    PMPlanModel.trigger_type == "meter",
                )
            )
            plans = res.scalars().all()

            for plan in plans:
                if not plan.interval_hours:
                    continue

                last_hours = plan.last_meter_hours or 0.0
                delta_hours = current_meter_hours - last_hours

                if delta_hours >= plan.interval_hours:
                    checklist_items = [
                        {"task": item, "completed": False} for item in (plan.checklist or [])
                    ]
                    wo = WorkOrderModel(
                        asset_id=plan.asset_id,
                        title=f"Meter PM: {plan.name}",
                        description=f"Run-hours reached {current_meter_hours:.1f}h (Interval: {plan.interval_hours}h)",
                        type="preventive",
                        priority="high",
                        source="pm",
                        status="open",
                        due_at=now + timedelta(days=2),
                        checklist=checklist_items,
                        created_at=now,
                    )
                    s.add(wo)
                    plan.last_meter_hours = current_meter_hours
                    plan.last_done = now
                    created_orders.append(wo)
                    logger.info(
                        "Created meter PM work order for %s (%s) at %.1f hours",
                        plan.asset_id,
                        plan.name,
                        current_meter_hours,
                    )

            await s.flush()
            return created_orders

        if session:
            return await _eval(session)
        else:
            async with get_async_session() as s:
                orders = await _eval(s)
                await s.commit()
                return orders

    async def trigger_condition_based_maintenance(
        self,
        asset_id: str,
        alarm_id: int,
        metric: str,
        value: float,
        condition_message: str,
        session: AsyncSession | None = None,
    ) -> WorkOrderModel:
        """
        Trigger condition-based maintenance from sustained high/critical alarm (TC-MNT-05).
        """
        now = datetime.now(UTC)
        wo = WorkOrderModel(
            asset_id=asset_id,
            title=f"CBM: Corrective Action for {metric} anomaly ({asset_id})",
            description=f"Condition-based alert: {condition_message}. Measured value: {value:.2f} (Alarm Ref: #{alarm_id})",
            type="corrective",
            priority="critical",
            source="alarm",
            status="open",
            due_at=now + timedelta(hours=12),
            checklist=[
                {
                    "task": f"Isolate machine {asset_id} and follow LOTO procedures",
                    "completed": False,
                },
                {
                    "task": f"Inspect sensor and mechanical assembly for {metric}",
                    "completed": False,
                },
                {"task": "Perform corrective alignment / replacement", "completed": False},
                {
                    "task": "Run test cycle and verify vibration / thermal levels",
                    "completed": False,
                },
            ],
            created_at=now,
        )

        async def _save(s: AsyncSession):
            s.add(wo)
            await s.flush()
            await s.refresh(wo)
            logger.warning(
                "Triggered condition-based corrective work order #%d for %s: %s",
                wo.id,
                asset_id,
                wo.title,
            )
            return wo

        if session:
            return await _save(session)
        else:
            async with get_async_session() as s:
                saved = await _save(s)
                await s.commit()
                return saved

    async def sync_mobile_offline_batch(
        self, batch: list[dict[str, Any]], session: AsyncSession | None = None
    ) -> dict[str, Any]:
        """
        Reconcile and sync offline technician jobs without data loss (TC-MNT-07).
        """
        synced_count = 0
        now = datetime.now(UTC)

        async def _sync(s: AsyncSession):
            nonlocal synced_count
            for item in batch:
                wo_id = item.get("work_order_id")
                if not wo_id:
                    continue

                res = await s.execute(select(WorkOrderModel).where(WorkOrderModel.id == wo_id))
                wo = res.scalar_one_or_none()
                if wo:
                    if item.get("status"):
                        wo.status = item["status"]
                    if item.get("started_at"):
                        wo.started_at = datetime.fromisoformat(item["started_at"])
                    if item.get("completed_at"):
                        wo.completed_at = datetime.fromisoformat(item["completed_at"])
                    if item.get("checklist"):
                        wo.checklist = item["checklist"]
                    if item.get("parts_used"):
                        wo.parts_used = item["parts_used"]
                    if item.get("labour_minutes") is not None:
                        wo.labour_minutes = item["labour_minutes"]
                    synced_count += 1
            await s.flush()

        if session:
            await _sync(session)
        else:
            async with get_async_session() as s:
                await _sync(s)
                await s.commit()

        return {
            "status": "synchronized",
            "synced_count": synced_count,
            "server_time": now.isoformat(),
        }

    async def calculate_mttr_hours(self, session: AsyncSession | None = None) -> float:
        """Calculate Mean Time to Repair (MTTR) across completed/closed work orders."""

        async def _calc(s: AsyncSession):
            res = await s.execute(
                select(WorkOrderModel).where(
                    WorkOrderModel.started_at.is_not(None),
                    WorkOrderModel.completed_at.is_not(None),
                )
            )
            completed_orders = res.scalars().all()
            if not completed_orders:
                return 0.0

            durations = []
            for wo in completed_orders:
                if wo.started_at and wo.completed_at:
                    dur_hours = (wo.completed_at - wo.started_at).total_seconds() / 3600.0
                    durations.append(dur_hours)

            return sum(durations) / len(durations) if durations else 0.0

        if session:
            return await _calc(session)
        else:
            async with get_async_session() as s:
                return await _calc(s)


# Global service instance
maintenance_service = MaintenanceService()
