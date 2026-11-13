TwinOps — Design Document

Digital Twin Asset Management Platform

13 November 2026

1. Domain model

Enterprise 1─* Site 1─* Area 1─* Line 1─* Asset 1─* Component

Asset *─1 AssetType (twin template)

Asset 1─* Tag · Asset 1─* Alarm · Asset 1─* WorkOrder

Asset *─* Asset (relationships: feeds, powers, part_of)

2. Database schema (PostgreSQL + TimescaleDB)

CREATE TABLE site (id uuid PK, name text,  timezone text DEFAULT 'Asia/Kolkata', address text);CREATE TABLE area (id uuid PK, site_id uuid FK, name text);CREATE TABLE line (id uuid PK, area_id uuid FK, name text);CREATE TABLE asset_type (  id text PK,               -- 'cnc_machine', 'centrifugal_pump'  name text, template jsonb -- metrics, units, limits, 3D model, KPIs);CREATE TABLE asset (  id text PK,               -- 'CNC-01'  line_id uuid FK, type_id text FK, name text,  make text, model text, serial_no text, install_date date,  criticality char(1) CHECK (criticality IN ('A','B','C')),  lifecycle_state text, position jsonb,  -- {x,y,z,rotY} in 3D scene  properties jsonb, created_at timestamptz, updated_at timestamptz);CREATE TABLE asset_relation (from_asset text, to_asset text, kind text,  PRIMARY KEY(from_asset,to_asset,kind));CREATE TABLE tag (  id uuid PK, asset_id text FK, metric text, unit text,  source_protocol text, source_address text,    -- 'opcua', 'ns=2;s=Line1.CNC01.SpindleTemp'  scan_ms int, deadband real, lo_lo real, lo real, hi real, hi_hi real);CREATE TABLE telemetry (  ts timestamptz NOT NULL, asset_id text, metric text,  value double precision, quality smallint  -- 0 good, 1 uncertain, 2 bad);SELECT create_hypertable('telemetry','ts');-- continuous aggregates: telemetry_1m, telemetry_1h; compression after 7 daysCREATE TABLE alarm (  id bigserial PK, asset_id text, metric text,  severity text,            -- low/medium/high/critical  rule_id uuid, message text, value real,  state text,               -- active/acked/cleared/shelved  raised_at timestamptz, acked_by uuid, acked_at timestamptz,  cleared_at timestamptz);CREATE TABLE work_order (  id bigserial PK, asset_id text, title text, description text,  type text,                -- corrective/preventive/predictive  priority text, status text, assignee uuid,  source text,              -- manual/pm/alarm/ai  due_at timestamptz, started_at timestamptz, completed_at timestamptz,  checklist jsonb, parts_used jsonb, labour_minutes int);CREATE TABLE pm_plan (id uuid PK, asset_id text, name text,  trigger_type text,        -- calendar/meter  interval_days int, interval_hours int, checklist jsonb,  last_done timestamptz);CREATE TABLE spare_part (id uuid PK, code text, name text, qty int,  reorder_level int, location text);CREATE TABLE audit_log (id bigserial PK, ts timestamptz, user_id uuid,  action text, entity text, entity_id text, diff jsonb);

3. Canonical telemetry message and MQTT topics

{  "v": 1,  "site": "PUNE-01",  "asset_id": "CNC-01",  "ts": "2026-11-13T06:35:12.120Z",  "metrics": {    "spindle_temp_c": {"v": 61.4, "q": 0},    "vibration_mm_s": {"v": 3.2, "q": 0},    "spindle_rpm":    {"v": 8000, "q": 0},    "power_kw":       {"v": 11.8, "q": 0}  },  "status": "RUNNING"}

Topic

Direction

Payload

twinops/{site}/{asset}/telemetry

edge → cloud

Canonical message

twinops/{site}/{asset}/event

edge → cloud

State change, edge alarm

twinops/{site}/edge/{gw}/health

edge → cloud

Gateway status, every 30 s

twinops/{site}/edge/{gw}/config

cloud → edge

Connector/tag config (retained)

4. Asset-type twin template (example)

