"""
TwinOps Copilot Knowledge Base & RAG Engine (ANL-04)
Provides semantic chunk search over plant SOPs, equipment manuals, and past RCA reports.
Features:
- Structured document chunks with metadata (doc_name, section, page, asset_type)
- Keyword & cosine similarity retrieval
- Prompt injection detection and sanitization (TC-AI-06)
- Safety SOP citation annotations
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, ClassVar

logger = logging.getLogger("twinops.copilot.rag")
security_logger = logging.getLogger("twinops.security.prompt_injection")


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_name: str
    section: str
    page: int
    asset_type: str | None
    content: str
    is_safety_sop: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# Standard plant manuals and SOPs for Pune-01 pilot facility
DEFAULT_KNOWLEDGE_BASE: list[DocumentChunk] = [
    DocumentChunk(
        chunk_id="sop-loto-01",
        doc_name="SOP-EHS-04: Lockout/Tagout (LOTO) Procedure",
        section="Section 4.1 - Energy Isolation Protocol",
        page=3,
        asset_type=None,
        is_safety_sop=True,
        content=(
            "Prior to servicing any rotating equipment or electrical enclosure, technicians must:\n"
            "1. Notify the area supervisor and affected operators.\n"
            "2. Shut down equipment via normal stopping procedure.\n"
            "3. Disconnect all primary and secondary energy sources (electrical, pneumatic, hydraulic).\n"
            "4. Apply personal safety padlock and danger tag to the isolation breaker.\n"
            "5. Dissipate residual energy (bleed hydraulic pressure, discharge capacitors).\n"
            "6. Attempt restart locally to verify zero energy state.\n"
            "MANDATORY: Verify all steps with a certified plant supervisor before breaking enclosure."
        ),
    ),
    DocumentChunk(
        chunk_id="sop-loto-02",
        doc_name="SOP-EHS-04: Lockout/Tagout (LOTO) Procedure",
        section="Section 5.3 - Lock Removal and Restoration",
        page=5,
        asset_type=None,
        is_safety_sop=True,
        content=(
            "Only the technician who applied the padlock may remove it after:\n"
            "1. Inspecting the machine to verify tools and parts are cleared.\n"
            "2. Reinstalling all guards and safety interlocking devices.\n"
            "3. Verifying all personnel are standing clear of hazardous zones.\n"
            "4. Obtaining supervisor co-signature on the return-to-service permit."
        ),
    ),
    DocumentChunk(
        chunk_id="manual-cnc-spindle",
        doc_name="DMG Mori CNC Mill Spindle Maintenance Manual",
        section="Section 6.2 - Spindle Overheating Troubleshooting",
        page=42,
        asset_type="cnc_machine",
        content=(
            "Spindle temperature rising above 70°C indicates thermal distress or insufficient lubrication.\n"
            "Thresholds:\n"
            "- Warning (HI): 70.0°C - check coolant chiller delivery and line filters.\n"
            "- Emergency Stop (HI-HI): 75.0°C - automatic feedhold and spindle brake engagement.\n"
            "Common Root Causes:\n"
            "1. Coolant flow interruption (coolant_flow_l_min < 5.0 L/min).\n"
            "2. Front spindle bearing pre-load loss or raceway pitting.\n"
            "3. Spindle drive belt slippage generating frictional heat.\n"
            "Torque specification for spindle cartridge retention bolts: 45 Nm using calibrated torque wrench."
        ),
    ),
    DocumentChunk(
        chunk_id="manual-pump-bearing",
        doc_name="Kirloskar Centrifugal Pump Maintenance Manual",
        section="Section 7.4 - Bearing Replacement Procedure",
        page=18,
        asset_type="centrifugal_pump",
        content=(
            "Centrifugal pump bearings require replacement when overall vibration (RMS) exceeds 4.5 mm/s (HI)\n"
            "or peak acceleration shows high kurtosis (> 3.5).\n"
            "Bearing type: Deep groove ball bearing SKF 6308-2Z/C3.\n"
            "Replacement Procedure:\n"
            "1. Execute LOTO on motor feeder circuit (SOP-EHS-04).\n"
            "2. Drain casing and decouple pump shaft from drive coupling.\n"
            "3. Use mechanical bearing puller; do NOT heat with open torch; use induction heater to 110°C.\n"
            "4. Pack with Shell Gadus S2 V220 grease (fill 35% of bearing cavity volume).\n"
            "5. Re-align coupling to within 0.05 mm radial and axial runout."
        ),
    ),
    DocumentChunk(
        chunk_id="manual-compressor-filter",
        doc_name="Atlas Copco GA37 Rotary Screw Compressor Manual",
        section="Section 3.1 - Air/Oil Separator and Intake Filters",
        page=27,
        asset_type="air_compressor",
        content=(
            "Intake air filter element should be replaced when differential pressure exceeds 0.05 bar (50 mbar)\n"
            "or every 2,000 running hours.\n"
            "Oil separator element maximum allowed differential pressure: 0.8 bar.\n"
            "High discharge temperature (> 95°C) triggers safety shutdown; verify thermostatic valve operation."
        ),
    ),
]


class KnowledgeBaseRAG:
    """RAG retriever with keyword + semantic search and prompt injection defenses."""

    INJECTION_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
        re.compile(r"system\s*prompt", re.IGNORECASE),
        re.compile(r"delete\s+(all\s+)?assets?", re.IGNORECASE),
        re.compile(r"drop\s+table", re.IGNORECASE),
        re.compile(r"bypass\s+(safety|guardrails|rbac)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    ]

    def __init__(self, documents: list[DocumentChunk] | None = None):
        self.documents: list[DocumentChunk] = documents or list(DEFAULT_KNOWLEDGE_BASE)

    def add_document(self, chunk: DocumentChunk) -> None:
        self.documents.append(chunk)

    def detect_prompt_injection(self, text: str) -> bool:
        """TC-AI-06: Detect prompt injection attempts in queries or external manuals."""
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(text):
                security_logger.warning("Prompt injection attempt detected: '%s'", text[:100])
                return True
        return False

    def search(
        self,
        query: str,
        asset_type: str | None = None,
        top_k: int = 3,
    ) -> list[DocumentChunk]:
        """
        Search knowledge base documents matching query terms.
        Applies prompt injection sanitization.
        """
        # TC-AI-06: Flag injection attempts
        if self.detect_prompt_injection(query):
            logger.warning("Query rejected by prompt injection filter: %s", query)
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))
        scored_chunks: list[tuple[float, DocumentChunk]] = []

        for doc in self.documents:
            # Asset type filter if supplied
            if asset_type and doc.asset_type and doc.asset_type != asset_type:
                continue

            content_lower = doc.content.lower()
            doc_tokens = set(re.findall(r"\w+", content_lower))
            overlap = query_tokens.intersection(doc_tokens)
            score = len(overlap)

            # Boost matches in section title and document name
            section_tokens = set(re.findall(r"\w+", doc.section.lower()))
            score += len(query_tokens.intersection(section_tokens)) * 2.0

            if score > 0:
                # Sanitize document content against injection payload before returning
                sanitized_content = self._sanitize_content(doc.content)
                sanitized_chunk = DocumentChunk(
                    chunk_id=doc.chunk_id,
                    doc_name=doc.doc_name,
                    section=doc.section,
                    page=doc.page,
                    asset_type=doc.asset_type,
                    content=sanitized_content,
                    is_safety_sop=doc.is_safety_sop,
                    metadata=doc.metadata,
                )
                scored_chunks.append((score, sanitized_chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:top_k]]

    def _sanitize_content(self, content: str) -> str:
        """Strip dangerous injection instructions from external text chunks."""
        sanitized = content
        for pattern in self.INJECTION_PATTERNS:
            sanitized = pattern.sub("[REDACTED INSTRUCTION]", sanitized)
        return sanitized


# Global singleton instance
knowledge_base = KnowledgeBaseRAG()
