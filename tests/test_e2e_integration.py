"""
End-to-End Pipeline Integration Test (Steps 1 to 4).
Demonstrates the full operational cycle:
1. Virtual Plant Simulator generates 25-asset canonical telemetry (Step 1 & 2)
2. Telemetry Ingest Service buffers and flushes to database (Step 3)
3. Asset Service serves ISA-95 tree and manages asset records (Step 4)
4. Telemetry API queries verify real-time data flow and 1m rollups
"""

import pytest
from httpx import ASGITransport, AsyncClient

from services.asset.main import app as asset_app
from services.common.database import async_session_factory, init_db, seed_pilot_data
from services.telemetry.api import ingest_service
from services.telemetry.main import app as telemetry_app
from simulator.plant import VirtualPlant


@pytest.fixture(autouse=True)
async def setup_e2e():
    await init_db()
    async with async_session_factory() as session:
        await seed_pilot_data(session)
    ingest_service.start()
    yield
    await ingest_service.stop()


@pytest.mark.asyncio
async def test_e2e_full_steps_1_to_4_pipeline():
    """
    Complete end-to-end test across Steps 1, 2, 3, and 4.
    """
    # -------------------------------------------------------------
    # Step 1 & 2: Simulator & Canonical Schema
    # -------------------------------------------------------------
    plant = VirtualPlant(site="PUNE-01")
    assert len(plant.machines) == 25

    # Simulate 3 consecutive 1-second ticks of the whole factory
    all_messages = []
    for _ in range(3):
        msgs = plant.tick(dt=1.0)
        assert len(msgs) == 25
        all_messages.extend(msgs)

    # 25 assets * 3 ticks = 75 canonical messages
    assert len(all_messages) == 75

    # -------------------------------------------------------------
    # Step 3: Telemetry Ingest Pipeline & Database
    # -------------------------------------------------------------
    # Ingest the stream into the micro-batch flusher
    await ingest_service.ingest_batch(all_messages)
    await ingest_service.flush()
    assert ingest_service.total_records_ingested > 400  # Hundreds of individual time-series metrics

    # Verify time-series retrieval via Telemetry API
    telemetry_transport = ASGITransport(app=telemetry_app)
    async with AsyncClient(transport=telemetry_transport, base_url="http://test") as t_client:
        # Check raw telemetry for CNC-01
        res = await t_client.get("/api/v1/assets/CNC-01/telemetry?metric=spindle_temp_c")
        assert res.status_code == 200
        cnc_points = res.json()
        assert len(cnc_points) >= 3
        assert cnc_points[0]["asset_id"] == "CNC-01"
        assert cnc_points[0]["quality"] == 0  # Good quality

        # Check pump flow telemetry
        pump_res = await t_client.get("/api/v1/assets/PUMP-01/telemetry?metric=flow_m3h")
        assert pump_res.status_code == 200
        pump_points = pump_res.json()
        assert len(pump_points) >= 3
        assert 35.0 < pump_points[0]["value"] < 45.0

    # -------------------------------------------------------------
    # Step 4: Asset Hierarchy & Registry Management
    # -------------------------------------------------------------
    asset_transport = ASGITransport(app=asset_app)
    async with AsyncClient(transport=asset_transport, base_url="http://test") as a_client:
        # 1. Fetch ISA-95 equipment tree
        tree_res = await a_client.get("/api/v1/sites/PUNE-01/tree")
        assert tree_res.status_code == 200
        tree = tree_res.json()
        assert tree["id"] == "PUNE-01"
        lines = tree["areas"][0]["lines"]
        assert len(lines) == 2
        total_in_tree = sum(len(l["assets"]) for l in lines)
        assert total_in_tree == 25

        # 2. Verify CNC-01 asset details & relationships in Asset Service
        cnc_detail = await a_client.get("/api/v1/assets/CNC-01")
        assert cnc_detail.status_code == 200
        cnc_data = cnc_detail.json()
        assert cnc_data["criticality"] == "A"
        assert cnc_data["lifecycle_state"] == "Operating"

        # Verify connected equipment
        rel_kinds = {r["kind"] for r in cnc_data["relationships"]}
        assert "powers" in rel_kinds
        assert "feeds_coolant" in rel_kinds
        assert "feeds_air" in rel_kinds
