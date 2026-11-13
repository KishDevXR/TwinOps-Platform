"""
TwinOps Database Models and Engine.
Supports PostgreSQL (TimescaleDB) in production and SQLite in testing/embedded edge.
Ref: docs/05_design_document.md §2
"""

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
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
    shelved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shelved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlarmRuleModel(Base):
    """Configurable threshold, rate-of-change, and stale alarm rules"""

    __tablename__ = "alarm_rule"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    asset_type_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_type: Mapped[str] = mapped_column(
        String(32), default="threshold"
    )  # threshold, rate_of_change, stale
    severity: Mapped[str] = mapped_column(String(32), default="high")  # low, medium, high, critical
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    comparison: Mapped[str] = mapped_column(String(8), default=">")  # >, >=, <, <=
    delay_s: Mapped[float] = mapped_column(Float, default=0.0)  # delay filter in seconds
    hysteresis: Mapped[float] = mapped_column(Float, default=0.0)  # clearance hysteresis deadband
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
    last_meter_hours: Mapped[float | None] = mapped_column(Float, default=0.0)
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
    unit_cost: Mapped[float | None] = mapped_column(Float, default=0.0)


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
get_async_session = async_session_factory


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

    # Check if site hierarchy already seeded
    res = await session.execute(select(func.count(SiteModel.id)))
    if (res.scalar() or 0) == 0:
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

    # 7. Default Alarm Rules (ISA-18.2)
    rule_res = await session.execute(select(func.count(AlarmRuleModel.id)))
    if (rule_res.scalar() or 0) == 0:
        default_rules = [
            AlarmRuleModel(
                id="RULE-TEMP-MOTOR-HI",
                asset_type_id="centrifugal_pump",
                metric="motor_temp_c",
                rule_type="threshold",
                severity="high",
                threshold=80.0,
                comparison=">",
                delay_s=10.0,
                hysteresis=2.0,
                enabled=True,
                message_template="{asset_id} motor temperature {value:.1f}°C exceeded limit (80.0°C) for 10s",
            ),
            AlarmRuleModel(
                id="RULE-TEMP-MOTOR-HIHI",
                asset_type_id="centrifugal_pump",
                metric="motor_temp_c",
                rule_type="threshold",
                severity="critical",
                threshold=95.0,
                comparison=">",
                delay_s=2.0,
                hysteresis=2.0,
                enabled=True,
                message_template="{asset_id} motor temperature {value:.1f}°C exceeded critical limit (95.0°C)",
            ),
            AlarmRuleModel(
                id="RULE-TEMP-SPINDLE-HI",
                asset_type_id="cnc_machine",
                metric="spindle_temp_c",
                rule_type="threshold",
                severity="high",
                threshold=65.0,
                comparison=">",
                delay_s=5.0,
                hysteresis=2.0,
                enabled=True,
                message_template="{asset_id} spindle temperature {value:.1f}°C exceeded warning limit (65.0°C)",
            ),
            AlarmRuleModel(
                id="RULE-TEMP-SPINDLE-HIHI",
                asset_type_id="cnc_machine",
                metric="spindle_temp_c",
                rule_type="threshold",
                severity="critical",
                threshold=75.0,
                comparison=">",
                delay_s=2.0,
                hysteresis=2.0,
                enabled=True,
                message_template="{asset_id} spindle overheat {value:.1f}°C exceeded critical limit (75.0°C)",
            ),
            AlarmRuleModel(
                id="RULE-VIB-PUMP-HI",
                asset_type_id="centrifugal_pump",
                metric="vibration_mm_s",
                rule_type="threshold",
                severity="high",
                threshold=4.5,
                comparison=">",
                delay_s=5.0,
                hysteresis=0.5,
                enabled=True,
                message_template="{asset_id} vibration {value:.2f} mm/s exceeded ISO 10816 Zone C (4.5 mm/s)",
            ),
            AlarmRuleModel(
                id="RULE-VIB-PUMP-HIHI",
                asset_type_id="centrifugal_pump",
                metric="vibration_mm_s",
                rule_type="threshold",
                severity="critical",
                threshold=7.1,
                comparison=">",
                delay_s=2.0,
                hysteresis=0.5,
                enabled=True,
                message_template="{asset_id} vibration {value:.2f} mm/s exceeded ISO 10816 Zone D (7.1 mm/s)",
            ),
        ]
        for r in default_rules:
            session.add(r)

    # 8. Pilot Spare Parts Inventory
    part_res = await session.execute(select(func.count(SparePartModel.id)))
    if (part_res.scalar() or 0) == 0:
        parts = [
            SparePartModel(
                id="PART-BRG-6205",
                code="BRG-6205",
                name="Deep Groove Ball Bearing 6205",
                qty=10,
                reorder_level=5,
                location="Bin A-12",
                unit_cost=450.0,
            ),
            SparePartModel(
                id="PART-SEAL-M32",
                code="SEAL-M32",
                name="Mechanical Seal 32mm Tungsten Carbide",
                qty=6,
                reorder_level=3,
                location="Bin B-04",
                unit_cost=1850.0,
            ),
            SparePartModel(
                id="PART-BELT-V1400",
                code="BELT-V1400",
                name="V-Belt Raw Edge Cogged 1400mm",
                qty=8,
                reorder_level=4,
                location="Bin C-01",
                unit_cost=620.0,
            ),
            SparePartModel(
                id="PART-FLT-AIR-01",
                code="FLT-AIR-01",
                name="Air Intake Filter Cartridge Pleated",
                qty=4,
                reorder_level=2,
                location="Bin D-08",
                unit_cost=1200.0,
            ),
            SparePartModel(
                id="PART-OIL-ISO46",
                code="OIL-ISO46",
                name="Hydraulic Oil ISO VG 46 (Liters)",
                qty=50,
                reorder_level=20,
                location="Drum Rack 1",
                unit_cost=280.0,
            ),
        ]
        for p in parts:
            session.add(p)

    # 9. Pilot PM Plans
    pm_res = await session.execute(select(func.count(PMPlanModel.id)))
    if (pm_res.scalar() or 0) == 0:
        pm_plans = [
            PMPlanModel(
                id="PM-CNC-30D",
                asset_id="CNC-01",
                name="CNC Monthly Preventive Maintenance",
                trigger_type="calendar",
                interval_days=30,
                checklist=[
                    "Check spindle coolant and oil levels",
                    "Clean and inspect guideway telescopic covers",
                    "Measure spindle runout and vibration",
                    "Lubricate ballscrew bearings",
                ],
                last_done=datetime.now(UTC) - timedelta(days=30),
            ),
            PMPlanModel(
                id="PM-PUMP-500H",
                asset_id="PUMP-01",
                name="Pump 500-Hour Bearing Greasing & Seal Inspection",
                trigger_type="meter",
                interval_hours=500,
                last_meter_hours=0.0,
                checklist=[
                    "Inspect mechanical seal for leakage",
                    "Apply high-temperature synthetic grease to DE/NDE bearings",
                    "Check motor-to-pump coupling alignment",
                    "Record baseline vibration spectrum",
                ],
                last_done=datetime.now(UTC) - timedelta(days=60),
            ),
        ]
        for plan in pm_plans:
            session.add(plan)

    await session.commit()
