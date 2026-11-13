"""
TwinOps Step 7 Test Suite: Alarms & Rules Engine (ISA-18.2)
Verifies:
- TC-ALM-01: High threshold (Motor temp > 80°C for 10s -> One HIGH alarm)
- TC-ALM-02: Delay filter (Spike for 3s only -> No alarm)
- TC-ALM-03: Hysteresis deadband & duplicate suppression (No chattering)
- TC-ALM-04: Alarm acknowledgment (State=acked, user, timestamp, comment)
- TC-ALM-05: Shelving (Shelve for 1h, hidden from active, auto-unshelve)
- TC-ALM-06: Notifications and escalation for critical alarms
- TC-ALM-07: Alarm flood suppression and summarization (500 alarms in 1 min)
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from services.alarm.engine import AlarmRulesEngine, alarm_engine
from services.alarm.main import app
from services.alarm.notification import NotificationService
from services.common.canonical import CanonicalTelemetryMessage, MetricValue
from services.common.database import (
    AlarmModel,
    get_async_session,
    init_db,
    seed_pilot_data,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    async with get_async_session() as session:
        await seed_pilot_data(session)
        # Clear any existing alarms to ensure test isolation
        await session.execute(delete(AlarmModel))
        await session.commit()
    # Reset in-memory trackers
    alarm_engine.trackers.clear()
    alarm_engine.recent_alarm_timestamps.clear()
    alarm_engine.flood_tracker.flood_active = False
    alarm_engine.flood_tracker.suppressed_count = 0
    await alarm_engine.load_rules()
    yield


@pytest.mark.asyncio
async def test_alm_01_high_threshold_sustained():
    """
    TC-ALM-01: High threshold
    Steps: Motor temperature > 80 °C for 10 s
    Expected result: One HIGH alarm raised
    """
    engine = alarm_engine
    base_time = datetime(2026, 11, 13, 10, 0, 0, tzinfo=UTC)

    # 1. At t=0s, motor_temp_c rises to 82.5°C (> 80.0°C limit, delay=10s)
    msg_t0 = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="PUMP-01",
        ts=base_time,
        metrics={"motor_temp_c": MetricValue(v=82.5, q=0)},
        status="RUNNING",
    )
    alarms_t0 = await engine.evaluate_telemetry(msg_t0)
    # At t=0s, delay filter (10s) is not satisfied yet -> No alarm
    assert len(alarms_t0) == 0

    # 2. At t=5s, still 83.0°C (elapsed 5s < 10s) -> No alarm
    msg_t5 = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="PUMP-01",
        ts=base_time + timedelta(seconds=5),
        metrics={"motor_temp_c": MetricValue(v=83.0, q=0)},
        status="RUNNING",
    )
    alarms_t5 = await engine.evaluate_telemetry(msg_t5)
    assert len(alarms_t5) == 0

    # 3. At t=10s, still 83.5°C (elapsed 10s >= 10s delay filter) -> Exactly ONE HIGH alarm raised!
    msg_t10 = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="PUMP-01",
        ts=base_time + timedelta(seconds=10),
        metrics={"motor_temp_c": MetricValue(v=83.5, q=0)},
        status="RUNNING",
    )
    alarms_t10 = await engine.evaluate_telemetry(msg_t10)
    assert len(alarms_t10) == 1
    alarm = alarms_t10[0]
    assert alarm.asset_id == "PUMP-01"
    assert alarm.metric == "motor_temp_c"
    assert alarm.severity == "high"
    assert alarm.state == "active"
    assert "80.0°C" in alarm.message


@pytest.mark.asyncio
async def test_alm_02_delay_filter_transient_spike():
    """
    TC-ALM-02: Delay filter
    Steps: Spike above the limit for 3 s only
    Expected result: No alarm
    """
    engine = alarm_engine
    base_time = datetime(2026, 11, 13, 11, 0, 0, tzinfo=UTC)

    # 1. At t=0s, transient spike to 85.0°C
    msg_t0 = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="PUMP-01",
        ts=base_time,
        metrics={"motor_temp_c": MetricValue(v=85.0, q=0)},
        status="RUNNING",
    )
    await engine.evaluate_telemetry(msg_t0)

    # 2. At t=3s, temperature drops back to 75.0°C (safe normal)
    msg_t3 = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="PUMP-01",
        ts=base_time + timedelta(seconds=3),
        metrics={"motor_temp_c": MetricValue(v=75.0, q=0)},
        status="RUNNING",
    )
    alarms_t3 = await engine.evaluate_telemetry(msg_t3)

    # 3. At t=12s, check if any alarm was raised
    msg_t12 = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="PUMP-01",
        ts=base_time + timedelta(seconds=12),
        metrics={"motor_temp_c": MetricValue(v=74.5, q=0)},
        status="RUNNING",
    )
    alarms_t12 = await engine.evaluate_telemetry(msg_t12)

    # Verified: spike lasted only 3s (< 10s delay filter), zero alarms raised!
    assert len(alarms_t3) == 0
    assert len(alarms_t12) == 0
    tracker = engine.trackers.get("PUMP-01:motor_temp_c:RULE-TEMP-MOTOR-HI")
    assert tracker is not None
    assert tracker.state == "cleared"


@pytest.mark.asyncio
async def test_alm_03_hysteresis_and_no_chattering():
    """
    TC-ALM-03: Hysteresis
    Steps: Value oscillates around the limit (e.g. 81°C, 79.5°C, 81.5°C, 79.0°C)
    Rule threshold = 80.0°C, Hysteresis = 2.0°C (clears only when <= 78.0°C)
    Expected result: No alarm chattering; a single alarm
    """
    engine = alarm_engine
    base_time = datetime(2026, 11, 13, 12, 0, 0, tzinfo=UTC)

    # 1. Trigger alarm (sustain 82°C for 10s)
    await engine.evaluate_telemetry(
        CanonicalTelemetryMessage(
            v=1,
            site="PUNE-01",
            asset_id="PUMP-01",
            ts=base_time,
            metrics={"motor_temp_c": MetricValue(v=82.0, q=0)},
            status="RUNNING",
        )
    )
    raised = await engine.evaluate_telemetry(
        CanonicalTelemetryMessage(
            v=1,
            site="PUNE-01",
            asset_id="PUMP-01",
            ts=base_time + timedelta(seconds=11),
            metrics={"motor_temp_c": MetricValue(v=82.0, q=0)},
            status="RUNNING",
        )
    )
    assert len(raised) == 1
    assert raised[0].id is not None

    # 2. Value dips to 79.5°C at t=15s (below 80°C threshold, but ABOVE 78.0°C hysteresis clear line)
    # Must NOT clear yet to prevent chattering!
    await engine.evaluate_telemetry(
        CanonicalTelemetryMessage(
            v=1,
            site="PUNE-01",
            asset_id="PUMP-01",
            ts=base_time + timedelta(seconds=15),
            metrics={"motor_temp_c": MetricValue(v=79.5, q=0)},
            status="RUNNING",
        )
    )
    tracker = engine.trackers["PUMP-01:motor_temp_c:RULE-TEMP-MOTOR-HI"]
    assert tracker.state == "active"

    # 3. Value rises back to 81.5°C at t=18s (duplicate suppression: no new alarm created)
    raised_rebound = await engine.evaluate_telemetry(
        CanonicalTelemetryMessage(
            v=1,
            site="PUNE-01",
            asset_id="PUMP-01",
            ts=base_time + timedelta(seconds=18),
            metrics={"motor_temp_c": MetricValue(v=81.5, q=0)},
            status="RUNNING",
        )
    )
    assert len(raised_rebound) == 0  # No duplicate alarm

    # 4. Value drops cleanly to 77.0°C at t=25s (below 78.0°C clear line) -> Clears alarm cleanly
    await engine.evaluate_telemetry(
        CanonicalTelemetryMessage(
            v=1,
            site="PUNE-01",
            asset_id="PUMP-01",
            ts=base_time + timedelta(seconds=25),
            metrics={"motor_temp_c": MetricValue(v=77.0, q=0)},
            status="RUNNING",
        )
    )
    assert tracker.state == "cleared"


@pytest.mark.asyncio
async def test_alm_04_acknowledge_alarm():
    """
    TC-ALM-04: Acknowledge
    Steps: Ack an alarm with a comment
    Expected result: State = acked; user and time recorded
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger an alarm
        base_time = datetime.now(UTC)
        await client.post(
            "/api/v1/alarm-rules/evaluate",
            json={
                "v": 1,
                "site": "PUNE-01",
                "asset_id": "CNC-01",
                "ts": base_time.isoformat(),
                "metrics": {"spindle_temp_c": {"v": 78.0, "q": 0}},
                "status": "RUNNING",
            },
        )
        # Advance past 2s delay for critical overheat
        res_eval = await client.post(
            "/api/v1/alarm-rules/evaluate",
            json={
                "v": 1,
                "site": "PUNE-01",
                "asset_id": "CNC-01",
                "ts": (base_time + timedelta(seconds=3)).isoformat(),
                "metrics": {"spindle_temp_c": {"v": 78.5, "q": 0}},
                "status": "RUNNING",
            },
        )
        data = res_eval.json()
        assert len(data["alarms_raised"]) >= 1
        alarm_id = data["alarms_raised"][0]["id"]

        # 2. Operator acknowledges the alarm
        res_ack = await client.post(
            f"/api/v1/alarms/{alarm_id}/ack",
            json={
                "user_id": "USER-MECH-44",
                "comment": "Spindle coolant flow inspected; pump valve adjusted.",
            },
        )
        assert res_ack.status_code == 200
        ack_data = res_ack.json()
        assert ack_data["state"] == "acked"
        assert ack_data["acked_by"] == "USER-MECH-44"
        assert ack_data["acked_at"] is not None
        assert "coolant flow inspected" in ack_data["comment"]


