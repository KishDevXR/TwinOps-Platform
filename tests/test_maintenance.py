"""
TwinOps Step 8 Test Suite: Maintenance / CMMS Service
Verifies:
- TC-MNT-01: Work order lifecycle (Create, assign, start, complete, close + MTTR)
- TC-MNT-02: Checklist and parts (Inventory reduction + checklist saved)
- TC-MNT-03: Calendar PM (30-day plan generates work order)
- TC-MNT-04: Meter PM (500 run-hours generates greasing work order)
- TC-MNT-05: Condition-based maintenance (Vibration > 7.1 mm/s generates corrective work order)
- TC-MNT-06: Spare parts inventory reorder alert (Stock <= reorder_level)
- TC-MNT-07: Mobile offline synchronization
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from services.common.database import (
    PMPlanModel,
    SparePartModel,
    WorkOrderModel,
    get_async_session,
    init_db,
    seed_pilot_data,
)
from services.maintenance.main import app
from services.maintenance.service import maintenance_service


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    async with get_async_session() as session:
        # Reset work orders, parts, and PM plans for pristine test isolation
        await session.execute(delete(WorkOrderModel))
        await session.execute(delete(SparePartModel))
        await session.execute(delete(PMPlanModel))
        await session.commit()
        await seed_pilot_data(session)
    maintenance_service.reorder_alerts.clear()
    yield


@pytest.mark.asyncio
async def test_mnt_01_work_order_lifecycle_and_mttr():
    """
    TC-MNT-01: Work order lifecycle
    Steps: Create, assign, start, complete, close
    Expected result: All states recorded with times; MTTR updates
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create work order
        res_create = await client.post(
            "/api/v1/work-orders",
            json={
                "asset_id": "CNC-01",
                "title": "Spindle Vibration Inspection",
                "description": "Routine diagnostic on CNC-01 spindle bearing",
                "type": "corrective",
                "priority": "high",
            },
        )
        assert res_create.status_code == 201
        wo_id = res_create.json()["id"]
        assert res_create.json()["status"] == "open"

        # 2. Assign to technician
        res_assign = await client.post(
            f"/api/v1/work-orders/{wo_id}/assign",
            json={"assignee": "TECH-MECH-07"},
        )
        assert res_assign.status_code == 200
        assert res_assign.json()["status"] == "assigned"
        assert res_assign.json()["assignee"] == "TECH-MECH-07"

        # 3. Start work order (transitions to in_progress)
        res_start = await client.post(f"/api/v1/work-orders/{wo_id}/start")
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "in_progress"
        assert res_start.json()["started_at"] is not None

        # 4. Complete work order
        res_comp = await client.post(
            f"/api/v1/work-orders/{wo_id}/complete",
            json={
                "checklist": [{"task": "Check runout", "completed": True}],
                "labour_minutes": 90,
            },
        )
        assert res_comp.status_code == 200
        assert res_comp.json()["status"] == "completed"
        assert res_comp.json()["completed_at"] is not None

        # 5. Close work order
        res_close = await client.post(f"/api/v1/work-orders/{wo_id}/close")
        assert res_close.status_code == 200
        assert res_close.json()["status"] == "closed"
        assert res_close.json()["closed_at"] is not None

        # 6. Check metrics (MTTR calculation)
        res_metrics = await client.get("/api/v1/maintenance/metrics")
        assert res_metrics.status_code == 200
        metrics = res_metrics.json()
        assert "mttr_hours" in metrics
        assert metrics["orders_by_type"].get("corrective") == 1


@pytest.mark.asyncio
async def test_mnt_02_checklist_and_parts_deduction():
    """
    TC-MNT-02: Checklist and parts
    Steps: Complete a checklist and use 2 bearings (BRG-6205)
    Expected result: Inventory reduced by 2; checklist saved
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check initial inventory of BRG-6205 (seeded with 10)
        res_parts_before = await client.get("/api/v1/parts")
        bearing_before = next(p for p in res_parts_before.json() if p["code"] == "BRG-6205")
        initial_qty = bearing_before["qty"]
        assert initial_qty >= 10

        # Create work order
        res_wo = await client.post(
            "/api/v1/work-orders",
            json={
                "asset_id": "PUMP-01",
                "title": "Pump Bearing Replacement",
                "type": "corrective",
            },
        )
        wo_id = res_wo.json()["id"]

        # Complete work order and consume 2 bearings
        completed_checklist = [
            {"task": "Lockout Tagout pump motor", "completed": True},
            {"task": "Remove drive-end bearing bracket", "completed": True},
            {"task": "Fit new 6205 bearings with induction heater", "completed": True},
        ]
        parts_consumed = [{"code": "BRG-6205", "qty": 2}]

        res_complete = await client.post(
            f"/api/v1/work-orders/{wo_id}/complete",
            json={
                "checklist": completed_checklist,
                "parts_used": parts_consumed,
                "labour_minutes": 120,
            },
        )
        assert res_complete.status_code == 200

        # Verify inventory reduced by exactly 2
        res_parts_after = await client.get("/api/v1/parts")
        bearing_after = next(p for p in res_parts_after.json() if p["code"] == "BRG-6205")
        assert bearing_after["qty"] == initial_qty - 2

        # Verify checklist saved on work order
        res_wo_get = await client.get(f"/api/v1/work-orders/{wo_id}")
        saved_checklist = res_wo_get.json()["checklist"]
        assert len(saved_checklist) == 3
        assert saved_checklist[0]["task"] == "Lockout Tagout pump motor"


@pytest.mark.asyncio
async def test_mnt_03_calendar_pm():
    """
    TC-MNT-03: Calendar PM
    Steps: 30-day plan with last_done 30 days ago
    Expected result: Work order created automatically today
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Trigger evaluation of calendar PM plans
        res = await client.post("/api/v1/pm-plans/evaluate-calendar")
        assert res.status_code == 200
        created = res.json()["created_work_orders"]

        # CNC Monthly PM was seeded with last_done 30 days ago -> Should trigger!
        assert len(created) >= 1
        pm_order = next(wo for wo in created if "PM: CNC Monthly" in wo["title"])
        assert pm_order["asset_id"] == "CNC-01"

        # Verify work order in DB
        res_wo = await client.get(f"/api/v1/work-orders/{pm_order['id']}")
        wo_data = res_wo.json()
        assert wo_data["type"] == "preventive"
        assert wo_data["source"] == "pm"
        assert wo_data["status"] == "open"
        assert len(wo_data["checklist"]) >= 4


