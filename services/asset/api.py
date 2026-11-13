"""
TwinOps Asset Management REST API.
Implements ISA-95 tree, Asset CRUD, Tag mappings, and CSV/Excel bulk onboarding.
Ref: docs/02_prd.md §6.2, docs/05_design_document.md §5
"""

import csv
import io
import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.asset.schemas import (
    AreaTreeNode,
    AssetCreate,
    AssetRelationshipCreate,
    AssetRelationshipItem,
    AssetResponse,
    AssetTreeNode,
    AssetUpdate,
    BulkImportResult,
    LineTreeNode,
    SiteTreeResponse,
    TagCreate,
    TagSummary,
)
from services.common.database import (
    AreaModel,
    AssetModel,
    AssetRelationModel,
    AssetTypeModel,
    AuditLogModel,
    LineModel,
    SiteModel,
    TagModel,
    get_db_session,
)

logger = logging.getLogger("twinops.asset.api")
router = APIRouter(prefix="/api/v1", tags=["asset"])


# -------------------------------------------------------------
# 1. ISA-95 Site Hierarchy Tree
# -------------------------------------------------------------


@router.get("/sites/{site_id}/tree", response_model=SiteTreeResponse)
async def get_site_hierarchy_tree(site_id: str, session: AsyncSession = Depends(get_db_session)):
    """
    Retrieve the full ISA-95 equipment hierarchy tree for a site:
    Enterprise -> Site -> Area -> Line -> Assets.
    """
    site = await session.get(SiteModel, site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    # Load areas with lines and assets
    areas_query = (
        select(AreaModel)
        .where(AreaModel.site_id == site_id)
        .options(selectinload(AreaModel.lines).selectinload(LineModel.assets))
    )
    res = await session.execute(areas_query)
    areas = res.scalars().all()

    area_nodes: list[AreaTreeNode] = []
    for area in areas:
        line_nodes: list[LineTreeNode] = []
        for line in area.lines:
            asset_nodes = [
                AssetTreeNode(
                    id=a.id,
                    name=a.name,
                    type_id=a.type_id,
                    criticality=a.criticality,
                    lifecycle_state=a.lifecycle_state,
                    position=a.position or {"x": 0.0, "y": 0.0, "z": 0.0, "rot_y": 0.0},
                )
                for a in line.assets
            ]
            line_nodes.append(LineTreeNode(id=line.id, name=line.name, assets=asset_nodes))
        area_nodes.append(AreaTreeNode(id=area.id, name=area.name, lines=line_nodes))

    return SiteTreeResponse(
        id=site.id, name=site.name, timezone=site.timezone, address=site.address, areas=area_nodes
    )


# -------------------------------------------------------------
# 2. Asset CRUD & Query
# -------------------------------------------------------------


@router.get("/assets", response_model=list[AssetResponse])
async def list_assets(
    line_id: str | None = Query(None, description="Filter by production line ID"),
    type_id: str | None = Query(None, description="Filter by asset type / twin template"),
    criticality: Literal["A", "B", "C"] | None = Query(
        None, description="Filter by criticality tier"
    ),
    lifecycle_state: str | None = Query(None, description="Operating, Under Maintenance, etc."),
    search: str | None = Query(None, description="Search by ID or name"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
):
    """
    List assets with multi-parameter filtering and search.
    """
    query = select(AssetModel).options(selectinload(AssetModel.tags))

    if line_id:
        query = query.where(AssetModel.line_id == line_id)
    if type_id:
        query = query.where(AssetModel.type_id == type_id)
    if criticality:
        query = query.where(AssetModel.criticality == criticality)
    if lifecycle_state:
        query = query.where(AssetModel.lifecycle_state == lifecycle_state)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(AssetModel.id.ilike(search_pattern), AssetModel.name.ilike(search_pattern))
        )

    query = query.order_by(AssetModel.id.asc()).offset(offset).limit(limit)
    res = await session.execute(query)
    assets = res.scalars().all()

    # Bulk fetch relations for listed assets
    asset_ids = [a.id for a in assets]
    rels_query = select(AssetRelationModel).where(
        or_(
            AssetRelationModel.from_asset.in_(asset_ids), AssetRelationModel.to_asset.in_(asset_ids)
        )
    )
    rels_res = await session.execute(rels_query)
    all_rels = rels_res.scalars().all()

    rel_map: dict[str, list[AssetRelationshipItem]] = {aid: [] for aid in asset_ids}
    for r in all_rels:
        item = AssetRelationshipItem(from_asset=r.from_asset, to_asset=r.to_asset, kind=r.kind)
        if r.from_asset in rel_map:
            rel_map[r.from_asset].append(item)
        if r.to_asset in rel_map and r.to_asset != r.from_asset:
            rel_map[r.to_asset].append(item)

    response_items = []
    for a in assets:
        tags_summary = [
            TagSummary(
                id=t.id,
                metric=t.metric,
                unit=t.unit,
                source_protocol=t.source_protocol,
                source_address=t.source_address,
                scan_ms=t.scan_ms,
            )
            for t in a.tags
        ]
        response_items.append(
            AssetResponse(
                id=a.id,
                name=a.name,
                line_id=a.line_id,
                type_id=a.type_id,
                make=a.make,
                model=a.model,
                serial_no=a.serial_no,
                install_date=a.install_date,
                criticality=a.criticality,
                lifecycle_state=a.lifecycle_state,
                position=a.position or {},
                properties=a.properties or {},
                created_at=a.created_at,
                updated_at=a.updated_at,
                tags=tags_summary,
                relationships=rel_map.get(a.id, []),
            )
        )
    return response_items


@router.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(payload: AssetCreate, session: AsyncSession = Depends(get_db_session)):
    """
    Create a new physical asset record.
    """
    existing = await session.get(AssetModel, payload.id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Asset ID '{payload.id}' already exists")

    # Validate type_id exists
    type_exists = await session.get(AssetTypeModel, payload.type_id)
    if not type_exists:
        raise HTTPException(
            status_code=400, detail=f"Asset type '{payload.type_id}' does not exist"
        )

    asset = AssetModel(
        id=payload.id,
        name=payload.name,
        line_id=payload.line_id,
        type_id=payload.type_id,
        make=payload.make,
        model=payload.model,
        serial_no=payload.serial_no,
        install_date=payload.install_date,
        criticality=payload.criticality,
        lifecycle_state=payload.lifecycle_state,
        position=payload.position,
        properties=payload.properties,
    )
    session.add(asset)

    # Audit log entry
    audit = AuditLogModel(
        action="CREATE", entity="asset", entity_id=payload.id, diff=payload.model_dump(mode="json")
    )
    session.add(audit)

    await session.commit()
    await session.refresh(asset)

    return AssetResponse(
        id=asset.id,
        name=asset.name,
        line_id=asset.line_id,
        type_id=asset.type_id,
        make=asset.make,
        model=asset.model,
        serial_no=asset.serial_no,
        install_date=asset.install_date,
        criticality=asset.criticality,
        lifecycle_state=asset.lifecycle_state,
        position=asset.position or {},
        properties=asset.properties or {},
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        tags=[],
        relationships=[],
    )


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset_by_id(asset_id: str, session: AsyncSession = Depends(get_db_session)):
    """
    Retrieve single asset details, mapped tags, and connected relationships.
    """
    query = (
        select(AssetModel).where(AssetModel.id == asset_id).options(selectinload(AssetModel.tags))
    )
    res = await session.execute(query)
    asset = res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

    # Fetch relationships
    rels_query = select(AssetRelationModel).where(
        or_(AssetRelationModel.from_asset == asset_id, AssetRelationModel.to_asset == asset_id)
    )
    rels_res = await session.execute(rels_query)
    rels = rels_res.scalars().all()

    tags_summary = [
        TagSummary(
            id=t.id,
            metric=t.metric,
            unit=t.unit,
            source_protocol=t.source_protocol,
            source_address=t.source_address,
            scan_ms=t.scan_ms,
        )
        for t in asset.tags
    ]

    return AssetResponse(
        id=asset.id,
        name=asset.name,
        line_id=asset.line_id,
        type_id=asset.type_id,
        make=asset.make,
        model=asset.model,
        serial_no=asset.serial_no,
        install_date=asset.install_date,
        criticality=asset.criticality,
        lifecycle_state=asset.lifecycle_state,
        position=asset.position or {},
        properties=asset.properties or {},
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        tags=tags_summary,
        relationships=[
            AssetRelationshipItem(from_asset=r.from_asset, to_asset=r.to_asset, kind=r.kind)
            for r in rels
        ],
    )


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: str, payload: AssetUpdate, session: AsyncSession = Depends(get_db_session)
):
    """
    Update asset attributes, 3D positions, or lifecycle state.
    """
    asset = await session.get(AssetModel, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

    diff = {}
    for field, val in payload.model_dump(exclude_unset=True).items():
        if val is not None:
            old_val = getattr(asset, field)
            setattr(asset, field, val)
            diff[field] = {"old": old_val, "new": val}

    if diff:
        audit = AuditLogModel(action="UPDATE", entity="asset", entity_id=asset_id, diff=diff)
        session.add(audit)
        await session.commit()
        await session.refresh(asset)

    return await get_asset_by_id(asset_id, session)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(asset_id: str, session: AsyncSession = Depends(get_db_session)):
    """
    Delete an asset and its relationships.
    """
    asset = await session.get(AssetModel, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

    # Clean relationships
    await session.execute(
        delete(AssetRelationModel).where(
            or_(AssetRelationModel.from_asset == asset_id, AssetRelationModel.to_asset == asset_id)
        )
    )
    # Delete asset
    await session.delete(asset)

    audit = AuditLogModel(action="DELETE", entity="asset", entity_id=asset_id, diff={})
    session.add(audit)

    await session.commit()


# -------------------------------------------------------------
# 3. Bulk CSV / Excel Import (AST-04 & CON-03)
# -------------------------------------------------------------


@router.post("/assets/import", response_model=BulkImportResult)
async def import_assets_csv(
    file: UploadFile | None = File(None),
    payload: list[AssetCreate] | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """
    AST-04: Bulk onboard assets via CSV upload or direct JSON array.
    Target onboarding time < 30 minutes.
    """
    items_to_process: list[dict[str, Any]] = []

    if file:
        content = await file.read()
        text_stream = io.StringIO(content.decode("utf-8-sig"))
        reader = csv.DictReader(text_stream)
        items_to_process = list(reader)
    elif payload:
        items_to_process = [item.model_dump() for item in payload]
    else:
        raise HTTPException(
            status_code=400, detail="Provide either a CSV file or JSON payload array"
        )

    created = 0
    updated = 0
    errors = []

    for idx, row in enumerate(items_to_process):
        aid = row.get("id") or row.get("asset_id")
        if not aid:
            errors.append(f"Row {idx + 1}: Missing asset id")
            continue

        existing = await session.get(AssetModel, aid)
        type_id = row.get("type_id", "cnc_machine")

        # Verify type_id
        t_exist = await session.get(AssetTypeModel, type_id)
        if not t_exist:
            errors.append(f"Row {idx + 1} ({aid}): Invalid type_id '{type_id}'")
            continue

        pos_str = row.get("position")
        position = {"x": 0.0, "y": 0.0, "z": 0.0, "rot_y": 0.0}
        if isinstance(pos_str, str):
            try:
                position = json.loads(pos_str)
            except Exception:
                pass
        elif isinstance(pos_str, dict):
            position = pos_str

        if existing:
            existing.name = row.get("name", existing.name)
            existing.line_id = row.get("line_id", existing.line_id)
            existing.type_id = type_id
            existing.make = row.get("make", existing.make)
            existing.model = row.get("model", existing.model)
            existing.serial_no = row.get("serial_no", existing.serial_no)
            existing.criticality = row.get("criticality", existing.criticality)
            existing.lifecycle_state = row.get("lifecycle_state", existing.lifecycle_state)
            existing.position = position
            updated += 1
        else:
            new_asset = AssetModel(
                id=aid,
                name=row.get("name", aid),
                line_id=row.get("line_id", "LINE-01"),
                type_id=type_id,
                make=row.get("make"),
                model=row.get("model"),
                serial_no=row.get("serial_no"),
                criticality=row.get("criticality", "B"),
                lifecycle_state=row.get("lifecycle_state", "Operating"),
                position=position,
            )
            session.add(new_asset)
            created += 1

    await session.commit()
    return BulkImportResult(
        total_processed=len(items_to_process),
        created_count=created,
        updated_count=updated,
        errors=errors,
    )


@router.post("/tags/import", response_model=BulkImportResult)
async def import_tags_csv(
    file: UploadFile | None = File(None),
    payload: list[TagCreate] | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """
    CON-03: Bulk import tag mappings from CSV or JSON array.
    """
    items_to_process: list[dict[str, Any]] = []

    if file:
        content = await file.read()
        text_stream = io.StringIO(content.decode("utf-8-sig"))
        reader = csv.DictReader(text_stream)
        items_to_process = list(reader)
    elif payload:
        items_to_process = [item.model_dump() for item in payload]
    else:
        raise HTTPException(
            status_code=400, detail="Provide either a CSV file or JSON payload array"
        )

    created = 0
    updated = 0
    errors = []

    for idx, row in enumerate(items_to_process):
        aid = row.get("asset_id")
        metric = row.get("metric")
        if not aid or not metric:
            errors.append(f"Row {idx + 1}: Missing asset_id or metric")
            continue

        # Check asset exists
        asset = await session.get(AssetModel, aid)
        if not asset:
            errors.append(f"Row {idx + 1}: Asset '{aid}' does not exist")
            continue

        # Check existing tag for asset + metric
        t_query = select(TagModel).where(TagModel.asset_id == aid, TagModel.metric == metric)
        t_res = await session.execute(t_query)
        existing = t_res.scalar_one_or_none()

        protocol = row.get("source_protocol", "opcua")
        address = row.get("source_address", f"ns=2;s={aid}.{metric}")
        unit = row.get("unit")
        scan_ms = int(row.get("scan_ms", 1000))
        lo = float(row["lo"]) if row.get("lo") is not None and row["lo"] != "" else None
        hi = float(row["hi"]) if row.get("hi") is not None and row["hi"] != "" else None

        if existing:
            existing.source_protocol = protocol
            existing.source_address = address
            existing.unit = unit
            existing.scan_ms = scan_ms
            existing.lo = lo
            existing.hi = hi
            updated += 1
        else:
            tag = TagModel(
                asset_id=aid,
                metric=metric,
                unit=unit,
                source_protocol=protocol,
                source_address=address,
                scan_ms=scan_ms,
                lo=lo,
                hi=hi,
            )
            session.add(tag)
            created += 1

    await session.commit()
    return BulkImportResult(
        total_processed=len(items_to_process),
        created_count=created,
        updated_count=updated,
        errors=errors,
    )


# -------------------------------------------------------------
# 4. Asset Relationships
# -------------------------------------------------------------


@router.post(
    "/assets/{asset_id}/relationships",
    response_model=AssetRelationshipItem,
    status_code=status.HTTP_201_CREATED,
)
async def add_asset_relationship(
    asset_id: str, payload: AssetRelationshipCreate, session: AsyncSession = Depends(get_db_session)
):
    """Add a relationship between two assets (feeds_coolant, powers, feeds_air, feeds_part)."""
    if payload.from_asset != asset_id and payload.to_asset != asset_id:
        raise HTTPException(
            status_code=400, detail="Relationship must connect to the target asset_id"
        )

    rel = AssetRelationModel(
        from_asset=payload.from_asset, to_asset=payload.to_asset, kind=payload.kind
    )
    session.add(rel)
    await session.commit()
    return AssetRelationshipItem(from_asset=rel.from_asset, to_asset=rel.to_asset, kind=rel.kind)


@router.delete("/assets/{asset_id}/relationships", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_relationship(
    asset_id: str,
    target_asset: str = Query(...),
    kind: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
):
    """Remove relationship between assets."""
    await session.execute(
        delete(AssetRelationModel).where(
            or_(
                (AssetRelationModel.from_asset == asset_id)
                & (AssetRelationModel.to_asset == target_asset)
                & (AssetRelationModel.kind == kind),
                (AssetRelationModel.from_asset == target_asset)
                & (AssetRelationModel.to_asset == asset_id)
                & (AssetRelationModel.kind == kind),
            )
        )
    )
    await session.commit()
