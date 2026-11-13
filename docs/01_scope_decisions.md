TwinOps — Scope Decisions

Digital Twin Asset Management Platform · Development Pack

13 November 2026

This document set is the build baseline for the platform: Scope Decisions, PRD, AI Agent Document, Architecture, Design Document and Test Cases. Working name used throughout: TwinOps.

1. Final industry selection

Phase

Industry

Reference plant (replica)

Why

Pilot (MVP)

Discrete manufacturing: auto-component machining

1 plant, 2 lines: CNC machining centres, conveyor, 6-axis robot cell, air compressor, coolant pump, chiller, energy meters

Large Indian market (auto/ancillary MSMEs), standard protocols, clear ROI from OEE and downtime

Phase 2

Water and wastewater treatment

Intake pumps, clarifier, filters, blowers, dosing pumps, tanks, flow and level meters

SCADA-heavy, smart-city and government demand, continuous process twin

Phase 3

Power and utilities (substation / captive power)

Transformers, breakers, DG sets, solar inverters

Adds DNP3, IEC 104 and IEC 61850 protocols

Phase 3

Pharma / process

Reactors, HVAC/AHU, cleanrooms

Needs 21 CFR Part 11 audit trail compliance

Pilot asset list (25 assets, about 400 tags): 6 CNC machines, 2 conveyors, 2 robots, 2 air compressors, 4 pumps, 1 chiller, 2 AHUs, 6 energy meters.

2. Final protocol list

Tier

Protocol

Typical source

Connector implementation

MVP

OPC UA (client, subscriptions)

SCADA servers, modern PLCs, CNCs

Eclipse Milo / asyncua

MVP

Modbus TCP and RTU (over gateway)

Energy meters, VFDs, older PLCs

pymodbus / Go modbus

MVP

MQTT 3.1.1/5 + Sparkplug B

IIoT sensors, edge devices

EMQX / Mosquitto

MVP

Siemens S7 (S7comm)

S7-300/400/1200/1500

Apache PLC4X

MVP

MTConnect

CNC machines (Fanuc, Haas, Mazak)

HTTP agent client

Phase 2

EtherNet/IP (CIP)

Allen-Bradley PLCs

PLC4X / pycomm3

Phase 2

BACnet/IP

HVAC, AHUs, chillers

BAC0

Phase 2

Historian: AVEVA PI Web API, REST, SQL, CSV

Existing historians, MES

Pull connectors

Phase 3

DNP3, IEC 60870-5-104, IEC 61850

Power and utility RTUs, IEDs

OpenDNP3, lib60870, libIEC61850

Phase 3

Profinet, Profibus

Field networks

Hardware gateway (HMS Anybus, Moxa) to OPC UA or Modbus

Rule: every connector outputs the same canonical message (see Design Document §3). Field protocols never reach the cloud directly; only the edge gateway talks to them.

3. SCADA access model (final)

Principle: read-only, no inbound connections, everything passes through an industrial DMZ, following the Purdue model and IEC 62443.

Connection point: the SCADA’s own OPC UA server (Ignition, Siemens WinCC OA / WinCC Unified, AVEVA System Platform, GE iFIX, Rockwell FactoryTalk) at Purdue Level 3. If OPC UA is unavailable, use the historian (Level 3) or a read-only database view.

Edge gateway location: Level 3.5 (DMZ), on an industrial PC with dual NICs: an OT-side NIC and an IT-side NIC.

Firewall rules: OT side, allow edge → SCADA on TCP 4840 (OPC UA) and 502 (Modbus) only. IT side, allow edge → cloud MQTT over TLS on 8883 and HTTPS on 443, outbound only. No inbound ports.

Accounts: a dedicated OPC UA service account with a read-only role, X.509 certificate authentication, and the Sign & Encrypt security policy (Basic256Sha256 or newer).

Write-back (setpoints and commands): disabled in MVP. From Phase 3 it requires a two-person approval workflow, an allow-list of tags, rate limits, and a full audit log.

Data rate: 1 s for critical tags, 5–60 s for others, using deadband/report-by-exception. The edge buffers 7 days locally.

Customer access checklist (collect before site visit):

☐ SCADA vendor, version and whether an OPC UA server is licensed and enabled

☐ Tag list export (CSV) with descriptions, units and engineering ranges

☐ Network diagram and IP plan, plus a DMZ slot for the edge gateway

☐ Read-only service account and certificate exchange

☐ Firewall change request approved by plant IT and OT

☐ Asset register (Excel) with make, model, serial number, install date and criticality

☐ Maintenance history (last 2 years) and current preventive maintenance schedules

☐ CAD or layout drawings for the 3D replica

☐ Named plant contacts: OT engineer, maintenance head, IT security