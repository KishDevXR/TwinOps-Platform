"""
Tests for open-dataset replay (SIM-01). Uses tiny files in the datasets' real formats,
so the suite never needs the downloads.
"""

from pathlib import Path

import pytest

from services.common.canonical import AssetOperationalStatus
from simulator.plant import VirtualPlant

AI4I_HEAD = (
    "UDI,Product ID,Type,Air temperature [K],Process temperature [K],Rotational speed [rpm],"
    "Torque [Nm],Tool wear [min],Machine failure,TWF,HDF,PWF,OSF,RNF\n"
)
AI4I_ROWS = (
    "1,M1,M,298.1,308.6,1539,40.0,7,0,0,0,0,0,0\n" * 3
    + "2,L2,L,298.2,309.0,1400,60.0,215,1,1,0,0,0,0\n"
) * 2500
METRO_HEAD = (
    ",timestamp,TP2,TP3,H1,DV_pressure,Reservoirs,Oil_temperature,Motor_current,COMP,"
    "DV_eletric,Towers,MPG,LPS,Pressure_switch,Oil_level,Caudal_impulses\n"
)
METRO_ROW = "0,2020-02-01 00:00:00,0,9.0,9,0,9,61.5,{amps},1,0,1,1,0,1,1,1\n"


@pytest.fixture
def replay_dir(tmp_path: Path) -> Path:
    (tmp_path / "ai4i").mkdir()
    (tmp_path / "ai4i" / "ai4i2020.csv").write_text(AI4I_HEAD + AI4I_ROWS, encoding="utf-8-sig")
    (tmp_path / "metropt3").mkdir()
    (tmp_path / "metropt3" / "MetroPT3(AirCompressor).csv").write_text(
        METRO_HEAD + (METRO_ROW.format(amps=6.0) + METRO_ROW.format(amps=0.04)) * 60000,
        encoding="utf-8",
    )
    hyd = tmp_path / "hydraulic"
    hyd.mkdir()
    for name, n, val in (("TS1", 60, 41.5), ("VS1", 60, 0.6), ("PS1", 6000, 160.0),
                         ("FS1", 600, 8.0), ("EPS1", 6000, 2500.0)):  # fmt: skip
        (hyd / f"{name}.txt").write_text(("\t".join([str(val)] * n) + "\n") * 2000)
    return tmp_path


def test_sim_01_cnc_replays_ai4i_scaled_to_nominal(replay_dir):
    plant = VirtualPlant(replay_dir=replay_dir)
    m = {x.asset_id: x for x in plant.tick(dt=1.0)}["CNC-01"].metrics
    assert m["spindle_rpm"].v == 8500.0  # dataset mean rpm -> asset nominal rpm
    assert m["power_kw"].v == 12.5
    assert m["spindle_temp_c"].v == pytest.approx(35.45)  # 308.6 K
    assert m["tool_wear_min"].v == 7.0


def test_sim_01_ai4i_failure_row_becomes_fault_status(replay_dir):
    plant = VirtualPlant(replay_dir=replay_dir)
    statuses = set()
    for _ in range(4):  # 4 parts, one row held per 60 s machining cycle
        statuses.add({x.asset_id: x for x in plant.tick(dt=60.0)}["CNC-01"].status)
    assert AssetOperationalStatus.FAULT in statuses


def test_sim_01_compressor_and_pump_replay(replay_dir):
    plant = VirtualPlant(replay_dir=replay_dir)
    msgs = {x.asset_id: x for x in plant.tick(dt=1.0)}
    comp = msgs["COMP-01"]
    assert comp.metrics["discharge_pressure_bar"].v == 7.4  # 9 bar typical -> nominal
    assert comp.metrics["discharge_temp_c"].v == 61.5
    assert comp.status == AssetOperationalStatus.RUNNING
    msgs = {x.asset_id: x for x in plant.tick(dt=10.0)}  # next row: unloaded
    assert msgs["COMP-01"].status == AssetOperationalStatus.IDLE
    pump = msgs["PUMP-01"].metrics
    assert pump["motor_temp_c"].v == 41.5 and pump["vibration_mm_s"].v == 0.6
    assert pump["discharge_bar"].v == 5.8 and pump["flow_m3h"].v == 42.0


def test_sim_01_injected_fault_overrides_replay_and_default_is_synthetic(replay_dir):
    plant = VirtualPlant(replay_dir=replay_dir)
    plant.inject_fault("CNC-01", "overheat")
    for _ in range(120):
        msg = plant.machines["CNC-01"].step(dt=1.0)
    assert msg.metrics["spindle_temp_c"].v > 65.0  # fault physics, not the 35 C dataset value
    assert "tool_wear_min" not in VirtualPlant().machines["CNC-01"].step().metrics
