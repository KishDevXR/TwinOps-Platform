"""
Tests for Canonical Telemetry Schema, Quality Flags, and Topic Routing.
Maps to requirement: CON-06 (Data-quality flags), TWN-01 (Twin templates)
"""

from datetime import UTC, datetime

import pytest

from services.common.canonical import (
    AssetOperationalStatus,
    CanonicalTelemetryMessage,
    DataQuality,
    MetricValue,
)
from services.common.mqtt_topics import (
    gateway_health_topic,
    parse_topic,
    telemetry_topic,
)
from services.common.twin_templates import get_template


def test_con_06_data_quality_flags():
    """Verify data-quality flags (good, bad, uncertain, stale) on every value."""
    # Good quality
    mv_good = MetricValue(v=42.5, q=DataQuality.GOOD)
    assert mv_good.q == 0

    # Uncertain quality
    mv_uncertain = MetricValue(v=42.5, q=DataQuality.UNCERTAIN)
    assert mv_uncertain.q == 1

    # Bad quality
    mv_bad = MetricValue(v=0.0, q=DataQuality.BAD)
    assert mv_bad.q == 2

    # Stale quality
    mv_stale = MetricValue(v=42.5, q=DataQuality.STALE)
    assert mv_stale.q == 3

    # Invalid quality must raise ValidationError
    with pytest.raises(ValueError):
        MetricValue(v=10.0, q=99)


def test_con_06_canonical_message_structure():
    """Verify serialization and validation of canonical telemetry message."""
    now = datetime.now(UTC)
    msg = CanonicalTelemetryMessage(
        v=1,
        site="PUNE-01",
        asset_id="CNC-01",
        ts=now,
        metrics={
            "spindle_temp_c": MetricValue(v=61.4, q=0),
            "vibration_mm_s": MetricValue(v=3.2, q=0),
            "spindle_rpm": MetricValue(v=8000, q=0),
            "power_kw": MetricValue(v=11.8, q=0),
        },
        status=AssetOperationalStatus.RUNNING,
    )

    data = msg.model_dump()
    assert data["v"] == 1
    assert data["site"] == "PUNE-01"
    assert data["asset_id"] == "CNC-01"
    assert data["status"] == "RUNNING"
    assert data["metrics"]["spindle_temp_c"]["v"] == 61.4
    assert data["metrics"]["spindle_temp_c"]["q"] == 0


def test_mqtt_topic_routing():
    """Verify topic generation and bidirectional parsing."""
    t_top = telemetry_topic("PUNE-01", "CNC-01")
    assert t_top == "twinops/PUNE-01/CNC-01/telemetry"

    parsed = parse_topic(t_top)
    assert parsed is not None
    assert parsed["type"] == "asset"
    assert parsed["site"] == "PUNE-01"
    assert parsed["asset_id"] == "CNC-01"
    assert parsed["channel"] == "telemetry"

    gw_top = gateway_health_topic("PUNE-01", "GW-01")
    assert gw_top == "twinops/PUNE-01/edge/GW-01/health"

    parsed_gw = parse_topic(gw_top)
    assert parsed_gw is not None
    assert parsed_gw["type"] == "gateway"
    assert parsed_gw["gateway_id"] == "GW-01"
    assert parsed_gw["channel"] == "health"


def test_twn_01_pilot_templates_complete():
    """Verify all 8 pilot equipment categories have valid twin templates."""
    expected_categories = [
        "cnc_machine",
        "conveyor",
        "robot_cell",
        "air_compressor",
        "centrifugal_pump",
        "chiller",
        "ahu",
        "energy_meter",
    ]
    for cat in expected_categories:
        tpl = get_template(cat)
        assert tpl is not None, f"Missing template for {cat}"
        assert len(tpl.metrics) > 0
        assert tpl.model_3d.endswith(".glb")
        assert len(tpl.status_rules) > 0
