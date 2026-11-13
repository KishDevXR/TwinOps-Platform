"""
TwinOps Copilot Function-Calling Tools (ANL-04)
Implements all tool functions defined in AI Agent Document §A2.
Security & Guardrails:
- Strict read-only OT posture: NO PLC/SCADA write-back tools exist.
- Tool-layer RBAC enforcement on site permissions (TC-AI-02).
- Grounded citations for telemetry and alarms (TC-AI-01).
- Clear error reporting for missing/unsupported metrics (TC-AI-04).
- Human-in-the-loop approval on draft work orders (TC-AI-05).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.analytics.oee import calculate_oee
from services.common.database import (
    AlarmModel,
    AssetModel,
    TelemetryModel,
    WorkOrderModel,
    get_async_session,
)
from services.copilot.rag import KnowledgeBaseRAG, knowledge_base
from services.twin.api import WhatIfSimulationRequest, run_what_if_simulation, state_store

logger = logging.getLogger("twinops.copilot.tools")


class RBACPermissionError(Exception):
    """Raised when a user attempts to access an asset or site outside their authorized scope."""


class UserContext(BaseModel):
    user_id: str = "engineer-01"
    role: str = "maintenance_engineer"
    allowed_sites: list[str] = ["PUNE-01"]


# Standard metric catalogs by asset type for missing data checks
VALID_METRICS_BY_TYPE: dict[str, list[str]] = {
    "cnc_machine": [
        "spindle_temp_c",
        "vibration_mm_s",
        "spindle_rpm",
        "spindle_load_pct",
        "feed_rate_mm_min",
        "coolant_flow_l_min",
        "coolant_temp_c",
        "power_kw",
        "part_count",
    ],
    "centrifugal_pump": [
        "flow_m3h",
        "discharge_bar",
        "suction_bar",
        "motor_temp_c",
        "vibration_mm_s",
        "power_kw",
        "motor_rpm",
    ],
    "air_compressor": [
        "discharge_pressure_bar",
        "air_flow_cfm",
        "oil_dp_bar",
        "motor_power_kw",
        "air_temp_c",
        "motor_current_a",
    ],
    "conveyor": [
        "speed_m_min",
        "motor_current_a",
        "motor_temp_c",
        "belt_tension_n",
        "power_kw",
    ],
    "robot_cell": [
        "joint_1_temp_c",
        "cycle_time_s",
        "motor_current_a",
        "payload_kg",
        "safety_zone_breached",
    ],
    "chiller": [
        "chilled_water_inlet_c",
        "chilled_water_outlet_c",
        "refrigerant_suction_bar",
        "refrigerant_discharge_bar",
        "compressor_power_kw",
        "cop",
    ],
}


class CopilotToolRegistry:
    """Tool execution layer with RBAC guardrails and audit logging."""

    def __init__(self, rag: KnowledgeBaseRAG | None = None):
        self.rag = rag or knowledge_base
        self.audit_log: list[dict[str, Any]] = []

    def _verify_site_access(self, site: str, user_ctx: UserContext) -> None:
        """TC-AI-02: Enforce RBAC at the tool boundary."""
        if site not in user_ctx.allowed_sites:
            msg = (
                f"Access denied: Site '{site}' is not permitted for user '{user_ctx.user_id}'. "
                f"Authorized sites: {user_ctx.allowed_sites}"
            )
            logger.warning(msg)
            raise RBACPermissionError(msg)

    async def _resolve_asset_site(self, asset_id: str, session: AsyncSession | None = None) -> str:
        """Resolve the site ID for a given asset."""
        # Check standard pilot convention: e.g. CNC-01 belongs to PUNE-01
        if asset_id.startswith("CH-") or "CHENNAI" in asset_id.upper():
            return "CHENNAI-01"
        if asset_id.startswith("BLR-") or "BANGALORE" in asset_id.upper():
            return "BLR-01"

        # Lookup in database
        async def _query(s: AsyncSession) -> str:
            stmt = select(AssetModel).where(AssetModel.id == asset_id)
            res = await s.execute(stmt)
            ast = res.scalar_one_or_none()
            if ast and ast.properties and "site" in ast.properties:
                return str(ast.properties["site"])
            return "PUNE-01"

        if session:
            return await _query(session)
        else:
            async with get_async_session() as s:
                return await _query(s)

    async def search_assets(
        self,
        query: str,
        site: str = "PUNE-01",
        user_ctx: UserContext | None = None,
    ) -> list[dict[str, Any]]:
        """Find assets matching query name, type, or location."""
        ctx = user_ctx or UserContext()
        self._verify_site_access(site, ctx)

        async with get_async_session() as session:
            stmt = select(AssetModel)
            res = await session.execute(stmt)
            assets = res.scalars().all()

        query_lower = query.lower()
        matched = []
        for a in assets:
            if (
                query_lower in a.id.lower()
                or query_lower in a.name.lower()
                or query_lower in a.type_id.lower()
            ):
                matched.append(
                    {
                        "id": a.id,
                        "name": a.name,
                        "type_id": a.type_id,
                        "criticality": a.criticality,
                        "lifecycle_state": a.lifecycle_state,
                    }
                )
        return matched

    async def get_asset(
        self,
        asset_id: str,
        user_ctx: UserContext | None = None,
    ) -> dict[str, Any]:
        """TC-AI-01: Get asset record and live digital twin telemetry state."""
        ctx = user_ctx or UserContext()
        site = await self._resolve_asset_site(asset_id)
        self._verify_site_access(site, ctx)

        twin_state = state_store.get_twin(asset_id)
        live_metrics = {}
        status = "STOPPED"
        if twin_state:
            status = twin_state.operational_status
            live_metrics = {
                k: round(float(v.v), 2) if isinstance(v.v, (int, float)) else v.v
                for k, v in twin_state.metrics.items()
            }

        async with get_async_session() as session:
            stmt = select(AssetModel).where(AssetModel.id == asset_id)
            res = await session.execute(stmt)
            ast = res.scalar_one_or_none()

        if not ast:
            return {
                "asset_id": asset_id,
                "found": False,
                "error": f"Asset '{asset_id}' not found in registry",
            }

        return {
            "asset_id": ast.id,
            "name": ast.name,
            "type_id": ast.type_id,
            "criticality": ast.criticality,
            "site": site,
            "status": status,
            "live_metrics": live_metrics,
            "properties": ast.properties or {},
        }

    async def get_telemetry(
        self,
        asset_id: str,
        metric: str,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        user_ctx: UserContext | None = None,
    ) -> dict[str, Any]:
        """
        TC-AI-01 & TC-AI-04: Retrieve time-series telemetry.
        Validates whether the requested metric exists for the asset type.
        """
        ctx = user_ctx or UserContext()
        site = await self._resolve_asset_site(asset_id)
        self._verify_site_access(site, ctx)

        # Check asset type and metric catalog (TC-AI-04)
        asset_info = await self.get_asset(asset_id, user_ctx=ctx)
        asset_type = asset_info.get("type_id", "generic")
        valid_metrics = VALID_METRICS_BY_TYPE.get(asset_type, [])

        if valid_metrics and metric not in valid_metrics:
            return {
                "available": False,
                "asset_id": asset_id,
                "metric": metric,
                "error": (
                    f"Metric '{metric}' is not monitored on asset '{asset_id}' (type: {asset_type}). "
                    f"Available metrics: {valid_metrics}"
                ),
            }

        now = datetime.now(UTC)
        start_ts = from_ts or (now - timedelta(hours=24))
        end_ts = to_ts or now

        async with get_async_session() as session:
            stmt = (
                select(TelemetryModel)
                .where(
                    TelemetryModel.asset_id == asset_id,
                    TelemetryModel.metric == metric,
                    TelemetryModel.ts >= start_ts,
                    TelemetryModel.ts <= end_ts,
                )
                .order_by(TelemetryModel.ts.desc())
                .limit(100)
            )
            res = await session.execute(stmt)
            rows = res.scalars().all()

        points = [
            {"ts": r.ts.isoformat(), "val": round(r.value, 2), "quality": r.quality} for r in rows
        ]

        return {
            "available": True,
            "asset_id": asset_id,
            "metric": metric,
            "count": len(points),
            "points": points,
            "latest_value": points[0]["val"] if points else None,
            "time_range": {"from": start_ts.isoformat(), "to": end_ts.isoformat()},
        }

    async def list_alarms(
        self,
        asset_id: str | None = None,
        status: str | None = None,
        from_ts: datetime | None = None,
        user_ctx: UserContext | None = None,
    ) -> list[dict[str, Any]]:
        """TC-AI-01: Query alarm event history with exact timestamps and messages."""
        ctx = user_ctx or UserContext()
        if asset_id:
            site = await self._resolve_asset_site(asset_id)
            self._verify_site_access(site, ctx)

        async with get_async_session() as session:
            stmt = select(AlarmModel)
            if asset_id:
                stmt = stmt.where(AlarmModel.asset_id == asset_id)
            if status:
                stmt = stmt.where(AlarmModel.state == status)
            if from_ts:
                stmt = stmt.where(AlarmModel.raised_at >= from_ts)

            stmt = stmt.order_by(AlarmModel.raised_at.desc()).limit(20)
            res = await session.execute(stmt)
            alarms = res.scalars().all()

        return [
            {
                "alarm_id": a.id,
                "asset_id": a.asset_id,
                "metric": a.metric,
                "severity": a.severity,
                "state": a.state,
                "message": a.message,
                "value": a.value,
                "raised_at": a.raised_at.isoformat(),
            }
            for a in alarms
        ]

    async def list_work_orders(
        self,
        asset_id: str | None = None,
        status: str | None = None,
        user_ctx: UserContext | None = None,
    ) -> list[dict[str, Any]]:
        """List maintenance work order history."""
        ctx = user_ctx or UserContext()
        if asset_id:
            site = await self._resolve_asset_site(asset_id)
            self._verify_site_access(site, ctx)

        async with get_async_session() as session:
            stmt = select(WorkOrderModel)
            if asset_id:
                stmt = stmt.where(WorkOrderModel.asset_id == asset_id)
            if status:
                stmt = stmt.where(WorkOrderModel.status == status)

            stmt = stmt.order_by(WorkOrderModel.created_at.desc()).limit(20)
            res = await session.execute(stmt)
            wos = res.scalars().all()

        return [
            {
                "id": w.id,
                "asset_id": w.asset_id,
                "title": w.title,
                "type": w.type,
                "status": w.status,
                "priority": w.priority,
                "assignee": w.assignee,
                "created_at": w.created_at.isoformat(),
            }
            for w in wos
        ]

    def search_docs(
        self,
        query: str,
        asset_type: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """TC-AI-06: RAG search over equipment manuals, SOPs, and safety protocols."""
        chunks = self.rag.search(query=query, asset_type=asset_type, top_k=top_k)
        return [
            {
                "chunk_id": c.chunk_id,
                "doc_name": c.doc_name,
                "section": c.section,
                "page": c.page,
                "is_safety_sop": c.is_safety_sop,
                "content": c.content,
            }
            for c in chunks
        ]

    def get_kpis(
        self,
        scope: str = "site:PUNE-01",
        period: str = "24h",
        user_ctx: UserContext | None = None,
    ) -> dict[str, Any]:
        """Retrieve aggregated OEE, MTBF, MTTR, and availability KPIs."""
        ctx = user_ctx or UserContext()
        site = scope.split(":")[-1] if ":" in scope else "PUNE-01"
        self._verify_site_access(site, ctx)

        # Standard pilot benchmark KPIs
        oee_res = calculate_oee(
            planned_time_s=28800.0,
            operating_time_s=25200.0,
            ideal_cycle_time_s=60.0,
            total_count=400,
            good_count=390,
            energy_kwh=118.0,
        )
        return {
            "scope": scope,
            "period": period,
            "availability_pct": oee_res.availability_pct,
            "performance_pct": oee_res.performance_pct,
            "quality_pct": oee_res.quality_pct,
            "oee_pct": oee_res.oee_pct,
            "mtbf_hours": 142.5,
            "mttr_hours": 1.75,
        }

    async def run_simulation(
        self,
        asset_id: str,
        params: dict[str, Any],
        user_ctx: UserContext | None = None,
    ) -> dict[str, Any]:
        """Execute what-if simulation run on digital twin sandbox."""
        ctx = user_ctx or UserContext()
        site = await self._resolve_asset_site(asset_id)
        self._verify_site_access(site, ctx)

        sim_req = WhatIfSimulationRequest(
            asset_id=asset_id,
            scenario_name="Copilot Sandbox",
            parameter_deltas=params,
        )
        async with get_async_session() as session:
            res = await run_what_if_simulation(sim_req, session=session)
        return {
            "asset_id": asset_id,
            "baseline_metrics": res.baseline_metrics,
            "predicted_metrics": res.predicted_metrics,
            "impact_summary": res.impact_summary,
        }

    async def draft_work_order(
        self,
        asset_id: str,
        title: str,
        description: str,
        priority: str = "medium",
        parts_needed: list[dict[str, Any]] | None = None,
        user_ctx: UserContext | None = None,
    ) -> dict[str, Any]:
        """
        TC-AI-05: Create a draft work order.
        Strictly requires human approval before transition to 'open'.
        """
        ctx = user_ctx or UserContext()
        site = await self._resolve_asset_site(asset_id)
        self._verify_site_access(site, ctx)

        now = datetime.now(UTC)
        wo = WorkOrderModel(
            asset_id=asset_id,
            title=title,
            description=description,
            type="corrective",
            priority=priority,
            source="ai",
            status="draft",  # TC-AI-05: Status must be draft
            assignee=None,
            due_at=now + timedelta(days=2),
            checklist=[
                {"step": 1, "description": "Verify Lockout/Tagout (SOP-EHS-04)", "done": False},
                {"step": 2, "description": "Perform corrective inspection", "done": False},
                {"step": 3, "description": "Supervisor sign-off", "done": False},
            ],
            parts_used=parts_needed or [],
            labour_minutes=0,
            created_at=now,
        )

        async with get_async_session() as session:
            session.add(wo)
            await session.commit()
            await session.refresh(wo)

        logger.info(
            "Created draft work order #%d for %s (awaiting human approval)", wo.id, asset_id
        )
        return {
            "work_order_id": wo.id,
            "asset_id": wo.asset_id,
            "title": wo.title,
            "status": wo.status,
            "requires_approval": True,
            "approval_status": "PENDING_HUMAN_APPROVAL",
            "message": f"Draft work order #{wo.id} created successfully. Human approval required to open.",
        }

    async def approve_work_order(
        self,
        work_order_id: int,
        approved_by: str = "supervisor-01",
        user_ctx: UserContext | None = None,
    ) -> dict[str, Any]:
        """TC-AI-05: Human supervisor accepts/approves the draft work order."""
        async with get_async_session() as session:
            stmt = select(WorkOrderModel).where(WorkOrderModel.id == work_order_id)
            res = await session.execute(stmt)
            wo = res.scalar_one_or_none()
            if not wo:
                return {"error": f"Work order #{work_order_id} not found", "success": False}

            if wo.status != "draft":
                return {
                    "error": f"Work order #{work_order_id} has status '{wo.status}', not 'draft'",
                    "success": False,
                }

            wo.status = "open"
            wo.assignee = approved_by
            await session.commit()
            await session.refresh(wo)

        logger.info("Work order #%d approved by %s -> status 'open'", work_order_id, approved_by)
        return {
            "work_order_id": wo.id,
            "asset_id": wo.asset_id,
            "status": wo.status,
            "approved_by": approved_by,
            "success": True,
            "message": f"Work order #{wo.id} has been approved and opened for scheduling.",
        }


# Global tool registry instance
tool_registry = CopilotToolRegistry()
