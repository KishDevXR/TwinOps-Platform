"""
TwinOps Asset Management Pydantic Schemas.
Ref: docs/02_prd.md §6.2 (AST), docs/05_design_document.md §1, 5
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# -------------------------------------------------------------
# Asset Schemas
# -------------------------------------------------------------


class AssetBase(BaseModel):
    name: str = Field(..., max_length=255)
    line_id: str | None = Field(None, max_length=36)
    type_id: str = Field(..., max_length=64)
    make: str | None = Field(None, max_length=128)
    model: str | None = Field(None, max_length=128)
    serial_no: str | None = Field(None, max_length=128)
    install_date: datetime | None = None
    criticality: Literal["A", "B", "C"] = "B"
    lifecycle_state: Literal[
        "Planned", "Installed", "Operating", "Under Maintenance", "Idle", "Decommissioned"
    ] = "Operating"
    position: dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0, "rot_y": 0.0}
    )
    properties: dict[str, Any] = Field(default_factory=dict)


class AssetCreate(AssetBase):
    id: str = Field(
        ..., min_length=1, max_length=64, description="Unique asset identifier, e.g. CNC-01"
    )


class AssetUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    line_id: str | None = Field(None, max_length=36)
    type_id: str | None = Field(None, max_length=64)
    make: str | None = Field(None, max_length=128)
    model: str | None = Field(None, max_length=128)
    serial_no: str | None = Field(None, max_length=128)
    install_date: datetime | None = None
    criticality: Literal["A", "B", "C"] | None = None
    lifecycle_state: (
        Literal["Planned", "Installed", "Operating", "Under Maintenance", "Idle", "Decommissioned"]
        | None
    ) = None
    position: dict[str, float] | None = None
    properties: dict[str, Any] | None = None


class TagSummary(BaseModel):
    id: str
    metric: str
    unit: str | None
    source_protocol: str
    source_address: str
    scan_ms: int


class AssetRelationshipItem(BaseModel):
    from_asset: str
    to_asset: str
    kind: str


class AssetResponse(AssetBase):
    id: str
    created_at: datetime
    updated_at: datetime
    tags: list[TagSummary] = Field(default_factory=list)
    relationships: list[AssetRelationshipItem] = Field(default_factory=list)


# -------------------------------------------------------------
# ISA-95 Tree Schemas
# -------------------------------------------------------------


class AssetTreeNode(BaseModel):
    id: str
    name: str
    type_id: str
    criticality: str
    lifecycle_state: str
    position: dict[str, float]


class LineTreeNode(BaseModel):
    id: str
    name: str
    assets: list[AssetTreeNode] = Field(default_factory=list)


class AreaTreeNode(BaseModel):
    id: str
    name: str
    lines: list[LineTreeNode] = Field(default_factory=list)


class SiteTreeResponse(BaseModel):
    id: str
    name: str
    timezone: str
    address: str | None
    areas: list[AreaTreeNode] = Field(default_factory=list)


# -------------------------------------------------------------
# Tag & Bulk Import Schemas
# -------------------------------------------------------------


class TagCreate(BaseModel):
    asset_id: str = Field(..., max_length=64)
    metric: str = Field(..., max_length=64)
    unit: str | None = Field(None, max_length=32)
    source_protocol: str = Field(..., max_length=32)  # opcua, modbus, mqtt, s7
    source_address: str = Field(..., max_length=255)
    scan_ms: int = Field(default=1000)
    deadband: float = Field(default=0.0)
    lo_lo: float | None = None
    lo: float | None = None
    hi: float | None = None
    hi_hi: float | None = None


class TagResponse(TagCreate):
    id: str


class AssetRelationshipCreate(BaseModel):
    from_asset: str = Field(..., max_length=64)
    to_asset: str = Field(..., max_length=64)
    kind: str = Field(
        ..., max_length=32, description="powers, feeds_coolant, feeds_air, feeds_part"
    )


class BulkImportResult(BaseModel):
    total_processed: int
    created_count: int
    updated_count: int
    errors: list[str] = Field(default_factory=list)
