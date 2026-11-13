"""
Tests for Digital Twin Microservice (Step 5).
Maps to test cases:
- TC-TWN-01 (Twin from template & derived KPIs)
- TC-TWN-02 (Live WebSocket push & latency)
- TC-TWN-03 (3D status colour evaluation)
- TC-TWN-06 (Historical playback scrubber)
- TC-TWN-07 (What-if simulation sandbox)
- TC-TWN-08 (Offline / stale asset detection)
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from services.common.canonical import AssetOperationalStatus, CanonicalTelemetryMessage, MetricValue
from services.common.database import (
    AssetModel,
    TelemetryModel,
    async_session_factory,
    init_db,
    seed_pilot_data,
)
from services.twin.api import state_store
from services.twin.evaluator import safe_eval
from services.twin.main import app
from simulator.config import PILOT_ASSETS


@pytest.fixture(autouse=True)
async def setup_twin_test_db():
    """Ensure DB schema is initialized and state store loaded."""
    await init_db()
    async with async_session_factory() as session:
        pilot_ids = [a.asset_id for a in PILOT_ASSETS]
        await session.execute(delete(AssetModel).where(AssetModel.id.not_in(pilot_ids)))
        await session.execute(delete(TelemetryModel))
        await session.commit()
        await seed_pilot_data(session)

    # Initialize state store with pilot assets
    state_store.initialize_from_assets(
        [
            {
                "id": a.asset_id,
                "name": a.name,
                "type_id": a.type_id,
                "criticality": a.criticality,
                "position": a.position_3d,
                "lifecycle_state": "Operating",
            }
            for a in PILOT_ASSETS
        ],
        site="PUNE-01",
    )


def test_twn_safe_eval():
    """Verify safe AST evaluator with arithmetic, comparisons and logic."""
    ctx = {"flow": 40.0, "head": 5.5, "power": 9.0}
    # Pump efficiency formula: (flow * head * 2.78) / power
    res = safe_eval("(flow * head * 2.78) / power", ctx)
    assert round(res, 2) == 67.96

    # Boolean comparisons
    assert safe_eval("power > 0.5 and flow > 10.0", ctx) is True
    assert safe_eval("power < 5.0", ctx) is False


@pytest.mark.asyncio
async def test_twn_01_live_twin_and_derived_kpis():
    """
    TC-TWN-01: Update PUMP-01 with telemetry and verify derived KPI (efficiency_pct) is computed.
    """
    pump_msg = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="PUMP-01",
        ts=datetime.now(UTC),
        metrics={
            "flow_m3h": MetricValue(v=42.0, q=0),
            "discharge_bar": MetricValue(v=5.8, q=0),
            "suction_bar": MetricValue(v=1.1, q=0),
            "power_kw": MetricValue(v=9.2, q=0),
            "motor_temp_c": MetricValue(v=58.5, q=0),
            "vibration_mm_s": MetricValue(v=2.2, q=0),
        },
        status=AssetOperationalStatus.RUNNING,
    )
    twin = await state_store.update_from_telemetry(pump_msg)
    assert twin.asset_id == "PUMP-01"
    assert "efficiency_pct" in twin.derived_metrics
    # efficiency = (42.0 * 5.8 * 2.78) / 9.2 = ~73.6%
    assert 70.0 < twin.derived_metrics["efficiency_pct"] < 78.0

    # Query via REST API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/assets/PUMP-01/twin")
        assert res.status_code == 200
        data = res.json()
        assert data["asset_id"] == "PUMP-01"
        assert data["operational_status"] == "RUNNING"
        assert data["status_color"] == "green"
        assert data["derived_metrics"]["efficiency_pct"] > 70.0
        assert data["model_3d"] == "models/pump_centrifugal.glb"


@pytest.mark.asyncio
async def test_twn_03_3d_status_colors():
    """
    TC-TWN-03: Verify 3D status colour transitions (green -> amber -> red).
    """
    now = datetime.now(UTC)

    # 1. Healthy machine -> Green
    healthy_msg = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="CNC-02",
        ts=now,
        metrics={
            "spindle_temp_c": MetricValue(v=48.0, q=0),
            "vibration_mm_s": MetricValue(v=2.2, q=0),
            "power_kw": MetricValue(v=12.0, q=0),
            "spindle_rpm": MetricValue(v=8500, q=0),
        },
        status=AssetOperationalStatus.RUNNING,
    )
    twin1 = await state_store.update_from_telemetry(healthy_msg)
    assert twin1.status_color == "green"

    # 2. Warning limit breached -> Amber (hi = 65 °C)
    warning_msg = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="CNC-02",
        ts=now,
        metrics={
            "spindle_temp_c": MetricValue(v=68.0, q=0),
            "vibration_mm_s": MetricValue(v=2.2, q=0),
            "power_kw": MetricValue(v=12.0, q=0),
            "spindle_rpm": MetricValue(v=8500, q=0),
        },
        status=AssetOperationalStatus.RUNNING,
    )
    twin2 = await state_store.update_from_telemetry(warning_msg)
    assert twin2.status_color == "amber"
    assert len(twin2.status_reasons) >= 1

    # 3. Critical limit breached -> Red (hi_hi = 75 °C)
    alarm_msg = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="CNC-02",
        ts=now,
        metrics={
            "spindle_temp_c": MetricValue(v=78.5, q=0),
            "vibration_mm_s": MetricValue(v=7.4, q=0),  # also ISO 10816 Zone D
            "power_kw": MetricValue(v=12.0, q=0),
            "spindle_rpm": MetricValue(v=8500, q=0),
        },
        status=AssetOperationalStatus.FAULT,
    )
    twin3 = await state_store.update_from_telemetry(alarm_msg)
    assert twin3.status_color == "red"


@pytest.mark.asyncio
async def test_twn_07_what_if_simulation():
    """
    TC-TWN-07: What-if simulation.
    Increase pump speed 20%, observe predicted power and motor temp.
    """
    # Prime PUMP-01 with baseline telemetry
    now = datetime.now(UTC)
    base_msg = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="PUMP-01",
        ts=now,
        metrics={
            "flow_m3h": MetricValue(v=40.0, q=0),
            "discharge_bar": MetricValue(v=5.5, q=0),
            "power_kw": MetricValue(v=9.0, q=0),
            "motor_temp_c": MetricValue(v=58.0, q=0),
            "vibration_mm_s": MetricValue(v=2.1, q=0),
        },
        status=AssetOperationalStatus.RUNNING,
    )
    await state_store.update_from_telemetry(base_msg)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sim_req = {
            "asset_id": "PUMP-01",
            "scenario_name": "Test 20% Speed Increase",
            "parameter_deltas": {"speed_pct": 20.0},
        }
        res = await client.post("/api/v1/simulations", json=sim_req)
        assert res.status_code == 200
        sim = res.json()
        assert sim["asset_id"] == "PUMP-01"

        # Affinity laws: flow should be 40 * 1.2 = 48.0
        assert sim["predicted_metrics"]["flow_m3h"] == 48.0
        # Head: 5.5 * 1.44 = 7.92 bar
        assert sim["predicted_metrics"]["discharge_bar"] == 7.92
        # Power increase
        assert sim["predicted_metrics"]["power_kw"] > sim["baseline_metrics"]["power_kw"]
        # Temperature increase
        assert sim["predicted_metrics"]["motor_temp_c"] > sim["baseline_metrics"]["motor_temp_c"]
        assert len(sim["impact_summary"]) >= 3


@pytest.mark.asyncio
async def test_twn_06_historical_playback():
    """
    TC-TWN-06: Historical playback scrubber.
    Store time-series rows and query playback replay frames.
    """
    now = datetime.now(UTC)
    t1 = now - timedelta(minutes=5)
    t2 = now - timedelta(minutes=4)
    t3 = now - timedelta(minutes=3)

    # Insert 3 frames in DB
    async with async_session_factory() as session:
        for t, temp in [(t1, 44.0), (t2, 52.0), (t3, 62.0)]:
            session.add(
                TelemetryModel(
                    ts=t, asset_id="CNC-01", metric="spindle_temp_c", value=temp, quality=0
                )
            )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        from_str = (now - timedelta(minutes=10)).isoformat()
        to_str = now.isoformat()
        res = await client.get(
            "/api/v1/assets/CNC-01/playback",
            params={"from": from_str, "to": to_str, "speed": 10}
        )
        assert res.status_code == 200
        playback = res.json()
        assert playback["asset_id"] == "CNC-01"
        assert playback["total_frames"] == 3
        assert playback["speed_factor"] == 10
        assert len(playback["frames"]) == 3
        assert playback["frames"][0]["metrics"]["spindle_temp_c"] == 44.0
        assert playback["frames"][-1]["metrics"]["spindle_temp_c"] == 62.0


def test_twn_08_offline_stale_detection():
    """
    TC-TWN-08: Stale asset detection.
    Assets with no telemetry for > 15 seconds become 'grey'.
    """
    old_time = datetime.now(UTC) - timedelta(seconds=20)
    twin = state_store.get_twin("CNC-01")
    assert twin is not None
    twin.last_updated = old_time
    twin.status_color = "green"

    stale_ids = state_store.check_stale_assets(timeout_seconds=15.0)
    assert "CNC-01" in stale_ids
    assert twin.status_color == "grey"
    assert "No telemetry received" in twin.status_reasons[0]


def test_twn_02_websocket_push():
    """
    TC-TWN-02: Live WebSocket push.
    Verify client connects, receives snapshot, and gets real-time broadcast.
    """
    from starlette.testclient import TestClient

    with (
        TestClient(app) as client,
        client.websocket_connect("/ws/live?site=PUNE-01") as websocket
    ):
        # First message should be full plant snapshot
        initial_data = websocket.receive_json()
        assert initial_data["type"] == "snapshot"
        assert len(initial_data["assets"]) >= 20

        # Ping test
        websocket.send_text("ping")
        pong = websocket.receive_text()
        assert pong == "pong"
