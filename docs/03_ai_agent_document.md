TwinOps — AI Agent Document

Digital Twin Asset Management Platform

13 November 2026

This document has two parts. Part A specifies the AI agents inside the product. Part B is an instruction file for the AI coding agents (Claude Code, etc.) that will help build it. Copy Part B into the repo as AGENTS.md / CLAUDE.md.

Part A — In-product AI agents

A1. Agent overview

Agent

Trigger

Inputs

Output

Autonomy

Anomaly Agent

Streaming, every 1 min per asset

Telemetry window, asset template baselines

Anomaly score, top contributing signals, event

Automatic

RUL Agent

Hourly

Run-hours, vibration/temperature trends, failure history

RUL estimate (days) with confidence band

Automatic

Diagnosis Agent

When an anomaly or alarm fires

Event, recent telemetry, manuals, past work orders

Probable cause, recommended action, references

Suggests only

Work Order Agent

Diagnosis confidence ≥ 0.7 or critical alarm

Diagnosis output, PM plans, spare stock, technician skills

Draft work order (title, steps, parts, priority)

Draft; human approves

Maintenance Copilot

User chat (web or mobile)

Question plus tool access

Answer with citations, charts, links

Read-only tools

Report Agent

Daily 07:00 / weekly

KPIs, alarms, work orders

Shift and weekly reports (PDF, email)

Automatic

A2. Copilot tools (function calling)

Tool

Purpose

Access

search_assets(query, site)

Find assets by name, type or location

Read

get_asset(asset_id)

Asset record and twin state

Read

get_telemetry(asset_id, metric, from, to, agg)

Time-series data

Read

list_alarms(asset_id?, status?, from?)

Alarms and events

Read

list_work_orders(asset_id?, status?)

Maintenance history

Read

search_docs(query, asset_type?)

RAG over manuals, SOPs, past root-cause reports

Read

get_kpis(scope, period)

OEE, MTBF, MTTR, energy

Read

run_simulation(asset_id, params)

What-if run on the twin

Read (sandbox)

draft_work_order(...)

Create a draft for human approval

Write (draft only)

Example questions: “Why did CNC-03 stop last night?” · “Which pumps are likely to fail this month?” · “Show compressor energy per shift this week.” · “What is the bearing replacement procedure for PUMP-02?”

A3. Guardrails

No machine control. No agent can write to PLC or SCADA. There is no such tool.

Agents see only sites the user’s role allows (RBAC enforced in the tool layer, not the prompt).

Every answer cites its data (tag, time range, document page). If data is missing, the agent says so and does not guess.

Safety-related steps (LOTO, confined space, electrical) always quote the plant SOP and add “verify with a supervisor.”

All prompts, tool calls and outputs are logged for audit and evaluation.

Cost and latency limits: max 8 tool calls per question, p95 response < 10 s.

A4. Models and data

LLM: Claude (via API, India-region or on-prem gateway); a smaller model for classification and summaries.

Embeddings and vector store: pgvector in PostgreSQL. Chunk manuals by section; store asset type and page number as metadata.

Anomaly: Isolation Forest + rolling z-score at MVP; LSTM autoencoder from R2.

RUL: Weibull / survival model at MVP; gradient-boosted or LSTM once there are 10+ failures per asset type.

MLOps: MLflow model registry, a model per asset type, weekly retraining, drift monitoring.

A5. Evaluation

Agent

Metric

Target

Anomaly

Precision / recall on labelled events

≥ 0.7 / ≥ 0.8

RUL

Mean absolute error on validation failures

≤ 20% of true life

Diagnosis

Expert-rated correct top-3 cause

≥ 70%

Copilot

Answers grounded with valid citations (golden set of 100 questions)

≥ 95%

Copilot

Hallucinated tag values or assets

0

Part B — Instructions for AI coding agents (AGENTS.md)

# TwinOps — agent instructions## ProjectDigital-twin asset management platform for industrial plants.Read /docs: PRD, Architecture, Design, Test Cases before changing code.## Repo layout/edge          Edge gateway + protocol connectors (Python asyncio)/services      Backend microservices (FastAPI): asset, twin, telemetry,               alarm, maintenance, analytics, copilot/web           React + TypeScript + React-Three-Fiber frontend/ml            Models, training notebooks, MLflow/simulator     Virtual plant (machine data generator)/deploy        docker-compose (dev), Helm charts (prod)/docs          Specs## Commandsmake dev        # docker compose up: mqtt, db, kafka, services, web, simulatormake test       # unit tests (pytest, vitest)make e2e        # Playwright end-to-end against the simulatormake lint       # ruff, mypy, eslint, prettier## Rules- Never add code that writes to PLC/SCADA unless the task explicitly says so  and it goes through the write-back approval service.- All telemetry follows the canonical message schema in docs/design.md §3.  Do not invent new fields.- Every new requirement ID (e.g. MNT-04) gets tests named test_<req_id>_*.- Use the simulator for all tests; never hard-code real plant IPs or credentials.- DB changes only via Alembic migrations. Time-series tables are  TimescaleDB hypertables.- API changes: update the OpenAPI spec and regenerate the TS client.- Keep services stateless; state lives in Postgres/Timescale/Redis.- Secrets come from env vars / Vault, never from code.- Before finishing: make lint && make test must pass.## Definition of doneCode + tests + docs updated + passes CI + linked to requirement ID.

Suggested build order for agent tasks: (1) simulator → (2) canonical schema and MQTT topics → (3) telemetry ingest service + Timescale → (4) asset service → (5) twin service + WebSocket → (6) web 3D viewer → (7) alarms → (8) maintenance → (9) analytics → (10) copilot.