"""
Tests for the logistics simulation (docks, trucks, forklifts).
Requirements: LOG-01 (dock & forklift twins), LOG-02 (logistics events), LOG-03 (KPIs).
"""

from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from services.analytics.logistics import LOGISTICS_METRICS, calculate_logistics_kpis
from services.analytics.main import app as analytics_app
from simulator.config import LOGISTICS_POINTS
from simulator.plant import VirtualPlant


def _run(plant: VirtualPlant, seconds: int):
    events = []
    for _ in range(seconds):
        plant.tick(dt=1.0)
        events.extend(plant.pop_events())
    return events


def test_log_01_forklift_and_dock_publish_canonical_telemetry():
    plant = VirtualPlant(site="PUNE-01")
    msgs = {m.asset_id: m for m in plant.tick(dt=1.0)}
    assert set(msgs["FLT-01"].metrics) == {
        "battery_pct", "pos_x_m", "pos_z_m", "heading_deg", "speed_m_s", "load_kg", "pallets_moved"
    }  # fmt: skip
    assert set(msgs["DOCK-RCV"].metrics) == {
        "truck_present", "pallets_pending", "pallets_handled", "truck_dwell_s"
    }  # fmt: skip


def test_log_01_inbound_truck_is_unloaded_to_both_lines():
    plant = VirtualPlant(site="PUNE-01")
    events = _run(plant, 250)  # one truck: second arrives 180 s after the first leaves
    rcv = plant.logistics.docks["DOCK-RCV"]
    assert rcv.pallets_handled == 6 and rcv.pallets_pending == 0 and not rcv.truck_present
    drops = [e.data["to_point"] for e in events if e.event_type == "PALLET_MOVED"]
    assert drops.count("LINE-01-IN") == 3 and drops.count("LINE-02-IN") == 3
    f = plant.logistics.forklifts["FLT-01"]
    assert f.pallets_moved == 6 and f.load_kg == 0 and f.battery < 90


def test_log_01_forklift_stays_inside_building_and_reaches_dock():
    plant = VirtualPlant(site="PUNE-01")
    seen = set()
    for _ in range(120):
        plant.tick(dt=1.0)
        f = plant.logistics.forklifts["FLT-01"]
        assert 0 <= f.x <= 56 and 0 <= f.z <= 36
        seen.add((f.x, f.z))
    assert LOGISTICS_POINTS["DOCK-RCV"] in seen


def test_log_02_truck_events_carry_turnaround():
    plant = VirtualPlant(site="PUNE-01")
    events = _run(plant, 400)
    kinds = [e.event_type for e in events if e.asset_id == "DOCK-RCV"]
    assert kinds[:2] == ["TRUCK_ARRIVED", "TRUCK_DEPARTED"]
    departed = next(e for e in events if e.event_type == "TRUCK_DEPARTED")
    assert departed.data["turnaround_s"] > 0
    moved = next(e for e in events if e.event_type == "PALLET_MOVED")
    assert moved.asset_id == "FLT-01" and moved.data["duration_s"] > 0


def test_log_01_finished_parts_become_outbound_pallets_and_ship():
    plant = VirtualPlant(site="PUNE-01")
    plant.machines["CNC-03"].part_counter += 12  # 6 pallets worth of finished parts
    events = _run(plant, 600)
    shp = plant.logistics.docks["DOCK-SHP"]
    assert shp.pallets_handled >= 6
    assert any(e.asset_id == "DOCK-SHP" and e.event_type == "TRUCK_DEPARTED" for e in events)


def test_log_01_low_battery_forklift_goes_to_charger():
    plant = VirtualPlant(site="PUNE-01")
    f = plant.logistics.forklifts["FLT-02"]
    f.battery = 20.0
    _run(plant, 60)
    assert f.charging or f.battery > 25
    assert (f.x, f.z) == LOGISTICS_POINTS["CHARGER"]


def test_log_03_kpis_from_dock_and_forklift_telemetry():
    plant = VirtualPlant(site="PUNE-01")
    t0, rows = datetime(2026, 11, 13, tzinfo=UTC), []
    for i in range(250):
        for m in plant.tick(dt=1.0):
            for name, mv in m.metrics.items():
                if name in LOGISTICS_METRICS:
                    rows.append((t0 + timedelta(seconds=i), m.asset_id, name, float(mv.v)))
    kpis = calculate_logistics_kpis(rows)
    assert kpis["DOCK-RCV"]["trucks_completed"] == 1
    assert 60 < kpis["DOCK-RCV"]["avg_truck_turnaround_s"] < 240
    assert kpis["DOCK-RCV"]["pallets_handled"] == 6
    assert kpis["FLT-01"]["pallets_moved"] == 6
    assert 5 < kpis["FLT-01"]["avg_carry_time_s"] < 60
    assert 0 < kpis["FLT-01"]["utilisation_pct"] <= 100


async def test_log_03_kpi_endpoint():
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://t") as c:
        res = await c.get("/api/v1/analytics/logistics/kpis?hours=1")
    assert res.status_code == 200 and "assets" in res.json()