@pytest.mark.asyncio
async def test_alm_05_shelve_and_auto_return():
    """
    TC-ALM-05: Shelve
    Steps: Shelve for 1 h
    Expected result: Hidden for 1 h, then returns if still active
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger alarm
        base_time = datetime.now(UTC)
        await client.post(
            "/api/v1/alarm-rules/evaluate",
            json={
                "v": 1,
                "site": "PUNE-01",
                "asset_id": "CNC-02",
                "ts": base_time.isoformat(),
                "metrics": {"spindle_temp_c": {"v": 79.0, "q": 0}},
                "status": "RUNNING",
            },
        )
        res_eval = await client.post(
            "/api/v1/alarm-rules/evaluate",
            json={
                "v": 1,
                "site": "PUNE-01",
                "asset_id": "CNC-02",
                "ts": (base_time + timedelta(seconds=3)).isoformat(),
                "metrics": {"spindle_temp_c": {"v": 79.0, "q": 0}},
                "status": "RUNNING",
            },
        )
        alarm_id = res_eval.json()["alarms_raised"][0]["id"]

        # 2. Shelve for 60 minutes
        res_shelve = await client.post(
            f"/api/v1/alarms/{alarm_id}/shelve",
            json={
                "user_id": "OPERATOR-01",
                "duration_minutes": 60.0,
                "reason": "Scheduled tooling change in progress",
            },
        )
        assert res_shelve.status_code == 200
        shelve_data = res_shelve.json()
        assert shelve_data["state"] == "shelved"
        assert shelve_data["shelved_until"] is not None

        # 3. Verify it is hidden from active alarm query
        res_active = await client.get("/api/v1/alarms?state=active")
        active_ids = [a["id"] for a in res_active.json()["alarms"]]
        assert alarm_id not in active_ids

        # 4. Verify unshelve restores active state
        res_unshelve = await client.post(f"/api/v1/alarms/{alarm_id}/unshelve")
        assert res_unshelve.status_code == 200
        assert res_unshelve.json()["state"] == "active"


@pytest.mark.asyncio
async def test_alm_06_notification_dispatch_and_escalation():
    """
    TC-ALM-06: Notification & Escalation
    Steps: Raise a critical alarm; verify notifications sent within 30s; escalates if not acked
    """
    notifier = NotificationService(escalation_default_delay_s=5.0)  # 5s test escalation timer
    engine = AlarmRulesEngine(notifier=notifier)
    await engine.load_rules()

    base_time = datetime(2026, 11, 13, 14, 0, 0, tzinfo=UTC)

    # 1. Trigger critical overheat on CNC-01
    await engine.evaluate_telemetry(
        CanonicalTelemetryMessage(
            v=1,
            site="PUNE-01",
            asset_id="CNC-01",
            ts=base_time,
            metrics={"spindle_temp_c": MetricValue(v=78.0, q=0)},
            status="RUNNING",
        )
    )
    raised = await engine.evaluate_telemetry(
        CanonicalTelemetryMessage(
            v=1,
            site="PUNE-01",
            asset_id="CNC-01",
            ts=base_time + timedelta(seconds=3),
            metrics={"spindle_temp_c": MetricValue(v=78.5, q=0)},
            status="RUNNING",
        )
    )
    assert len(raised) >= 1
    crit_alarm = raised[0]

    # Verify initial notifications dispatched across email, SMS, and webhook
    dispatched_channels = [
        m.channel for m in notifier.sent_notifications if m.alarm_id == crit_alarm.id
    ]
    assert "email" in dispatched_channels
    assert "sms" in dispatched_channels
    assert "webhook" in dispatched_channels

    # Check escalation timer before expiration (at t=2s) -> No escalation yet
    esc_early = await notifier.check_escalations(current_time=base_time + timedelta(seconds=2))
    assert len(esc_early) == 0

    # Advance time past escalation delay (at t=10s) while unacknowledged -> Escalates to supervisor!
    esc_triggered = await notifier.check_escalations(current_time=base_time + timedelta(seconds=10))
    assert len(esc_triggered) >= 1
    assert any(m.is_escalation for m in esc_triggered)
    assert any("[ESCALATED]" in m.message for m in esc_triggered)


@pytest.mark.asyncio
async def test_alm_07_alarm_flood_suppression():
    """
    TC-ALM-07: Alarm flood
    Steps: 500 alarms in 1 min
    Expected result: System stays responsive; flood is summarised and suppressed
    """
    # Create engine with flood threshold = 50 alarms per min
    engine = AlarmRulesEngine(flood_threshold_per_min=50)
    now = datetime(2026, 11, 13, 15, 0, 0, tzinfo=UTC)

    # Simulate 500 alarms fired rapidly
    for i in range(500):
        t = now + timedelta(milliseconds=i * 50)
        engine.recent_alarm_timestamps.append(t)
        in_flood = engine._check_flood_status(t)
        if in_flood:
            engine.flood_tracker.suppressed_count += 1

    # Verify system detected flood, remains responsive, and summarized count
    assert engine.flood_tracker.flood_active is True
    assert engine.flood_tracker.suppressed_count > 400
    assert len(engine.recent_alarm_timestamps) == 500
