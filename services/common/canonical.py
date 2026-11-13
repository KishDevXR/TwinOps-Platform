"""
TwinOps Canonical Data Models and Quality Definitions.
Ref: docs/05_design_document.md §3, docs/04_architecture.md §3
"""

from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DataQuality(IntEnum):
    """Data quality codes according to OPC UA / industrial standards."""
    GOOD = 0
    UNCERTAIN = 1
    BAD = 2
    STALE = 3


class AssetOperationalStatus(StrEnum):
    """Standard asset operational lifecycle / runtime states."""
    RUNNING = "RUNNING"
    IDLE = "IDLE"
    STOPPED = "STOPPED"
    FAULT = "FAULT"
    OFFLINE = "OFFLINE"


class MetricValue(BaseModel):
    """Individual metric value with data quality code."""
    v: Union[float, int, str, bool] = Field(..., description="Sampled value")
    q: int = Field(default=DataQuality.GOOD, description="Quality: 0=good, 1=uncertain, 2=bad, 3=stale")

    @field_validator("q")
    @classmethod
    def validate_quality(cls, v: int) -> int:
        if v not in (DataQuality.GOOD, DataQuality.UNCERTAIN, DataQuality.BAD, DataQuality.STALE):
            raise ValueError(f"Invalid quality code {v}. Must be 0, 1, 2, or 3.")
        return v


class CanonicalTelemetryMessage(BaseModel):
    """
    Standard Canonical Telemetry Message emitted by Edge Gateways and Simulator.
    Strictly follows docs/05_design_document.md §3.
    """
    v: int = Field(default=1, description="Schema version")
    site: str = Field(..., description="Site identifier, e.g. PUNE-01")
    asset_id: str = Field(..., description="Unique asset identifier, e.g. CNC-01")
    ts: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp in UTC ISO-8601 format"
    )
    metrics: Dict[str, MetricValue] = Field(
        default_factory=dict,
        description="Map of canonical metric names to values and qualities"
    )
    status: AssetOperationalStatus = Field(
        default=AssetOperationalStatus.RUNNING,
        description="Operational state of the asset"
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )


class CanonicalEventMessage(BaseModel):
    """State changes, edge alarms, and operational notifications."""
    v: int = Field(default=1, description="Schema version")
    site: str = Field(..., description="Site identifier")
    asset_id: str = Field(..., description="Asset identifier")
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = Field(..., description="e.g. STATE_CHANGE, EDGE_ALARM, FAULT_TRIP")
    severity: str = Field(default="INFO", description="INFO, LOW, MEDIUM, HIGH, CRITICAL")
    message: str = Field(..., description="Human readable description")
    data: Dict[str, Any] = Field(default_factory=dict, description="Contextual payload")


class GatewayHealthMessage(BaseModel):
    """Gateway heartbeat emitted every 30 seconds."""
    v: int = Field(default=1, description="Schema version")
    site: str = Field(...)
    gateway_id: str = Field(...)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="HEALTHY", description="HEALTHY, DEGRADED, OFFLINE")
    uptime_seconds: int = Field(default=0)
    connected_connectors: list[str] = Field(default_factory=list)
    buffered_records: int = Field(default=0, description="Records queued in local store-and-forward buffer")
    cpu_percent: float = Field(default=0.0)
    memory_percent: float = Field(default=0.0)
