TwinOps — Product Requirements Document

Digital Twin Asset Management Platform

13 November 2026

1. Problem

Plants run assets until they fail. Data is locked in SCADA, maintenance lives in Excel or paper, and nobody has a single live view of asset health. Unplanned downtime costs 5–20% of capacity.

2. Vision

One platform that connects every machine, mirrors the plant as a live 3D digital twin, and turns sensor data into maintenance actions.

3. Goals and success metrics (pilot, 6 months after go-live)

Goal

Metric

Target

Connect machines fast

Time to onboard a new asset

< 30 min

Reduce downtime

Unplanned downtime

−20%

Improve maintenance

PM compliance

> 90%

Predict failures

Failures predicted ≥ 24 h ahead

> 60%

Adoption

Weekly active technicians

> 80%

Reliability

Platform uptime

99.5%

4. Users and personas

Persona

Needs

Plant Head

KPIs (OEE, downtime, cost), plant overview

Maintenance Manager

Work orders, PM plans, spare parts, asset history

Technician (mobile)

Assigned jobs, checklists, scan QR to see asset, close job with photos

Process / OT Engineer

Connectors, tag mapping, alarms, trends

Reliability Engineer / Data Scientist

Anomalies, RUL, root cause, what-if simulation

Admin

Users, roles, sites, integrations

5. Scope

In MVP: connectivity (MVP protocols), asset registry, live 3D twin of the pilot plant, alarms, work orders, PM scheduling, KPIs, anomaly detection, AI maintenance copilot (read-only).

Out of MVP: write-back to machines, ERP two-way sync, AR, multi-tenant SaaS billing, Phase 2/3 protocols.

6. Functional requirements

6.1 Connectivity and middleware (CON)

CON-01 Edge gateway supports OPC UA, Modbus TCP/RTU, MQTT/Sparkplug B, S7, MTConnect.

CON-02 Connectors are configured from the UI (endpoint, credentials, polling rate, tag list) without code.

CON-03 Bulk tag import from CSV, with mapping to asset and canonical metric name.

CON-04 Store-and-forward: buffer ≥ 7 days on network loss and replay in order.

CON-05 Device health: connection state, last value time, error counts.

CON-06 Data-quality flags (good, bad, uncertain, stale) on every value.

6.2 Asset management (AST)

AST-01 ISA-95 hierarchy: Enterprise → Site → Area → Line → Asset → Component.

AST-02 Asset record: make, model, serial, install date, criticality (A/B/C), warranty, cost, documents, photos, QR code.

AST-03 Asset lifecycle states: Planned, Installed, Operating, Under Maintenance, Idle, Decommissioned.

AST-04 Excel import of the asset register.

AST-05 Full asset history: telemetry, alarms, work orders, changes.

6.3 Maintenance (MNT)

MNT-01 Work orders: create, assign, prioritise, track (Open → Assigned → In Progress → On Hold → Completed → Closed).

MNT-02 Checklists, labour time, spare parts used, photo attachments.

MNT-03 Preventive maintenance by calendar (e.g. every 30 days) or by meter (e.g. every 500 run-hours).

MNT-04 Condition-based maintenance: a rule (e.g. vibration > 7 mm/s for 10 min) auto-creates a work order.

MNT-05 Spare-parts inventory with reorder alerts.

6.4 Digital twin (TWN)

TWN-01 Every asset has a twin: static properties, live state, derived KPIs, and relationships.

TWN-02 Live state updates in the UI within 2 s of the field value changing.

TWN-03 3D plant replica: navigate, click an asset to see live values, colour by status (green/amber/red/grey).

TWN-04 Historical playback of any time window, at 1×–60× speed.

TWN-05 What-if simulation: change load or speed and see predicted temperature, energy and RUL impact.

TWN-06 Twin models are defined as templates per asset type (e.g. “CNC Machine”), reusable across plants.

6.5 Alarms and events (ALM)

ALM-01 Threshold, rate-of-change, and stale-data alarms with severity levels.

ALM-02 Acknowledge, shelve and comment on alarms. Alarm history follows ISA-18.2.

ALM-03 Notifications via email, SMS and WhatsApp/Teams, with escalation.

6.6 Analytics and AI (ANL)

ANL-01 KPIs: OEE (availability × performance × quality), MTBF, MTTR, energy per part.

ANL-02 Anomaly detection per asset, with a score from 0 to 1 and contributing signals.

ANL-03 Remaining Useful Life estimates for rotating assets (pumps, compressors, spindles).

ANL-04 AI Maintenance Copilot: natural-language Q&A over assets, manuals and history (see AI Agent Document).

ANL-05 Dashboards and trend charts, with CSV/PDF export.

6.7 Platform (PLT)

PLT-01 SSO (OIDC/SAML) and role-based access control scoped by site.

PLT-02 Audit log of every create, update and delete.

PLT-03 REST API and webhooks for ERP/MES integration.

PLT-04 Mobile-responsive web app, offline mode for technicians (PWA).

7. Non-functional requirements

Area

Requirement

Scale

50,000 tags per site, 100,000 values/s per cluster

Latency

Field to UI p95 < 2 s; API p95 < 300 ms

Retention

Raw 90 days, 1-min rollups 2 years, 1-hour rollups 10 years

Availability

99.5% cloud; edge runs autonomously when offline

Security

IEC 62443-3-3 SL2, OWASP ASVS L2, TLS 1.2+, encryption at rest

Deployment

Cloud (AWS/Azure India regions) or fully on-prem

Data residency

Customer data stays in India by default (DPDP Act 2023)

8. Release plan

Release

Timing

Content

R0 PoC

Month 2

Simulator, MQTT, TimescaleDB, basic 3D view

R1 MVP

Month 6

All MVP requirements at one pilot plant

R2

Month 9

AI copilot, RUL, what-if, mobile offline

R3

Month 12

Phase 2 protocols, water-treatment template, ERP integration

9. Assumptions and open questions

Pilot customer gives read-only OPC UA access to SCADA (Scope Decisions §3).

3D models are built from layout drawings plus a generic parametric machine library.

Open: licensing model (per asset vs per site); preferred cloud provider.