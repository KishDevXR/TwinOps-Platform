"""
TwinOps Common Module.
Exports canonical schemas, topic definitions, quality flags, and asset templates.
"""

from services.common.canonical import (
    AssetOperationalStatus,
    CanonicalEventMessage,
    CanonicalTelemetryMessage,
    DataQuality,
    GatewayHealthMessage,
    MetricValue,
)
from services.common.mqtt_topics import (
    event_topic,
    gateway_config_topic,
    gateway_health_topic,
    parse_topic,
    telemetry_topic,
)
from services.common.twin_templates import (
    TEMPLATES,
    AssetTypeTemplate,
    DerivedMetricDefinition,
    MetricDefinition,
    PMDefault,
    get_template,
)

__all__ = [
    "DataQuality",
    "AssetOperationalStatus",
    "MetricValue",
    "CanonicalTelemetryMessage",
    "CanonicalEventMessage",
    "GatewayHealthMessage",
    "telemetry_topic",
    "event_topic",
    "gateway_health_topic",
    "gateway_config_topic",
    "parse_topic",
    "AssetTypeTemplate",
    "MetricDefinition",
    "DerivedMetricDefinition",
    "PMDefault",
    "TEMPLATES",
    "get_template",
]