@pytest.mark.asyncio
async def test_mnt_04_meter_pm():
    """
    TC-MNT-04: Meter PM
    Steps: Pump reaches 500 run-hours
    Expected result: Greasing work order created
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Trigger meter PM evaluation with 520 run hours (interval is 500h)
        res = await client.post("/api/v1/pm-plans/evaluate-meter?asset_id=PUMP-01&run_hours=520.0")
        assert res.status_code == 200
        created = res.json()["created_work_orders"]

        assert len(created) == 1
        greasing_wo = created[0]
        assert "Pump 500-Hour" in greasing_wo["title"]
        assert greasing_wo["asset_id"] == "PUMP-01"

        # Verify details
        res_detail = await client.get(f"/api/v1/work-orders/{greasing_wo['id']}")
        detail = res_detail.json()
        assert detail["priority"] == "high"
        assert detail["type"] == "preventive"
        assert "520.0h" in detail["description"]


@pytest.mark.asyncio
async def test_mnt_05_condition_based_maintenance():
    """
    TC-MNT-05: Condition-based maintenance
    Steps: Vibration > 7.1 mm/s for 10 min
    Expected result: Alarm and linked corrective work order created
    """
    wo = await maintenance_service.trigger_condition_based_maintenance(
        asset_id="PUMP-01",
        alarm_id=108,
        metric="vibration_mm_s",
        value=7.84,
        condition_message="Severe vibration peak (7.84 mm/s) sustained for 10 min",
    )
    assert wo.id is not None
    assert wo.asset_id == "PUMP-01"
    assert wo.priority == "critical"
    assert wo.type == "corrective"
    assert wo.source == "alarm"
    assert "7.84" in wo.description
    assert len(wo.checklist) >= 4


@pytest.mark.asyncio
async def test_mnt_06_spare_parts_reorder_alert():
    """
    TC-MNT-06: Reorder
    Steps: Stock falls below the reorder level
    Expected result: Reorder alert sent
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Air filter element FLT-AIR-01 was seeded with qty=4, reorder_level=2
        # Consume 3 filters -> Remaining qty = 1 (< reorder_level 2)
        res_consume = await client.post(
            "/api/v1/parts/FLT-AIR-01/consume",
            json={"qty": 3},
        )
        assert res_consume.status_code == 200
        assert res_consume.json()["remaining_qty"] == 1

        # Use complete_work_order which checks reorder threshold
        res_wo = await client.post(
            "/api/v1/work-orders",
            json={"asset_id": "AHU-01", "title": "Filter Replacement"},
        )
        wo_id = res_wo.json()["id"]

        await client.post(
            f"/api/v1/work-orders/{wo_id}/complete",
            json={"parts_used": [{"code": "FLT-AIR-01", "qty": 1}]},
        )

        # Check reorder alerts endpoint
        res_alerts = await client.get("/api/v1/parts/reorder-alerts")
        assert res_alerts.status_code == 200
        alerts = res_alerts.json()
        assert len(alerts) >= 1
        filter_alert = next(a for a in alerts if a["code"] == "FLT-AIR-01")
        assert filter_alert["current_qty"] <= 1
        assert filter_alert["reorder_level"] == 2


@pytest.mark.asyncio
async def test_mnt_07_mobile_offline_sync():
    """
    TC-MNT-07: Mobile offline
    Steps: Technician completes a job with no network, syncs when online
    Expected result: Syncs when online; no data lost
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create work order
        res_create = await client.post(
            "/api/v1/work-orders",
            json={
                "asset_id": "ROBOT-01",
                "title": "Robot Joint 3 Lubrication",
                "type": "preventive",
            },
        )
        wo_id = res_create.json()["id"]

        # 2. Technician completes job offline on mobile PWA
        offline_batch = [
            {
                "work_order_id": wo_id,
                "status": "completed",
                "started_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "checklist": [
                    {"task": "Purge old grease from gearbox", "completed": True},
                    {"task": "Inject Mobilux EP2 grease", "completed": True},
                ],
                "parts_used": [{"code": "OIL-ISO46", "qty": 5}],
                "labour_minutes": 110,
            }
        ]

        # 3. Mobile connects back to factory Wi-Fi and syncs
        res_sync = await client.post(
            "/api/v1/work-orders/sync",
            json={"batch": offline_batch},
        )
        assert res_sync.status_code == 200
        assert res_sync.json()["status"] == "synchronized"
        assert res_sync.json()["synced_count"] == 1

        # 4. Verify work order on server matches offline data without data loss
        res_get = await client.get(f"/api/v1/work-orders/{wo_id}")
        assert res_get.status_code == 200
        synced_wo = res_get.json()
        assert synced_wo["status"] == "completed"
        assert synced_wo["labour_minutes"] == 110
        assert len(synced_wo["checklist"]) == 2
        assert synced_wo["parts_used"][0]["qty"] == 5
