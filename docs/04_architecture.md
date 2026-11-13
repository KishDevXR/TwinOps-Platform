TwinOps — Architecture

Digital Twin Asset Management Platform

13 November 2026

1. Logical architecture

PURDUE L0-2  Sensors · PLCs · CNCs · VFDs · Meters      │  Modbus / S7 / EtherNet/IP / MTConnect PURDUE L3    SCADA · Historian  (OPC UA server, read-only)      │  OPC UA (4840)          ─── OT firewall ─── PURDUE L3.5  EDGE GATEWAY (DMZ)              ├─ Connector plugins (OPC UA, Modbus, S7, MTConnect, MQTT)              ├─ Normalizer (tag → asset/metric, units, quality)              ├─ Edge rules + local buffer (7 days, SQLite/RocksDB)              └─ MQTT client (TLS 8883, outbound only)      │                         ─── IT firewall ─── CLOUD / ON-PREM CLUSTER (Kubernetes)   Ingest:   EMQX (MQTT) ──► Kafka topics: telemetry.raw, events, commands   Stream:   Telemetry Ingest svc ─► TimescaleDB             Rule/Alarm svc  ─► alarms, auto work orders             Twin svc        ─► Redis (live state) + WebSocket fan-out             Analytics svc   ─► anomaly, RUL, KPI rollups   Core:     Asset svc · Maintenance svc · Document svc · Identity (Keycloak)   AI:       Copilot svc (LLM + tools) · pgvector · MLflow   Gateway:  API Gateway (Kong/Traefik) ─► REST + GraphQL + WebSocket   Apps:     Web (React + R3F 3D) · Mobile PWA · Grafana (engineering)   Integr.:  ERP/MES connectors, webhooks, notifications (email/SMS/WhatsApp)

2. Services

Service

Responsibility

Store

Tech

edge-gateway

Protocol connectors, normalisation, buffer

SQLite

Python asyncio (asyncua, pymodbus, PLC4X via sidecar)

ingest

Kafka → validated batches → Timescale

TimescaleDB

Python / Go

twin

Twin models, live state, relationships, WebSocket push

Redis, PostgreSQL

FastAPI

asset

Hierarchy, records, documents, QR

PostgreSQL, S3/MinIO

FastAPI

alarm

Rules engine, alarm lifecycle, notifications

PostgreSQL

FastAPI + Kafka consumer

maintenance

Work orders, PM schedules, inventory

PostgreSQL

FastAPI + scheduler

analytics

KPIs, anomaly, RUL, simulations

Timescale, MLflow

Python, scikit-learn, PyTorch

copilot

LLM agent, tools, RAG

pgvector

FastAPI + Claude API

identity

SSO, RBAC

Keycloak DB

Keycloak

web

UI, 3D viewer

—

React, TypeScript, React-Three-Fiber, ECharts

3. Data flow (telemetry)

Connector reads/subscribes to a tag → raw value.

Normalizer maps it to the canonical message {site, asset_id, metric, value, unit, quality, ts}.

Edge publishes to MQTT twinops/{site}/{asset_id}/telemetry (batched every 1 s, QoS 1).

EMQX bridges to Kafka telemetry.raw (key = asset_id, preserving per-asset order).

Consumers: ingest writes to Timescale; twin updates Redis and pushes over WebSocket; alarm evaluates rules; analytics feeds windows to models.

Continuous aggregates build 1-min and 1-hour rollups.

4. Deployment options

Option

For

Notes

Cloud SaaS

Most customers

AWS Mumbai / Azure Central India, EKS/AKS, managed Postgres

On-prem

Defence, pharma, PSU

K3s / RKE2 on 3 nodes, same Helm charts, local LLM gateway option

Edge-only

Small plants

Single IPC running the full stack via docker compose

Sizing (pilot, 400 tags at 1 s): edge IPC with 4 cores, 8 GB RAM, 256 GB SSD. Cluster: 3 nodes × 8 vCPU/32 GB; DB 500 GB SSD.

5. Security architecture

Zones and conduits per IEC 62443: OT zone, DMZ (edge), cloud zone. Only defined conduits allowed.

Device identity: X.509 per edge gateway, mTLS to EMQX, certificate rotation every 90 days.

Users: Keycloak OIDC, MFA for admins, RBAC roles (Admin, Plant Head, Maint Manager, Technician, Engineer, Viewer) scoped by site.

Data: TLS 1.2+ in transit, AES-256 at rest, per-tenant schema or row-level security.

Write-back (Phase 3): separate command service, two-person approval, tag allow-list, signed commands, audit.

Monitoring: Prometheus, Grafana, Loki, OpenTelemetry tracing; SIEM export.

6. Key decisions (ADRs)

#

Decision

Reason

ADR-01

MQTT at the edge, Kafka in the core

MQTT suits unreliable plant links; Kafka gives replay and fan-out

ADR-02

TimescaleDB for time-series

SQL joins with asset data, compression, continuous aggregates

ADR-03

Own JSON twin templates, exportable to AAS / DTDL

Simple for MVP, standards-compatible

ADR-04

Web 3D (React-Three-Fiber, glTF) over Unity

Runs in any browser and on mobile, no plugins

ADR-05

Read-only OT access in MVP

Safety and faster customer approval

ADR-06

Python for edge and services

Mature industrial libraries and one language for ML