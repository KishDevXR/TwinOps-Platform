"""
Tests for Asset Hierarchy and Registry Microservice.
Maps to requirements:
- AST-01 (ISA-95 hierarchy tree)
- AST-02 (Asset master records)
- AST-03 (Asset lifecycle states)
- AST-04 (Bulk asset onboarding / Excel/CSV import)
- CON-03 (Bulk tag mapping CSV import)
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from services.asset.main import app
from services.common.database import (
    AssetModel,
    AuditLogModel,
    TagModel,
    async_session_factory,
    init_db,
    seed_pilot_data,
)


@pytest.fixture(autouse=True)
async def setup_test_database():
    """Ensure DB schema is initialized and clean pilot baseline before each test."""
    await init_db()
    async with async_session_factory() as session:
        from simulator.config import PILOT_ASSETS

        pilot_ids = [a.asset_id for a in PILOT_ASSETS]
        await session.execute(delete(AssetModel).where(AssetModel.id.not_in(pilot_ids)))
        await session.execute(delete(TagModel))
        await session.commit()
        await seed_pilot_data(session)
    yield


@pytest.mark.asyncio
async def test_ast_01_site_tree_hierarchy():
    """
    TC-AST-01: Verify GET /api/v1/sites/{site_id}/tree returns full ISA-95 tree.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/sites/PUNE-01/tree")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "PUNE-01"
        assert len(data["areas"]) == 2  # machining + logistics

        area = next(a for a in data["areas"] if a["id"] == "AREA-MACHINING")
        assert area["id"] == "AREA-MACHINING"
        assert len(area["lines"]) == 2

        line1 = next(l for l in area["lines"] if l["id"] == "LINE-01")
        line2 = next(l for l in area["lines"] if l["id"] == "LINE-02")

        # Line 1: 12 assets, Line 2: 13 assets = 25 machines (logistics area holds 4 more)
        total_assets = len(line1["assets"]) + len(line2["assets"])
        assert total_assets == 25

        # Check CNC-01 in Line 1
        cnc1 = next(a for a in line1["assets"] if a["id"] == "CNC-01")
        assert cnc1["type_id"] == "cnc_machine"
        assert cnc1["criticality"] == "A"
        assert cnc1["position"]["x"] == 16.0


