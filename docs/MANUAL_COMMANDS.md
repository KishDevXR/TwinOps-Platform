# TwinOps — Manual Operations & Command Runbook

This runbook provides complete, copy-pasteable manual commands to configure, start, test, query, and troubleshoot all components of the **TwinOps Digital Twin Asset Management Platform**.

---

## 1. System Architecture & Port Mapping

| Service / Component | Protocol / Port | Entrypoint | Description |
| :--- | :--- | :--- | :--- |
| **Virtual Plant Simulator** | OT / Internal | `simulator.cli` | Physics-lite plant simulator (25 assets, ~400 tags) |
| **Modbus TCP Server** | TCP `5020` | `simulator.modbus_server` | Modbus holding register simulator |
| **OPC UA Server** | TCP `48400` | `simulator.opcua_server` | OPC UA server with industrial tag hierarchy |
| **Telemetry Ingest Service** | HTTP `8001` | `services.telemetry.main` | High-throughput batch ingest & time-series query API |
| **Asset Registry Service** | HTTP `8002` | `services.asset.main` | ISA-95 equipment hierarchy & CSV onboarding |
| **Live Digital Twin Service** | HTTP/WS `8003` | `services.twin.main` | Live state store, what-if sandbox, WebSocket broadcast |
| **Alarms & Rules Engine** | HTTP `8004` | `services.alarm.main` | ISA-18.2 threshold evaluation, hysteresis & shelving |
| **Maintenance / CMMS** | HTTP `8005` | `services.maintenance.main` | Work order lifecycles, PM plans & mobile offline sync |
| **Analytics & ML Service** | HTTP `8006` | `services.analytics.main` | OEE calculation, Isolation Forest anomaly & Weibull RUL |
| **AI Maintenance Copilot** | HTTP `8007` | `services.copilot.main` | Natural language Q&A, RAG manuals & safety guardrails |
| **Web 3D Twin Viewer** | HTTP `5173` | `web/` (Vite + React) | React-Three-Fiber interactive 3D plant dashboard |
| **MQTT Broker (Optional)** | TCP `1883` | EMQX / Mosquitto | Pub/Sub event bus for telemetry and twin updates |

---

## 2. Environment Setup & Prerequisites

### 2.1 Prerequisites
- **Python**: Version 3.11+ (Python 3.13 supported)
- **Node.js**: Version 18+ (Node v20/v22 LTS recommended) and `npm`
- **Package Manager**: `uv` (recommended for ultra-fast installs) or standard `pip`
- **Database**: SQLite (default zero-config local `twinops.db`) or PostgreSQL / TimescaleDB

### 2.2 Python Environment Setup

#### Option A: Using `uv` (Fastest)
```powershell
# Windows (PowerShell)
uv venv .venv
uv pip install -e .
uv pip install numpy scikit-learn scipy
```

```bash
# Linux / macOS (Bash)
uv venv .venv
source .venv/bin/activate
uv pip install -e .
uv pip install numpy scikit-learn scipy
```

#### Option B: Using Standard `python -m venv`
```powershell
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
pip install numpy scikit-learn scipy
```

```bash
# Linux / macOS (Bash)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install numpy scikit-learn scipy
```

### 2.3 Web Frontend Setup
```bash
# Navigate to web directory and install npm packages
cd web
npm install
cd ..
```

---

## 3. Running Services Manually

To run the full stack manually, open separate terminal windows for each service. Ensure the virtual environment is activated in each terminal.

### 3.1 Virtual Plant Simulator (Machine Generator)
Generates real-time synthetic physics telemetry for 25 machines across 2 lines.

```powershell
# Windows (PowerShell)
.venv\Scripts\python.exe -m simulator.cli --site PUNE-01 --interval 1.0 --dump-stdout

# Run with fault injection (e.g. bearing wear on PUMP-01)
.venv\Scripts\python.exe -m simulator.cli --site PUNE-01 --interval 1.0 --inject PUMP-01:bearing_wear:0.5

# Run with field protocols enabled (Modbus port 5020, OPC UA port 48400)
.venv\Scripts\python.exe -m simulator.cli --site PUNE-01 --enable-modbus --enable-opcua
```

```bash
# Linux / macOS (Bash)
python -m simulator.cli --site PUNE-01 --interval 1.0 --dump-stdout
```

---

### 3.2 Telemetry Ingest Service (Port 8001)
Ingests telemetry, maintains batch write buffers, and exposes 1-minute rollup aggregations.

```powershell
# Windows (PowerShell)
.venv\Scripts\python.exe -m services.telemetry.main
```

```bash
# Linux / macOS (Bash)
python -m services.telemetry.main
# Or via uvicorn directly:
uvicorn services.telemetry.main:app --host 0.0.0.0 --port 8001 --reload
```

---

### 3.3 Asset Registry Service (Port 8002)
Manages the ISA-95 equipment hierarchy, tag bindings, asset metadata, and bulk CSV onboarding.

```powershell
# Windows (PowerShell)
.venv\Scripts\python.exe -m services.asset.main
```

```bash
# Linux / macOS (Bash)
uvicorn services.asset.main:app --host 0.0.0.0 --port 8002 --reload
```

