# TwinOps — Agent Instructions

## Project
Digital-twin asset management platform for industrial plants.
Read `/docs`: PRD, Architecture, Design, Test Cases before changing code.

## Repo Layout
- `/edge` — Edge gateway + protocol connectors (Python asyncio)
- `/services` — Backend microservices (FastAPI): asset, twin, telemetry, alarm, maintenance, analytics, copilot
- `/web` — React + TypeScript + React-Three-Fiber frontend
- `/ml` — Models, training notebooks, MLflow
- `/simulator` — Virtual plant (machine data generator)
- `/deploy` — Docker-compose (dev), Helm charts (prod)
- `/docs` — System specifications and design baselines

## Commands
```bash
make dev        # docker compose up: mqtt, db, kafka, services, web, simulator
make test       # unit tests (pytest, vitest)
make e2e        # Playwright end-to-end against the simulator
make lint       # ruff, mypy, eslint, prettier
```

## Rules
- Never add code that writes to PLC/SCADA unless the task explicitly says so and it goes through the write-back approval service.
- All telemetry follows the canonical message schema in `docs/design.md` §3. Do not invent new fields.
- Every new requirement ID (e.g. MNT-04) gets tests named `test_<req_id>_*`.
- Use the simulator for all tests; never hard-code real plant IPs or credentials.
- DB changes only via Alembic migrations. Time-series tables are TimescaleDB hypertables.
- API changes: update the OpenAPI spec and regenerate the TS client.
- Keep services stateless; state lives in Postgres/Timescale/Redis.
- Secrets come from env vars / Vault, never from code.
- Before finishing: `make lint && make test` must pass.

## Definition of Done
Code + tests + docs updated + passes CI + linked to requirement ID.

## Suggested Build Order
1. Simulator (`/simulator`)
2. Canonical schema and MQTT topics (`/services/common`)
3. Telemetry ingest service + Timescale (`/services/telemetry`)
4. Asset service (`/services/asset`)
5. Twin service + WebSocket (`/services/twin`)
6. Web 3D viewer (`/web`)
7. Alarms & rules engine (`/services/alarm`)
8. Maintenance / CMMS (`/services/maintenance`)
9. Analytics, Anomaly & RUL (`/services/analytics`, `/ml`)
10. AI Maintenance Copilot (`/services/copilot`)