@pytest.mark.asyncio
async def test_ast_02_asset_crud_and_lifecycle():
    """
    TC-AST-02 / TC-AST-03: Create, retrieve, update lifecycle state, and delete asset.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create asset
        new_asset = {
            "id": "CNC-TEST-99",
            "name": "CNC Test Machine 99",
            "line_id": "LINE-01",
            "type_id": "cnc_machine",
            "make": "DMG Mori",
            "model": "NLX 2500",
            "criticality": "A",
            "lifecycle_state": "Installed",
            "position": {"x": 25.0, "y": 0.0, "z": 5.0, "rot_y": 0.0},
            "properties": {"controller": "Siemens 840D"},
        }
        res = await client.post("/api/v1/assets", json=new_asset)
        assert res.status_code == 201
        created = res.json()
        assert created["id"] == "CNC-TEST-99"
        assert created["lifecycle_state"] == "Installed"

        # 2. Get asset by ID
        get_res = await client.get("/api/v1/assets/CNC-TEST-99")
        assert get_res.status_code == 200
        assert get_res.json()["make"] == "DMG Mori"

        # 3. Update lifecycle state to Under Maintenance
        patch_res = await client.patch(
            "/api/v1/assets/CNC-TEST-99", json={"lifecycle_state": "Under Maintenance"}
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["lifecycle_state"] == "Under Maintenance"

        # 4. Verify audit log entry was generated
        async with async_session_factory() as session:
            audit_res = await session.execute(
                select(AuditLogModel).where(AuditLogModel.entity_id == "CNC-TEST-99")
            )
            logs = audit_res.scalars().all()
            assert len(logs) >= 2  # CREATE and UPDATE
            actions = [l.action for l in logs]
            assert "CREATE" in actions and "UPDATE" in actions

        # 5. Delete asset
        del_res = await client.delete("/api/v1/assets/CNC-TEST-99")
        assert del_res.status_code == 204

        # 6. Verify deletion
        not_found = await client.get("/api/v1/assets/CNC-TEST-99")
        assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_ast_04_bulk_asset_csv_import():
    """
    TC-AST-04: Bulk onboard assets via CSV upload.
    Target onboarding time < 30 minutes.
    """
    csv_content = (
        "id,name,line_id,type_id,make,model,serial_no,criticality,lifecycle_state\n"
        "CNC-CSV-01,CSV Imported CNC 1,LINE-01,cnc_machine,Doosan,DNM 5700,SN-001,A,Operating\n"
        "PUMP-CSV-01,CSV Imported Pump 1,LINE-02,centrifugal_pump,Kirloskar,DB 50,SN-002,B,Operating\n"
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("assets_onboarding.csv", csv_content.encode("utf-8"), "text/csv")}
        res = await client.post("/api/v1/assets/import", files=files)
        assert res.status_code == 200
        result = res.json()
        assert result["total_processed"] == 2
        assert result["created_count"] == 2
        assert len(result["errors"]) == 0

        # Verify asset was created in database
        check_res = await client.get("/api/v1/assets/CNC-CSV-01")
        assert check_res.status_code == 200
        assert check_res.json()["make"] == "Doosan"


@pytest.mark.asyncio
async def test_con_03_bulk_tag_csv_import():
    """
    TC-CON-03: Bulk import tag mappings from CSV.
    """
    csv_content = (
        "asset_id,metric,unit,source_protocol,source_address,scan_ms,lo,hi\n"
        "CNC-01,spindle_temp_c,°C,opcua,ns=2;s=Line1.CNC01.SpindleTemp,1000,20.0,65.0\n"
        "CNC-01,vibration_mm_s,mm/s,opcua,ns=2;s=Line1.CNC01.Vibration,500,0.5,4.5\n"
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("tags_mapping.csv", csv_content.encode("utf-8"), "text/csv")}
        res = await client.post("/api/v1/tags/import", files=files)
        assert res.status_code == 200
        result = res.json()
        assert result["total_processed"] == 2
        assert result["created_count"] == 2
        assert len(result["errors"]) == 0

        # Verify tags appear on CNC-01 asset record
        cnc_res = await client.get("/api/v1/assets/CNC-01")
        assert cnc_res.status_code == 200
        tags = cnc_res.json()["tags"]
        metric_names = [t["metric"] for t in tags]
        assert "spindle_temp_c" in metric_names
        assert "vibration_mm_s" in metric_names


@pytest.mark.asyncio
async def test_ast_05_asset_relationships_graph():
    """
    TC-AST-05: Verify asset relationship topology (feeds, powers, part_of).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check CNC-01 relationships: fed parts from CONV-01, coolant from PUMP-01, air from COMP-01
        res = await client.get("/api/v1/assets/CNC-01")
        assert res.status_code == 200
        rels = res.json()["relationships"]
        assert len(rels) >= 3

        # Add new custom relationship: CNC-01 feeds inspection robot
        new_rel = {"from_asset": "CNC-01", "to_asset": "ROBOT-02", "kind": "feeds_subassembly"}
        add_res = await client.post("/api/v1/assets/CNC-01/relationships", json=new_rel)
        assert add_res.status_code == 201

        # Verify link is present
        verify_res = await client.get("/api/v1/assets/CNC-01")
        updated_rels = verify_res.json()["relationships"]
        kinds = [r["kind"] for r in updated_rels]
        assert "feeds_subassembly" in kinds

        # Delete relationship
        del_res = await client.delete(
            "/api/v1/assets/CNC-01/relationships?target_asset=ROBOT-02&kind=feeds_subassembly"
        )
        assert del_res.status_code == 204
