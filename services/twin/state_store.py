"""
TwinOps Live Digital Twin In-Memory & Redis State Store.
Maintains instantaneous operational state, derived KPIs, and 3D visual status.
Ref: docs/04_architecture.md §2, docs/05_design_document.md §4
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from services.common.canonical import CanonicalTelemetryMessage
from services.common.twin_templates import get_template
from services.twin.evaluator import TwinEvaluator

logger = logging.getLogger("twinops.twin.state")


class LiveMetricState(BaseModel):
    v: float | int | str | bool
    q: int
    ts: datetime


class LiveAssetTwin(BaseModel):
    asset_id: str
    site: str
    type_id: str
    name: str
    criticality: str = "B"
    lifecycle_state: str = "Operating"
    operational_status: str = "RUNNING"
    status_color: str = "green"  # green, amber, red, grey
    status_reasons: list[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metrics: dict[str, LiveMetricState] = Field(default_factory=dict)
    derived_metrics: dict[str, float] = Field(default_factory=dict)
    position_3d: dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0, "rot_y": 0.0}
    )
    model_3d: str = "models/generic_machine.glb"


class TwinStateStore:
    """
    Central repository for real-time digital twin instances.
    """

    def __init__(self):
        self._twins: dict[str, LiveAssetTwin] = {}
        self._listeners: list[Callable[[LiveAssetTwin], Any]] = []
        self._lock = asyncio.Lock()

    def register_listener(self, callback: Callable[[LiveAssetTwin], Any]):
        """Register a callback (e.g. WebSocket broadcaster) invoked upon twin state change."""
        self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[LiveAssetTwin], Any]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def initialize_from_assets(self, assets: list[dict[str, Any]], site: str = "PUNE-01"):
        """Initialize placeholder twins from asset records."""
        for a in assets:
            aid = a["id"]
            tid = a.get("type_id", "cnc_machine")
            tpl = get_template(tid)
            model_path = tpl.model_3d if tpl else "models/generic_machine.glb"

            self._twins[aid] = LiveAssetTwin(
                asset_id=aid,
                site=site,
                type_id=tid,
                name=a.get("name", aid),
                criticality=a.get("criticality", "B"),
                lifecycle_state=a.get("lifecycle_state", "Operating"),
                operational_status="IDLE",
                status_color="grey",
                position_3d=a.get("position", {"x": 0.0, "y": 0.0, "z": 0.0, "rot_y": 0.0}),
                model_3d=model_path,
                last_updated=datetime.now(UTC),
            )
        logger.info(f"Initialized state store with {len(self._twins)} assets.")

    def get_twin(self, asset_id: str) -> LiveAssetTwin | None:
        return self._twins.get(asset_id)

    def get_all_twins(self, site: str | None = None) -> list[LiveAssetTwin]:
        if site:
            return [t for t in self._twins.values() if t.site == site]
        return list(self._twins.values())

    async def update_from_telemetry(self, msg: CanonicalTelemetryMessage) -> LiveAssetTwin:
        """
        Process incoming canonical telemetry message:
        1. Updates raw metrics map.
        2. Computes derived KPIs.
        3. Evaluates 3D status color (green/amber/red).
        4. Notifies listeners (WebSocket fanout).
        """
        aid = msg.asset_id
        async with self._lock:
            twin = self._twins.get(aid)
            if not twin:
                # Dynamically register unknown asset
                twin = LiveAssetTwin(
                    asset_id=aid,
                    site=msg.site,
                    type_id="cnc_machine",
                    name=aid,
                    last_updated=msg.ts,
                )
                self._twins[aid] = twin

            twin.last_updated = msg.ts
            twin.operational_status = str(msg.status.value)

            # Update raw metrics map
            numeric_metrics: dict[str, float] = {}
            for m_name, mv in msg.metrics.items():
                twin.metrics[m_name] = LiveMetricState(v=mv.v, q=int(mv.q), ts=msg.ts)
                if isinstance(mv.v, (int, float, bool)):
                    numeric_metrics[m_name] = float(mv.v)

            # Evaluate template derived metrics & status color
            template = get_template(twin.type_id)
            if template:
                twin.derived_metrics = TwinEvaluator.evaluate_derived_metrics(
                    template, numeric_metrics
                )
                color, reasons = TwinEvaluator.evaluate_status_color(
                    template, numeric_metrics, twin.operational_status, is_stale=False
                )
                twin.status_color = color
                twin.status_reasons = reasons

        # Notify active WebSocket listeners outside lock
        for cb in self._listeners:
            try:
                res = cb(twin)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning(f"Error invoking twin update listener: {e}")

        return twin

    def check_stale_assets(self, timeout_seconds: float = 15.0) -> list[str]:
        """
        Check for assets that have not received telemetry for > timeout_seconds.
        Marks them as 'grey' (OFFLINE/STALE) per TC-TWN-08.
        """
        now = datetime.now(UTC)
        stale_ids = []

        for twin in self._twins.values():
            delta = (now - twin.last_updated).total_seconds()
            if delta > timeout_seconds and twin.status_color != "grey":
                twin.status_color = "grey"
                twin.status_reasons = [f"No telemetry received for {int(delta)}s"]
                stale_ids.append(twin.asset_id)

        return stale_ids

    # Alias for canonical update
    update_from_canonical = update_from_telemetry

