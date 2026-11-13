"""
TwinOps Digital Twin REST & WebSocket API.
Provides live twin state, what-if simulations, historical playback, and WebSocket fan-out.
Ref: docs/05_design_document.md §4, 5
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.common.database import AssetModel, AssetRelationModel, TelemetryModel, get_db_session
from services.common.twin_templates import get_template
from services.twin.evaluator import TwinEvaluator
from services.twin.state_store import TwinStateStore
from services.twin.websocket_manager import WebSocketManager

logger = logging.getLogger("twinops.twin.api")
router = APIRouter(prefix="/api/v1", tags=["twin"])
ws_router = APIRouter(tags=["twin-ws"])

# Global singletons
state_store = TwinStateStore()
ws_manager = WebSocketManager()

# Hook broadcaster into state store
state_store.register_listener(ws_manager.broadcast_twin_update)


# -------------------------------------------------------------
# Simulation & Playback Models
# -------------------------------------------------------------


class WhatIfSimulationRequest(BaseModel):
    asset_id: str
    scenario_name: str = "Speed and Load Adjustment"
    parameter_deltas: dict[str, float] = Field(
        ..., description="e.g. {'speed_pct': 20.0} or {'power_kw': 14.5} or {'flow_m3h': 48.0}"
    )


class WhatIfSimulationResponse(BaseModel):
    asset_id: str
    scenario_name: str
    baseline_metrics: dict[str, float]
    predicted_metrics: dict[str, float]
    baseline_kpis: dict[str, float]
    predicted_kpis: dict[str, float]
    impact_summary: list[str]


class PlaybackFrame(BaseModel):
    ts: datetime
    metrics: dict[str, float]
    status: str
    status_color: str


class PlaybackResponse(BaseModel):
    asset_id: str
    from_ts: datetime
    to_ts: datetime
    speed_factor: int
    total_frames: int
    frames: list[PlaybackFrame]


# -------------------------------------------------------------
# 1. Live Twin Endpoints
# -------------------------------------------------------------


@router.get("/assets/{asset_id}/twin", response_model=dict[str, Any])
async def get_live_twin(asset_id: str, session: AsyncSession = Depends(get_db_session)):
    """
    GET /api/v1/assets/{id}/twin
    Retrieve current real-time digital twin state with derived KPIs and connected topology.
    """
    twin = state_store.get_twin(asset_id)
    if not twin:
        # Check if asset exists in DB
        db_asset = await session.get(AssetModel, asset_id)
        if not db_asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")
        # Initialize placeholder twin
        state_store.initialize_from_assets(
            [
                {
                    "id": db_asset.id,
                    "name": db_asset.name,
                    "type_id": db_asset.type_id,
                    "criticality": db_asset.criticality,
                    "position": db_asset.position or {},
                    "lifecycle_state": db_asset.lifecycle_state,
                }
            ]
        )
        twin = state_store.get_twin(asset_id)

    # Fetch relations
    rels_query = select(AssetRelationModel).where(
        or_(AssetRelationModel.from_asset == asset_id, AssetRelationModel.to_asset == asset_id)
    )
    rels_res = await session.execute(rels_query)
    rels = [
        {"from_asset": r.from_asset, "to_asset": r.to_asset, "kind": r.kind}
        for r in rels_res.scalars().all()
    ]

    return {
        "asset_id": twin.asset_id,
        "site": twin.site,
        "name": twin.name,
        "type_id": twin.type_id,
        "criticality": twin.criticality,
        "operational_status": twin.operational_status,
        "status_color": twin.status_color,
        "status_reasons": twin.status_reasons,
        "last_updated": twin.last_updated.isoformat(),
        "position_3d": twin.position_3d,
        "model_3d": twin.model_3d,
        "metrics": {
            k: {"v": v.v, "q": v.q, "ts": v.ts.isoformat()} for k, v in twin.metrics.items()
        },
        "derived_metrics": twin.derived_metrics,
        "relationships": rels,
    }


@router.get("/sites/{site_id}/twin", response_model=list[dict[str, Any]])
async def get_site_twin_snapshot(site_id: str, session: AsyncSession = Depends(get_db_session)):
    """
    Retrieve full 3D plant twin snapshot of all assets for scene initialization.
    """
    twins = state_store.get_all_twins(site=site_id)
    if not twins:
        # Load from DB assets
        res = await session.execute(select(AssetModel))
        db_assets = res.scalars().all()
        state_store.initialize_from_assets(
            [
                {
                    "id": a.id,
                    "name": a.name,
                    "type_id": a.type_id,
                    "criticality": a.criticality,
                    "position": a.position or {},
                    "lifecycle_state": a.lifecycle_state,
                }
                for a in db_assets
            ],
            site=site_id,
        )
        twins = state_store.get_all_twins(site=site_id)

    return [
        {
            "asset_id": t.asset_id,
            "name": t.name,
            "type_id": t.type_id,
            "criticality": t.criticality,
            "operational_status": t.operational_status,
            "status_color": t.status_color,
            "position_3d": t.position_3d,
            "model_3d": t.model_3d,
            "last_updated": t.last_updated.isoformat(),
            "metrics": {k: {"v": v.v, "q": v.q} for k, v in t.metrics.items()},
            "derived_metrics": t.derived_metrics,
            "status_reasons": t.status_reasons,
        }
        for t in twins
    ]


# -------------------------------------------------------------
# 2. What-If Simulation Sandbox (TWN-05)
# -------------------------------------------------------------


@router.post("/simulations", response_model=WhatIfSimulationResponse)
async def run_what_if_simulation(
    payload: WhatIfSimulationRequest, session: AsyncSession = Depends(get_db_session)
):
    """
    TWN-05: What-if simulation sandbox.
    Evaluates impact of operational changes (e.g. +20% pump speed, +30% CNC load).
    Predicts resultant temperatures, vibration shifts, and hydraulic/thermal efficiency.
    """
    twin = state_store.get_twin(payload.asset_id)
    if not twin:
        db_asset = await session.get(AssetModel, payload.asset_id)
        if not db_asset:
            raise HTTPException(status_code=404, detail=f"Asset '{payload.asset_id}' not found")
        # Initialize
        state_store.initialize_from_assets([{"id": db_asset.id, "type_id": db_asset.type_id}])
        twin = state_store.get_twin(payload.asset_id)

    template = get_template(twin.type_id)
    if not template:
        raise HTTPException(
            status_code=400, detail=f"No twin template found for asset type '{twin.type_id}'"
        )

    # Baseline numerical metrics
    baseline = {k: float(v.v) for k, v in twin.metrics.items() if isinstance(v.v, (int, float))}
    predicted = dict(baseline)
    deltas = payload.parameter_deltas
    impacts = []

    # Simulation Physics Rules
    if twin.type_id == "centrifugal_pump":
        speed_delta_pct = deltas.get("speed_pct", deltas.get("speed_increase_pct", 0.0))
        if speed_delta_pct != 0.0:
            factor = 1.0 + (speed_delta_pct / 100.0)
            # Affinity Laws: Flow ~ N, Head ~ N^2, Power ~ N^3
            predicted["flow_m3h"] = round(baseline.get("flow_m3h", 40.0) * factor, 2)
            predicted["discharge_bar"] = round(baseline.get("discharge_bar", 5.5) * (factor**2), 2)
            predicted["power_kw"] = round(baseline.get("power_kw", 9.0) * (factor**2.7), 2)
            predicted["motor_temp_c"] = round(
                baseline.get("motor_temp_c", 58.0) + (speed_delta_pct * 0.4), 1
            )
            predicted["vibration_mm_s"] = round(
                baseline.get("vibration_mm_s", 2.1) * (1.0 + (speed_delta_pct * 0.02)), 2
            )
            impacts.append(f"Pump speed changed by {speed_delta_pct:+.1f}%.")
            impacts.append(
                f"Predicted power increase: {predicted['power_kw'] - baseline.get('power_kw', 9.0):+.2f} kW."
            )
            impacts.append(f"Predicted motor temperature: {predicted['motor_temp_c']} °C.")

    elif twin.type_id == "cnc_machine":
        load_delta_pct = deltas.get("load_pct", deltas.get("speed_pct", 0.0))
        if load_delta_pct != 0.0:
            factor = 1.0 + (load_delta_pct / 100.0)
            predicted["power_kw"] = round(baseline.get("power_kw", 12.0) * factor, 2)
            predicted["spindle_temp_c"] = round(
                baseline.get("spindle_temp_c", 45.0) + (load_delta_pct * 0.25), 1
            )
            predicted["vibration_mm_s"] = round(
                baseline.get("vibration_mm_s", 2.2) * (1.0 + (load_delta_pct * 0.015)), 2
            )
            impacts.append(f"Spindle cutting load changed by {load_delta_pct:+.1f}%.")
            impacts.append(
                f"Predicted thermal rise: {predicted['spindle_temp_c'] - baseline.get('spindle_temp_c', 45.0):+.1f} °C."
            )

    # Re-evaluate derived KPIs for both baseline and predicted
    baseline_kpis = TwinEvaluator.evaluate_derived_metrics(template, baseline)
    predicted_kpis = TwinEvaluator.evaluate_derived_metrics(template, predicted)

    return WhatIfSimulationResponse(
        asset_id=payload.asset_id,
        scenario_name=payload.scenario_name,
        baseline_metrics=baseline,
        predicted_metrics=predicted,
        baseline_kpis=baseline_kpis,
        predicted_kpis=predicted_kpis,
        impact_summary=impacts,
    )


# -------------------------------------------------------------
# 3. Historical Playback Scrubber (TWN-04)
# -------------------------------------------------------------


@router.get("/assets/{asset_id}/playback", response_model=PlaybackResponse)
async def get_historical_playback(
    asset_id: str,
    from_ts: datetime = Query(..., alias="from"),
    to_ts: datetime = Query(..., alias="to"),
    speed: int = Query(10, ge=1, le=60, description="Replay speed factor (1x to 60x)"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    TWN-04: Historical digital twin playback scrubber.
    Retrieves time-synchronized frames to visually replay plant conditions at 1x-60x speed.
    """
    db_asset = await session.get(AssetModel, asset_id)
    if not db_asset:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

    template = get_template(db_asset.type_id)

    # Fetch ordered historical points
    q = (
        select(TelemetryModel)
        .where(
            TelemetryModel.asset_id == asset_id,
            TelemetryModel.ts >= from_ts,
            TelemetryModel.ts <= to_ts,
        )
        .order_by(TelemetryModel.ts.asc())
        .limit(2000)
    )
    res = await session.execute(q)
    rows = res.scalars().all()

    # Group into timestamp frames
    frames_map: dict[str, dict[str, Any]] = {}
    for r in rows:
        ts_key = r.ts.isoformat()
        if ts_key not in frames_map:
            frames_map[ts_key] = {"ts": r.ts, "metrics": {}, "status": "RUNNING"}
        frames_map[ts_key]["metrics"][r.metric] = r.value

    frames: list[PlaybackFrame] = []
    for f in frames_map.values():
        mets = f["metrics"]
        color = "green"
        if template:
            color, _ = TwinEvaluator.evaluate_status_color(template, mets, f["status"])
        frames.append(
            PlaybackFrame(ts=f["ts"], metrics=mets, status=f["status"], status_color=color)
        )

    return PlaybackResponse(
        asset_id=asset_id,
        from_ts=from_ts,
        to_ts=to_ts,
        speed_factor=speed,
        total_frames=len(frames),
        frames=frames,
    )


# -------------------------------------------------------------
# 4. Live WebSocket Endpoint (WS /ws/live)
# -------------------------------------------------------------


@ws_router.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket, site: str = Query("PUNE-01")):
    """
    WS /ws/live?site=PUNE-01
    Real-time push channel delivering digital twin state updates (< 2 s latency).
    """
    await ws_manager.connect(websocket, site=site)

    # Immediately send full snapshot to newly connected client
    current_twins = state_store.get_all_twins(site=site)
    await ws_manager.broadcast_full_snapshot(websocket, current_twins)

    try:
        while True:
            # Keep socket alive and handle incoming client commands (e.g. ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, site=site)
    except Exception as e:
        logger.debug(f"WebSocket client error: {e}")
        await ws_manager.disconnect(websocket, site=site)
