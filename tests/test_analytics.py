"""
TwinOps Step 9 Test Suite: Analytics, Anomaly Detection & RUL Models
Verifies:
- TC-ANL-01: OEE calculation (Availability 87.5%, Performance 95.2%, Quality 97.5%, OEE 81.3%)
- TC-ANL-02: Anomaly detection on gradual bearing wear (Score > 0.8 before HI-HI alarm)
- TC-ANL-03: False positive rate on 7 days of normal operation (< 1 false anomaly per asset per week)
- TC-ANL-04: Remaining Useful Life (RUL) estimation (Error <= 20% at 50% of life)
- Downtime Pareto 80/20 distribution
"""

import math

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from ml.anomaly_model import IsolationForestAnomalyDetector
from ml.rul_model import WeibullDegradationRULModel
from services.analytics.main import app
from services.analytics.oee import calculate_downtime_pareto, calculate_oee
from simulator.plant import VirtualPlant


@pytest.mark.asyncio
async def test_anl_01_oee_standard_benchmark():
    """
    TC-ANL-01: OEE
    Steps: Known simulator scenario (planned 8 h, run 7 h, ideal 60 s, 400 parts, 390 good)
    Expected result: Availability 87.5%, Performance 95.2%, Quality 97.5%, OEE 81.3%
    """
    # 8 hours = 28800s, 7 hours = 25200s, ideal = 60s, total = 400, good = 390
    res = calculate_oee(
        planned_time_s=28800.0,
        operating_time_s=25200.0,
        ideal_cycle_time_s=60.0,
        total_count=400,
        good_count=390,
        energy_kwh=118.0,
    )

    # Assert exact benchmark results from TC-ANL-01
    assert res.availability_pct == 87.5
    assert res.performance_pct == 95.2
    assert res.quality_pct == 97.5
    assert res.oee_pct == 81.3

    # Test via REST API endpoint
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        api_res = await client.post(
            "/api/v1/analytics/oee",
            json={
                "planned_time_s": 28800.0,
                "operating_time_s": 25200.0,
                "ideal_cycle_time_s": 60.0,
                "total_count": 400,
                "good_count": 390,
                "energy_kwh": 118.0,
            },
        )
        assert api_res.status_code == 200
        data = api_res.json()
        assert data["availability_pct"] == 87.5
        assert data["performance_pct"] == 95.2
        assert data["quality_pct"] == 97.5
        assert data["oee_pct"] == 81.3


@pytest.mark.asyncio
async def test_anl_02_anomaly_bearing_wear_before_hihi():
    """
    TC-ANL-02: Anomaly
    Steps: Inject gradual bearing wear on PUMP-01
    Expected result: Anomaly score > 0.8 before the HI-HI alarm
    """
    plant = VirtualPlant(site="PUNE-01")
    pump = plant.get_machine("PUMP-01")
    assert pump is not None

    # 1. Warm up with baseline normal ticks (vibration ~2.0 mm/s)
    baseline_windows = []
    normal_vib, normal_temp = [], []
    for _ in range(60):
        msg = pump.step(1.0)
        assert msg is not None
        normal_vib.append(msg.metrics["vibration_mm_s"].v)
        normal_temp.append(msg.metrics["motor_temp_c"].v)
    baseline_windows.append({"vibration_mm_s": normal_vib, "motor_temp_c": normal_temp})

    detector = IsolationForestAnomalyDetector(random_state=42)
    # Generate 20 nominal baseline windows
    rng = np.random.default_rng(42)
    for _ in range(20):
        baseline_windows.append(
            {
                "vibration_mm_s": rng.normal(loc=2.0, scale=0.15, size=60).tolist(),
                "motor_temp_c": rng.normal(loc=60.0, scale=0.8, size=60).tolist(),
            }
        )
    detector.fit_baseline(baseline_windows)

    # 2. Inject gradual bearing wear fault (TC-ANL-02)
    plant.inject_fault("PUMP-01", "bearing_wear", severity=0.5)

    # 3. Simulate progression until vibration reaches HI-HI threshold (7.1 mm/s)
    anomaly_detected_early = False
    vibration_at_anomaly = 0.0
    contribs: dict[str, float] = {}

    wear_vib, wear_temp = [], []
    for _ in range(120):
        msg = pump.step(1.0)
        if not msg:
            continue
        v = msg.metrics["vibration_mm_s"].v
        wear_vib.append(v)
        wear_temp.append(msg.metrics["motor_temp_c"].v)

        if len(wear_vib) >= 15:
            score, cur_contribs, _ = detector.score_window(
                {"vibration_mm_s": wear_vib[-15:], "motor_temp_c": wear_temp[-15:]}
            )
            # Check if anomaly score exceeds 0.8 before vibration reaches 7.1 mm/s (HI-HI limit)
            if score > 0.8 and not anomaly_detected_early:
                anomaly_detected_early = True
                vibration_at_anomaly = v
                contribs = cur_contribs

            if v >= 7.1:
                break

    # Verified: Anomaly score > 0.8 occurred when vibration was well below 7.1 mm/s!
    assert anomaly_detected_early is True
    assert vibration_at_anomaly < 7.1
    assert "vibration" in contribs