{  "id": "centrifugal_pump",  "metrics": [    {"name": "flow_m3h", "unit": "m3/h", "hi": 120},    {"name": "discharge_bar", "unit": "bar", "hi": 8, "hi_hi": 10},    {"name": "motor_temp_c", "unit": "°C", "hi": 80, "hi_hi": 95},    {"name": "vibration_mm_s", "unit": "mm/s", "hi": 4.5, "hi_hi": 7.1}  ],  "derived": [{"name": "efficiency_pct",               "expr": "flow_m3h*discharge_bar*2.78/power_kw"}],  "status_rules": {"RUNNING": "power_kw > 0.5", "STOPPED": "power_kw <= 0.5"},  "model_3d": "models/pump_centrifugal.glb",  "pm_defaults": [{"name": "Bearing greasing", "interval_hours": 500}],  "ai": {"anomaly": true, "rul": true}}

Vibration limits follow ISO 10816 / 20816 bands.

5. REST API (v1, OpenAPI)

Method

Path

Purpose

GET

/api/v1/sites/{id}/tree

Site hierarchy

GET/POST

/api/v1/assets

List (filter by line, type, status) / create

GET/PATCH/DELETE

/api/v1/assets/{id}

Asset record

POST

/api/v1/assets/import

Excel/CSV import

GET

/api/v1/assets/{id}/twin

Live twin state + derived KPIs

GET

/api/v1/assets/{id}/telemetry?metric=&from=&to=&agg=1m

Time series

GET/POST

/api/v1/connectors

Connector configuration

POST

/api/v1/tags/import

CSV tag mapping

GET

/api/v1/alarms?state=active

Alarms

POST

/api/v1/alarms/{id}/ack

Acknowledge

GET/POST/PATCH

/api/v1/work-orders

Work orders

GET/POST

/api/v1/pm-plans

PM plans

GET

/api/v1/kpis?scope=line:L1&period=24h

OEE, MTBF, MTTR

POST

/api/v1/simulations

What-if run

POST

/api/v1/copilot/chat

AI copilot (streaming)

WS

/ws/live?site=PUNE-01

Live twin updates

Conventions: JWT bearer auth, cursor pagination, ISO-8601 UTC timestamps, RFC 7807 errors, Idempotency-Key on POST.

6. UI design

Screen

Key elements

Plant 3D Twin (home)

3D scene, assets coloured by status, hover tooltip with live values, click → side panel; alarm ticker; layer toggles (status, energy heatmap, anomaly score); timeline scrubber for playback

Asset Detail

Header (name, status, criticality, RUL), tabs: Live, Trends, Alarms, Work Orders, PM, Documents, Twin Model

Alarms

Table by severity, ack/shelve, filter by line

Maintenance

Kanban (Open → Closed), calendar of PM, work-order form with checklist

Dashboards

OEE by line, downtime Pareto, MTBF/MTTR, energy

Connectivity

Gateways, connectors, tag mapping grid, health

Copilot

Chat panel available on every screen, answers with charts and citations

Mobile (PWA)

My jobs, scan QR, checklist, photo, offline sync

Status colours: green = running, amber = warning/idle, red = alarm/fault, grey = offline/stale. Dark theme default for control rooms.

7. 3D replica pipeline

Plant layout (DWG/PDF) → floor plan in metres.

Machines: vendor CAD (STEP) → Blender, decimated → glTF/GLB (< 2 MB each), or the parametric library (box/cylinder machines).

Scene file scene.json maps asset_id → model, position, rotation.

Viewer: React-Three-Fiber, instancing for repeated machines, LOD, target 60 fps on a mid-range laptop.

8. Simulator design

Each virtual machine runs a state machine (RUNNING / IDLE / FAULT) with physics-lite signals: temperature follows load with first-order lag; vibration = baseline + noise + degradation term that grows over time; injected faults (bearing wear, overheating, cavitation) for testing anomaly and RUL. It publishes canonical messages and exposes an OPC UA and Modbus server so connectors can be tested end-to-end.

9. Key algorithms

OEE = Availability (run time / planned time) × Performance (ideal cycle × count / run time) × Quality (good / total).

Alarm rule: raise when condition holds for delay_s; clear with hysteresis (e.g. 2% of range); suppress duplicates.

Anomaly score: Isolation Forest on 5-min feature windows (mean, std, slope, kurtosis per metric), normalised 0–1; event when > 0.8 for 3 windows.