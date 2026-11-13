"""
Tests for Virtual Plant Simulator and Fault Injection.
Maps to test cases:
- TC-AST-01 (Asset inventory & hierarchy)
- TC-TWN-03 (Overheat fault injection)
- TC-ANL-02 (Bearing wear anomaly injection)
- TC-CON-06 (Data-quality flags & comm loss)
"""

from services.common.canonical import DataQuality
from simulator.plant import VirtualPlant


def test_ast_01_pilot_asset_inventory():
    """TC-AST-01: Verify all 29 pilot assets (25 machines + 4 logistics) are present."""
    plant = VirtualPlant(site="PUNE-01")
    assert len(plant.machines) == 29

    # Check breakdown per scope decision
    cncs = [m for m in plant.machines.values() if m.type_id == "cnc_machine"]
    conveyors = [m for m in plant.machines.values() if m.type_id == "conveyor"]
    robots = [m for m in plant.machines.values() if m.type_id == "robot_cell"]
    compressors = [m for m in plant.machines.values() if m.type_id == "air_compressor"]
    pumps = [m for m in plant.machines.values() if m.type_id == "centrifugal_pump"]
    chillers = [m for m in plant.machines.values() if m.type_id == "chiller"]
    ahus = [m for m in plant.machines.values() if m.type_id == "ahu"]
    meters = [m for m in plant.machines.values() if m.type_id == "energy_meter"]

    assert len(cncs) == 6
    assert len(conveyors) == 2
    assert len(robots) == 2
    assert len(compressors) == 2
    assert len(pumps) == 4
    assert len(chillers) == 1
    assert len(ahus) == 2
    assert len(meters) == 6

    # Verify relationships are loaded
    assert len(plant.relationships) >= 20


def test_twn_03_inject_overheat_cnc02():
    """TC-TWN-03: Inject overheat fault on CNC-02 and observe spindle temperature rise."""
    plant = VirtualPlant(site="PUNE-01")
    cnc = plant.get_machine("CNC-02")
    assert cnc is not None

    # Step normal: temperature baseline is ~45-55 °C
    for _ in range(5):
        cnc.step(dt=1.0)
    baseline_temp = float(cnc.temperature)
    assert baseline_temp < 60.0

    # Inject overheat fault (severity 1.0)
    plant.inject_fault("CNC-02", "overheat", severity=1.0)

    # Step 30 seconds to allow first-order thermal lag to take effect
    for _ in range(30):
        cnc.step(dt=1.0)

    fault_temp = float(cnc.temperature)
    # Temperature should have climbed past 70 °C (exceeding hi_hi 75 limit)
    assert fault_temp > baseline_temp + 15.0
    assert fault_temp > 70.0

    # Clear fault and verify cool-down
    plant.clear_fault("CNC-02", "overheat")
    for _ in range(30):
        cnc.step(dt=1.0)
    recovered_temp = float(cnc.temperature)
    assert recovered_temp < fault_temp


def test_anl_02_inject_bearing_wear_pump01():
    """TC-ANL-02: Inject gradual bearing wear on PUMP-01 and verify vibration spike."""
    plant = VirtualPlant(site="PUNE-01")
    pump = plant.get_machine("PUMP-01")
    assert pump is not None

    # Baseline vibration is ~2.1 mm/s (ISO 10816 Zone A/B)
    for _ in range(5):
        pump.step(dt=1.0)
    baseline_vib = float(pump.vibration)
    assert baseline_vib < 3.5

    # Inject bearing wear
    plant.inject_fault("PUMP-01", "bearing_wear", severity=1.0)

    # Step 20 seconds
    for _ in range(20):
        pump.step(dt=1.0)

    worn_vib = float(pump.vibration)
    # Vibration should rise into warning/critical range (> 4.5 mm/s)
    assert worn_vib > 4.5
    assert worn_vib > baseline_vib + 2.0


def test_con_06_comm_loss_and_sensor_fault():
    """TC-CON-06: Verify simulator handling of communication loss and bad quality flags."""
    plant = VirtualPlant(site="PUNE-01")
    cnc = plant.get_machine("CNC-01")

    # Inject sensor fault -> qualities should become BAD (2)
    plant.inject_fault("CNC-01", "sensor_fault", severity=1.0)
    msg = cnc.step(dt=1.0)
    assert msg is not None
    assert msg.metrics["spindle_temp_c"].q == DataQuality.BAD

    # Inject comm loss -> machine returns None (dropped from message stream)
    plant.inject_fault("CNC-01", "comm_loss")
    msg_comm_loss = cnc.step(dt=1.0)
    assert msg_comm_loss is None

    # Whole plant tick should now have 28 messages instead of 29
    messages = plant.tick(dt=1.0)
    assert len(messages) == 28
    assert not any(m.asset_id == "CNC-01" for m in messages)