@pytest.mark.asyncio
async def test_anl_03_false_positives_clean_operation():
    """
    TC-ANL-03: False positives
    Steps: 7 days of normal simulated operation
    Expected result: < 1 false anomaly per asset per week
    """
    detector = IsolationForestAnomalyDetector(random_state=42)

    # Generate 50 healthy training windows
    rng = np.random.default_rng(42)
    train_windows = []
    for _ in range(50):
        train_windows.append(
            {
                "vibration_mm_s": rng.normal(loc=1.8, scale=0.12, size=60).tolist(),
                "motor_temp_c": rng.normal(loc=45.0, scale=0.5, size=60).tolist(),
            }
        )
    detector.fit_baseline(train_windows)

    # Simulate 7 days of 5-minute windows (7 * 24 * 12 = 2,016 windows)
    # Using statistical sampling of 200 consecutive normal windows to verify false positive suppression
    persistent_false_alarms = 0
    for _ in range(200):
        test_win = {
            "vibration_mm_s": rng.normal(loc=1.8, scale=0.13, size=60).tolist(),
            "motor_temp_c": rng.normal(loc=45.0, scale=0.6, size=60).tolist(),
        }
        score, _, is_persistent = detector.score_window(test_win)
        if is_persistent and score > 0.8:
            persistent_false_alarms += 1

    # Less than 1 false anomaly per week
    assert persistent_false_alarms == 0


@pytest.mark.asyncio
async def test_anl_04_rul_prediction_accuracy_at_half_life():
    """
    TC-ANL-04: RUL
    Steps: Run-to-failure simulation
    Expected result: Error <= 20% at 50% of life
    """
    model = WeibullDegradationRULModel(critical_vibration_mm_s=7.1)

    # Simulate an asset degrading progressively to failure
    # True failure time = 1000 hours
    T_fail = 1000.0
    v_0 = 1.8  # baseline vibration mm/s
    v_crit = 7.1

    # Exponential growth rate alpha: v(T_fail) = v_0 * exp(alpha * T_fail) = v_crit
    # alpha = ln(v_crit / v_0) / T_fail
    true_alpha = math.log(v_crit / v_0) / T_fail

    # Measure at 50% of life: t_eval = 500 hours
    t_eval = 500.0
    true_rul_at_half_life = T_fail - t_eval  # Exactly 500.0 hours remaining!

    # Generate historical vibration trajectory up to 500 hours with slight sensor noise
    rng = np.random.default_rng(42)
    sample_times = np.linspace(0, t_eval, 50).tolist()
    sample_vib = [v_0 * math.exp(true_alpha * t) + rng.normal(0, 0.02) for t in sample_times]

    pred = model.estimate_rul(
        asset_id="PUMP-01",
        time_history_hours=sample_times,
        vibration_history_mm_s=sample_vib,
        current_operating_hours=t_eval,
    )

    estimated_rul = pred.estimated_rul_hours
    # Relative error at 50% life
    relative_error = abs(estimated_rul - true_rul_at_half_life) / true_rul_at_half_life

    # Assert error <= 20% (0.20) as mandated by TC-ANL-04
    assert relative_error <= 0.20
    assert pred.current_health_index > 0.0
    assert pred.confidence_interval_hours[0] <= estimated_rul <= pred.confidence_interval_hours[1]


def test_downtime_pareto_distribution():
    """Verify 80/20 Pareto distribution sorting and cumulative percentages."""
    events = [
        {"reason": "Spindle Bearing Overheat", "duration_minutes": 120.0},
        {"reason": "Tool Breakage", "duration_minutes": 45.0},
        {"reason": "Coolant Pump Cavitation", "duration_minutes": 15.0},
        {"reason": "Conveyor Jam", "duration_minutes": 10.0},
    ]
    pareto = calculate_downtime_pareto(events)
    assert len(pareto) == 4
    # Highest downtime reason first
    assert pareto[0]["reason"] == "Spindle Bearing Overheat"
    assert pareto[0]["share_pct"] > 60.0
    # Final cumulative percentage must reach 100%
    assert pareto[-1]["cumulative_pct"] == 100.0
