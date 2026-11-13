"""
Tests for Database Schema, Telemetry Ingestion Pipeline, and REST API.
Maps to requirements:
- AST-01 (ISA-95 hierarchy & asset database records)
- CON-06 (Canonical telemetry ingestion and quality code persistence)
- PLT-03 (REST API time-series endpoints)
- ANL-05 (Time-series rollups and aggregations)
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from services.common.canonical import (
    AssetOperationalStatus,
    CanonicalTelemetryMessage,
    DataQuality,
    MetricValue,
)
from services.common.database import (
    AssetModel,
    AssetRelationModel,
    LineModel,
    SiteModel,
    TelemetryModel,
    async_session_factory,
    init_db,
    seed_pilot_data,
)
from services.telemetry.api import ingest_service
from services.telemetry.main import app
from simulator.plant import VirtualPlant


@pytest.fixture(autouse=True)
async def setup_test_database():
    """Ensure DB schema is initialized and telemetry is cleared before each test."""
    await init_db()
    async with async_session_factory() as session:
        from simulator.config import PILOT_ASSETS

        pilot_ids = [a.asset_id for a in PILOT_ASSETS]
        await session.execute(delete(AssetModel).where(AssetModel.id.not_in(pilot_ids)))
        await session.execute(delete(TelemetryModel))
        await session.commit()
        await seed_pilot_data(session)
    ingest_service.start()
    yield
    await ingest_service.stop()


@pytest.mark.asyncio
async def test_ast_01_database_seed_and_hierarchy():
    """
    AST-01: Verify ISA-95 hierarchy tables in DB.
    Enterprise -> Site (PUNE-01) -> Area -> Line -> Assets (29 assets)
    """
    async with async_session_factory() as session:
        # Check site
        site = await session.get(SiteModel, "PUNE-01")
        assert site is not None
        assert "Pune" in site.name
        assert site.timezone == "Asia/Kolkata"

        # Check lines
        lines_res = await session.execute(select(LineModel))
        lines = lines_res.scalars().all()
        assert len(lines) == 3  # 2 machining lines + logistics
        line_ids = {l.id for l in lines}
        assert "LINE-01" in line_ids and "LINE-02" in line_ids

        # Check all 29 assets
        assets_res = await session.execute(select(AssetModel))
        assets = assets_res.scalars().all()
        assert len(assets) == 29

        # Check CNC-01 details
        cnc1 = await session.get(AssetModel, "CNC-01")
        assert cnc1 is not None
        assert cnc1.criticality == "A"
        assert cnc1.type_id == "cnc_machine"
        assert cnc1.position["x"] == 16.0

        # Check relationships
        rels_res = await session.execute(select(AssetRelationModel))
        rels = rels_res.scalars().all()
        assert len(rels) >= 20


@pytest.mark.asyncio
async def test_con_06_ingest_canonical_telemetry():
    """
    CON-06: Ingest canonical telemetry from the plant simulator,
    verify batch unpacking into database, and verify quality preservation.
    """
    plant = VirtualPlant(site="PUNE-01")
    # Generate 1 tick across all 29 assets
    messages = plant.tick(dt=1.0)
    assert len(messages) == 29

    # Ingest through TelemetryIngestService
    await ingest_service.ingest_batch(messages)
    flushed_count = await ingest_service.flush()
    assert flushed_count > 100  # 25 assets * multiple metrics each

    # Query DB to verify rows exist
    async with async_session_factory() as session:
        count_res = await session.execute(select(func.count(TelemetryModel.id)))
        total_in_db = count_res.scalar()
        assert total_in_db >= flushed_count

        # Check specific CNC-01 spindle temperature point
        point_res = await session.execute(
            select(TelemetryModel)
            .where(TelemetryModel.asset_id == "CNC-01", TelemetryModel.metric == "spindle_temp_c")
            .limit(1)
        )
        point = point_res.scalar_one_or_none()
        assert point is not None
        assert 30.0 < point.value < 90.0
        assert point.quality == DataQuality.GOOD


@pytest.mark.asyncio
async def test_plt_03_telemetry_rest_api_raw_query():
    """
    PLT-03: Verify REST API GET /api/v1/assets/{asset_id}/telemetry.
    """
    # Ingest test message
    test_msg = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="PUMP-01",
        ts=datetime.now(UTC),
        metrics={"flow_m3h": MetricValue(v=41.5, q=0), "discharge_bar": MetricValue(v=5.6, q=0)},
        status=AssetOperationalStatus.RUNNING,
    )
    await ingest_service.ingest_message(test_msg)
    await ingest_service.flush()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Query raw telemetry for PUMP-01
        res = await client.get("/api/v1/assets/PUMP-01/telemetry?metric=flow_m3h")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        assert data[-1]["asset_id"] == "PUMP-01"
        assert data[-1]["metric"] == "flow_m3h"
        assert data[-1]["value"] == 41.5
        assert data[-1]["quality"] == 0


@pytest.mark.asyncio
async def test_anl_05_telemetry_rest_api_1m_aggregates():
    """
    ANL-05: Verify 1-minute aggregation rollup (avg, min, max, count).
    """
    now = datetime.now(UTC)
    # Ingest 3 distinct points for CNC-06 with a specific metric
    for v in [50.0, 60.0, 70.0]:
        msg = CanonicalTelemetryMessage(
            v=1,
            site="PUNE-01",
            asset_id="CNC-06",
            ts=now,
            metrics={"custom_test_temp_c": MetricValue(v=v, q=0)},
            status=AssetOperationalStatus.RUNNING,
        )
        await ingest_service.ingest_message(msg)
    await ingest_service.flush()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/assets/CNC-06/telemetry?metric=custom_test_temp_c&agg=1m")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        agg_point = data[0]
        assert agg_point["asset_id"] == "CNC-06"
        assert agg_point["metric"] == "custom_test_temp_c"
        assert agg_point["avg"] == 60.0
        assert agg_point["min"] == 50.0
        assert agg_point["max"] == 70.0
        assert agg_point["count"] == 3


@pytest.mark.asyncio
async def test_plt_03_http_batch_ingest_endpoint():
    """
    PLT-03: Verify POST /api/v1/telemetry/ingest endpoint.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = [
            {
                "v": 1,
                "site": "PUNE-01",
                "asset_id": "CHILLER-01",
                "ts": datetime.now(UTC).isoformat(),
                "metrics": {
                    "chilled_water_outlet_c": {"v": 8.2, "q": 0},
                    "compressor_power_kw": {"v": 21.8, "q": 0},
                },
                "status": "RUNNING",
            }
        ]
        res = await client.post("/api/v1/telemetry/ingest", json=payload)
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "accepted"
        assert data["records_received"] == 1