---

### 3.4 Live Digital Twin Service (Port 8003)
Maintains the real-time twin state store, derived KPIs, what-if sandbox, and WebSocket push stream.

```powershell
# Windows (PowerShell)
.venv\Scripts\python.exe -m services.twin.main
```

```bash
# Linux / macOS (Bash)
uvicorn services.twin.main:app --host 0.0.0.0 --port 8003 --reload
```

---

### 3.5 Alarms & Rules Engine Service (Port 8004)
Evaluates ISA-18.2 high/low thresholds, rate-of-change, transient delay filtering, hysteresis clearance, and alarm shelving.

```powershell
# Windows (PowerShell)
.venv\Scripts\python.exe -m services.alarm.main
```

```bash
# Linux / macOS (Bash)
uvicorn services.alarm.main:app --host 0.0.0.0 --port 8004 --reload
```

---

### 3.6 Maintenance & CMMS Service (Port 8005)
Manages corrective work orders, calendar/meter PM plans, parts deduction, and mobile offline sync.

```powershell
# Windows (PowerShell)
.venv\Scripts\python.exe -m services.maintenance.main
```

```bash
# Linux / macOS (Bash)
uvicorn services.maintenance.main:app --host 0.0.0.0 --port 8005 --reload
```

---

### 3.7 Analytics & ML Service (Port 8006)
Runs SEMI E10 / ISO 22400 OEE formulation, Isolation Forest anomaly scoring, and Weibull RUL prediction.

```powershell
# Windows (PowerShell)
.venv\Scripts\python.exe -m services.analytics.main
```

```bash
# Linux / macOS (Bash)
uvicorn services.analytics.main:app --host 0.0.0.0 --port 8006 --reload
```

---

### 3.8 AI Maintenance Copilot Service (Port 8007)
Provides natural-language Q&A with function-calling over equipment telemetry, RAG manuals, and safety guardrails.

```powershell
# Windows (PowerShell)
.venv\Scripts\python.exe -m services.copilot.main
```

```bash
# Linux / macOS (Bash)
uvicorn services.copilot.main:app --host 0.0.0.0 --port 8007 --reload
```

---

### 3.9 Web 3D Viewer Frontend (Port 5173)
Launches the Vite dev server with React-Three-Fiber 3D plant model, side panel, scrubber, and sandbox.

```bash
# From workspace root
npm --prefix web run dev

# Or from web/ directory
cd web
npm run dev
```

*Open your browser at `http://localhost:5173`.*

---

## 4. Makefile Shortcuts

The repository includes a root `Makefile` for streamlined one-command tasks:

```bash
make test         # Run complete backend (pytest) + frontend (vitest) test suites
make test-backend # Run backend pytest suite (55 tests)
make test-web     # Run frontend vitest suite (9 tests)
make lint         # Run ruff check and code formatting verifications
make simulator    # Start virtual plant simulator with stdout dump
make dev          # Start core dev services concurrently
```

---

## 5. Manual Verification & API Testing via cURL

### 5.1 Service Health Checks
```bash
curl -s http://localhost:8001/healthz  # Telemetry Service
curl -s http://localhost:8002/healthz  # Asset Service
curl -s http://localhost:8003/healthz  # Live Twin Service
curl -s http://localhost:8004/healthz  # Alarm Service
curl -s http://localhost:8005/healthz  # Maintenance Service
curl -s http://localhost:8006/healthz  # Analytics Service
curl -s http://localhost:8007/health   # Copilot Service
```

### 5.2 Asset Registry & ISA-95 Tree
```bash
# List all registered assets
curl -s http://localhost:8002/api/v1/assets

# Get ISA-95 hierarchical site tree
curl -s http://localhost:8002/api/v1/tree?site=PUNE-01
```

### 5.3 Live Twin & What-If Simulation
```bash
# Get live digital twin state for PUMP-01
curl -s http://localhost:8003/api/v1/twins/PUMP-01

# Run What-If Simulation (+20% pump speed)
curl -s -X POST http://localhost:8003/api/v1/simulations \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "PUMP-01", "scenario_name": "Speed Increase", "parameter_deltas": {"speed_pct": 20.0}}'
```

### 5.4 Alarms Management (ISA-18.2)
```bash
# List active alarms
curl -s http://localhost:8004/api/v1/alarms?status=active

# Acknowledge an alarm
curl -s -X POST http://localhost:8004/api/v1/alarms/1/ack \
  -H "Content-Type: application/json" \
  -d '{"operator_id": "OP-102", "comment": "Checking spindle coolant line"}'

# Shelve an alarm for 30 minutes
curl -s -X POST http://localhost:8004/api/v1/alarms/1/shelve \
  -H "Content-Type: application/json" \
  -d '{"shelved_by": "OP-102", "duration_minutes": 30, "reason": "Scheduled sensor calibration"}'
```

