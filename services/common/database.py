"""
TwinOps Database Models and Engine.
Supports PostgreSQL (TimescaleDB) in production and SQLite in testing/embedded edge.
Ref: docs/05_design_document.md §2
"""

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

# Detect database URL from environment or default to local aiosqlite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///twinops.db")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# JSON field adapter compatible with SQLite and Postgres
JSONType = JSONB if not IS_SQLITE else JSON


class Base(DeclarativeBase):
    pass


class SiteModel(Base):
    """Enterprise 1-* Site"""

    __tablename__ = "site"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    areas: Mapped[list["AreaModel"]] = relationship(
        "AreaModel", back_populates="site", cascade="all, delete-orphan"
    )


class AreaModel(Base):
    """Site 1-* Area"""

    __tablename__ = "area"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("site.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    site: Mapped["SiteModel"] = relationship("SiteModel", back_populates="areas")
    lines: Mapped[list["LineModel"]] = relationship(
        "LineModel", back_populates="area", cascade="all, delete-orphan"
    )


class LineModel(Base):
    """Area 1-* Line"""

    __tablename__ = "line"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    area_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("area.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    area: Mapped["AreaModel"] = relationship("AreaModel", back_populates="lines")
    assets: Mapped[list["AssetModel"]] = relationship("AssetModel", back_populates="line")


class AssetTypeModel(Base):
    """Asset Type / Twin Template: metrics, limits, derived rules, 3D model path"""

    __tablename__ = "asset_type"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )  # 'cnc_machine', 'centrifugal_pump'
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    assets: Mapped[list["AssetModel"]] = relationship("AssetModel", back_populates="asset_type")


class AssetModel(Base):
    """Master physical asset record & 3D digital twin instance"""

    __tablename__ = "asset"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # 'CNC-01'
    line_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("line.id", ondelete="SET NULL"), nullable=True
    )
    type_id: Mapped[str] = mapped_column(String(64), ForeignKey("asset_type.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    make: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    serial_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    install_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criticality: Mapped[str] = mapped_column(
        String(1), CheckConstraint("criticality IN ('A','B','C')"), default="B"
    )
    lifecycle_state: Mapped[str] = mapped_column(String(32), default="Operating")
    position: Mapped[dict[str, float]] = mapped_column(JSONType, default=dict)  # {x, y, z, rotY}
    properties: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    line: Mapped[Optional["LineModel"]] = relationship("LineModel", back_populates="assets")
    asset_type: Mapped["AssetTypeModel"] = relationship("AssetTypeModel", back_populates="assets")
    tags: Mapped[list["TagModel"]] = relationship(
        "TagModel", back_populates="asset", cascade="all, delete-orphan"
    )


class AssetRelationModel(Base):
    """Relationships between assets: feeds, powers, part_of"""

    __tablename__ = "asset_relation"

    from_asset: Mapped[str] = mapped_column(String(64), primary_key=True)
    to_asset: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )  # 'powers', 'feeds_coolant', etc.


class TagModel(Base):
    """Tag configuration and source mapping to field protocols"""

    __tablename__ = "tag"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("asset.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_protocol: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'opcua', 'modbus', 'mqtt', 's7'
    source_address: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # 'ns=2;s=Line1.CNC01.SpindleTemp'
    scan_ms: Mapped[int] = mapped_column(Integer, default=1000)
    deadband: Mapped[float] = mapped_column(Float, default=0.0)
    lo_lo: Mapped[float | None] = mapped_column(Float, nullable=True)
    lo: Mapped[float | None] = mapped_column(Float, nullable=True)
    hi: Mapped[float | None] = mapped_column(Float, nullable=True)
    hi_hi: Mapped[float | None] = mapped_column(Float, nullable=True)

    asset: Mapped["AssetModel"] = relationship("AssetModel", back_populates="tags")


class TelemetryModel(Base):
    """
    Time-series table.
    On TimescaleDB, hypertable partitioned by ts.
    """

    __tablename__ = "telemetry"

    # In SQLite, INTEGER PRIMARY KEY aliases ROWID for true autoincrement
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    quality: Mapped[int] = mapped_column(
        SmallInteger, default=0
    )  # 0 good, 1 uncertain, 2 bad, 3 stale

    __table_args__ = (Index("idx_telemetry_asset_metric_ts", "asset_id", "metric", "ts"),)


class AlarmModel(Base):
    """ISA-18.2 Alarm records"""

    __tablename__ = "alarm"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)  # low, medium, high, critical
    rule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(
        String(32), default="active"
    )  # active, acked, cleared, shelved
    raised_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    acked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkOrderModel(Base):
    """Maintenance work orders"""

    __tablename__ = "work_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(
        String(32), default="corrective"
    )  # corrective, preventive, predictive
    priority: Mapped[str] = mapped_column(
        String(16), default="medium"
    )  # low, medium, high, critical
    status: Mapped[str] = mapped_column(
        String(32), default="open"
    )  # open, assigned, in_progress, on_hold, completed, closed
    assignee: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")  # manual, pm, alarm, ai
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    parts_used: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    labour_minutes: Mapped[int] = mapped_column(Integer, default=0)


