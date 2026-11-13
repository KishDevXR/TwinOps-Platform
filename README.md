# TwinOps — Digital-Twin Asset Management Platform

TwinOps is a next-generation industrial digital twin and asset management platform for discrete manufacturing and industrial plants. Built following ISA-95 equipment hierarchies, ISA-18.2 alarm management standards, ISO 22400 / SEMI E10 OEE formulations, and a strictly read-only OT safety architecture.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │    React-Three-Fiber 3D Web UI       │
                      │    Port 5173                         │
                      └──────────────────┬───────────────────┘
                                         │ WebSocket / REST
  ┌──────────────────────────────────────┼──────────────────────────────────────┐
  │                                      │                                      │
┌─▼─────────────┐      ┌─────────────────▼───┐                 ┌────────────────▼───┐
│ Asset Service │      │  Live Twin Service  │                 │  Telemetry Ingest  │
│ Port 8002     │      │  Port 8003          │                 │  Port 8001         │
└───────┬───────┘      └──────────┬──────────┘                 └──────────┬─────────┘
        │                         │                                       │
  ┌─────┴─────────────────────────┴───────────────────────────────────────┴─────┐
  │                            TimescaleDB / SQLite                             │
  └─────┬─────────────────────────┬───────────────────────────────────────┬─────┘
        │                         │                                       │
┌───────▼───────┐      ┌──────────▼──────────┐                 ┌──────────▼─────────┐
│ Alarms Engine │      │  Maintenance / CMMS │                 │  Analytics & ML    │
│ Port 8004     │      │  Port 8005          │                 │  Port 8006         │
└───────┬───────┘      └──────────┬──────────┘                 └──────────┬─────────┘
        │                         │                                       │
  ┌─────┴─────────────────────────┴───────────────────────────────────────┴─────┐
  │                    AI Maintenance Copilot (Port 8007)                      │
  │                    RAG Manuals · Grounded Citations · Guardrails            │
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         │ OT Boundary
                               ┌─────────▼──────────┐
                               │ Plant Simulator    │
                               │ 25 Assets, 2 Lines │
                               └────────────────────┘
```

---

## Quick Start

### 1. Manual Commands Runbook
For step-by-step instructions to run each microservice, the virtual plant simulator, the 3D web frontend, and manual API testing via `curl`, see:
👉 **[Manual Commands Runbook (docs/MANUAL_COMMANDS.md)](docs/MANUAL_COMMANDS.md)**

### 2. Run All Tests
```bash
make test
```
- **Backend (pytest)**: 55/55 passed (`tests/`)
- **Frontend (vitest)**: 9/9 passed (`web/`)

### 3. Start Development Services
```bash
make dev
```

### 4. Code Quality & Lint
```bash
make lint
```

---

## Microservices Port Directory

| Service | Port | Health Check |
| :--- | :--- | :--- |
| **Telemetry Ingest** | `8001` | `http://localhost:8001/healthz` |
| **Asset Registry** | `8002` | `http://localhost:8002/healthz` |
| **Live Digital Twin** | `8003` | `http://localhost:8003/healthz` |
| **Alarms Engine (ISA-18.2)** | `8004` | `http://localhost:8004/healthz` |
| **Maintenance CMMS** | `8005` | `http://localhost:8005/healthz` |
| **Analytics & ML Models** | `8006` | `http://localhost:8006/healthz` |
| **AI Maintenance Copilot** | `8007` | `http://localhost:8007/health` |
| **3D Web Viewer Frontend** | `5173` | `http://localhost:5173` |