### 5.5 CMMS Maintenance & Work Orders
```bash
# List open work orders
curl -s http://localhost:8005/api/v1/work-orders?status=open

# Create corrective work order
curl -s -X POST http://localhost:8005/api/v1/work-orders \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "PUMP-01", "title": "Check Mechanical Seal", "priority": "high", "type": "corrective"}'

# Mobile Offline Sync (Batch upload completed checklists)
curl -s -X POST http://localhost:8005/api/v1/sync/offline \
  -H "Content-Type: application/json" \
  -d '{"client_id": "PWA-TECH-01", "synced_at": "2026-11-13T12:00:00Z", "completed_work_orders": []}'
```

### 5.6 Analytics, OEE & RUL
```bash
# Calculate standard benchmark OEE
curl -s -X POST http://localhost:8006/api/v1/analytics/oee \
  -H "Content-Type: application/json" \
  -d '{"planned_time_s": 28800.0, "operating_time_s": 25200.0, "ideal_cycle_time_s": 60.0, "total_count": 400, "good_count": 390, "energy_kwh": 118.0}'

# Get RUL prediction for PUMP-01
curl -s http://localhost:8006/api/v1/analytics/assets/PUMP-01/rul

# Downtime Pareto analysis
curl -s -X POST http://localhost:8006/api/v1/analytics/pareto/downtime \
  -H "Content-Type: application/json" \
  -d '{"events": [{"category": "Mechanical", "duration_minutes": 120.0}, {"category": "Tooling", "duration_minutes": 60.0}, {"category": "Electrical", "duration_minutes": 30.0}]}'
```

### 5.7 AI Maintenance Copilot Chat
```bash
# Ask diagnostic question (Grounded telemetry & alarm response)
curl -s -X POST http://localhost:8007/api/v1/copilot/chat \
  -H "Content-Type: application/json" \
  -H "x-user-id: engineer-01" \
  -H "x-allowed-sites: PUNE-01" \
  -d '{"query": "Why did CNC-03 stop last night?", "site": "PUNE-01"}'

# Query maintenance SOP with safety Lockout/Tagout citation
curl -s -X POST http://localhost:8007/api/v1/copilot/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the procedure for pump bearing replacement?"}'

# Test OT Machine-Control Refusal (Strict read-only safety guardrail)
curl -s -X POST http://localhost:8007/api/v1/copilot/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Set pump speed to 100%"}'
```

---

## 6. Running Automated Test Suites

### 6.1 Complete Backend Test Suite (55 Tests)
```powershell
# Windows (PowerShell)
.venv\Scripts\pytest.exe -v
```

```bash
# Linux / macOS (Bash)
pytest -v
```

### 6.2 Running Individual Test Modules
```powershell
# Step 1 & 2: Simulator & Canonical Telemetry
.venv\Scripts\pytest.exe -v tests/test_simulator.py tests/test_canonical.py tests/test_protocols.py

# Step 3: Telemetry Ingest & Storage
.venv\Scripts\pytest.exe -v tests/test_telemetry.py

# Step 4: Asset Registry & ISA-95 Hierarchy
.venv\Scripts\pytest.exe -v tests/test_asset.py

# Step 5: Live Twin & WebSockets
.venv\Scripts\pytest.exe -v tests/test_twin.py

# Step 7: Alarms & ISA-18.2 Rules Engine
.venv\Scripts\pytest.exe -v tests/test_alarm.py

# Step 8: Maintenance & CMMS
.venv\Scripts\pytest.exe -v tests/test_maintenance.py

# Step 9: Analytics, Anomaly & RUL Models
.venv\Scripts\pytest.exe -v tests/test_analytics.py

# Step 10: AI Maintenance Copilot & Guardrails
.venv\Scripts\pytest.exe -v tests/test_copilot.py

# End-to-End Pipeline Test
.venv\Scripts\pytest.exe -v tests/test_e2e_integration.py
```

### 6.3 Frontend Vitest Suite (9 Tests)
```bash
npm --prefix web run test
```

### 6.4 Linter & Code Formatter
```powershell
# Windows (PowerShell)
.venv\Scripts\ruff.exe check services simulator ml tests
.venv\Scripts\ruff.exe format --check services simulator ml tests

# Auto-format code
.venv\Scripts\ruff.exe format services simulator ml tests
```

```bash
# Linux / macOS (Bash)
ruff check services simulator ml tests
ruff format --check services simulator ml tests
```

---

## 7. Troubleshooting & FAQs

### Q1: "Database locked" or database reset
TwinOps uses an async SQLite database (`twinops.db`) by default in development mode.
To reset to clean factory state:
```powershell
# Windows (PowerShell)
Remove-Item twinops.db -ErrorAction SilentlyContinue
```
```bash
# Linux / macOS (Bash)
rm -f twinops.db
```
The database will automatically re-create and seed all pilot assets, lines, and default alarm rules upon service start.

### Q2: Port already in use (e.g. Port 8001 / 8003)
Find and terminate any orphaned Python processes:
```powershell
# Windows (PowerShell)
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
```
```bash
# Linux / macOS (Bash)
pkill -f "python -m services"
```

### Q3: Running without an active MQTT broker
All TwinOps microservices include fallback polling, HTTP batch ingestion endpoints (`POST /api/v1/telemetry/batch`), and direct in-memory state stores. An active external MQTT broker is optional for local development and testing.