class PMPlanModel(Base):
    """Preventive Maintenance Plans (Calendar and Meter Based)"""

    __tablename__ = "pm_plan"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("asset.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), default="meter")  # calendar, meter
    interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checklist: Mapped[list[str]] = mapped_column(JSONType, default=list)
    last_done: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SparePartModel(Base):
    """Spare Parts Inventory"""

    __tablename__ = "spare_part"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=5)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)


class AuditLogModel(Base):
    """Security and compliance audit trail"""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # CREATE, UPDATE, DELETE, ACK_ALARM
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    diff: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


# Engine & Session Maker
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency helper for FastAPI endpoints."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables and setup TimescaleDB hypertable if running on PostgreSQL."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # If connected to PostgreSQL / TimescaleDB, create hypertable
        if not IS_SQLITE:
            try:
                await conn.execute(
                    text("SELECT create_hypertable('telemetry', 'ts', if_not_exists => TRUE);")
                )
            except Exception:
                pass  # not a timescaledb extension, regular postgres


async def seed_pilot_data(session: AsyncSession):
    """
    Seed initial ISA-95 site hierarchy, asset types, and all 25 pilot assets.
    """
    from services.common.twin_templates import TEMPLATES
    from simulator.config import ASSET_RELATIONSHIPS, PILOT_ASSETS

    # Check if already seeded
    res = await session.execute(select(func.count(SiteModel.id)))
    if (res.scalar() or 0) > 0:
        return

    # 1. Site
    site = SiteModel(
        id="PUNE-01",
        name="Pune Auto Machining Facility",
        timezone="Asia/Kolkata",
        address="Chakan Industrial Area, Phase II, Pune, Maharashtra 410501",
    )
    session.add(site)

    # 2. Area
    area = AreaModel(id="AREA-MACHINING", site_id="PUNE-01", name="Machining & Assembly Bay")
    session.add(area)

    # 3. Lines
    line1 = LineModel(
        id="LINE-01", area_id="AREA-MACHINING", name="Line 1: Cylinder Head Machining"
    )
    line2 = LineModel(
        id="LINE-02", area_id="AREA-MACHINING", name="Line 2: Gearbox Casing Machining"
    )
    session.add_all([line1, line2])

    # 4. Asset Types (from twin templates)
    for tid, tpl in TEMPLATES.items():
        atm = AssetTypeModel(id=tid, name=tpl.name, template=tpl.model_dump())
        session.add(atm)

    # 5. Assets (all 25 pilot assets)
    for ac in PILOT_ASSETS:
        am = AssetModel(
            id=ac.asset_id,
            line_id=ac.line_id,
            type_id=ac.type_id,
            name=ac.name,
            make=ac.make,
            model=ac.model,
            serial_no=ac.serial_no,
            criticality=ac.criticality,
            lifecycle_state="Operating",
            position=ac.position_3d,
            properties=ac.nominal_params,
        )
        session.add(am)

    # 6. Relationships
    for rel in ASSET_RELATIONSHIPS:
        arm = AssetRelationModel(
            from_asset=rel["from_asset"], to_asset=rel["to_asset"], kind=rel["kind"]
        )
        session.add(arm)

    await session.commit()
