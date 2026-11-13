"""
TwinOps AI Maintenance Copilot REST API Router
Endpoints:
- POST /api/v1/copilot/chat (Chat Q&A with function-calling agent)
- POST /api/v1/copilot/work-orders/{id}/approve (Approve draft work order)
- GET /api/v1/copilot/tools (List tool registry specifications)
- GET /api/v1/copilot/audit-logs (Audit trail for compliance)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from services.copilot.agent import copilot_agent
from services.copilot.tools import UserContext, tool_registry

router = APIRouter(prefix="/api/v1/copilot", tags=["copilot"])


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language question or request")
    site: str = Field(default="PUNE-01", description="Target plant site")
    session_id: str | None = Field(default=None, description="Chat session identifier")


class ChatResponse(BaseModel):
    query: str
    answer: str
    status: str
    citations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApproveWORequest(BaseModel):
    approved_by: str = Field(default="supervisor-01", description="Approving supervisor ID")


@router.post("/chat", response_model=ChatResponse)
async def copilot_chat(
    req: ChatRequest,
    x_user_id: str = Header(default="engineer-01"),
    x_user_role: str = Header(default="maintenance_engineer"),
    x_allowed_sites: str = Header(default="PUNE-01"),
):
    """
    ANL-04: Chat with AI Maintenance Copilot.
    Enforces RBAC, grounded citations, and machine-control refusal guardrails.
    """
    allowed_list = [s.strip() for s in x_allowed_sites.split(",") if s.strip()]
    user_ctx = UserContext(
        user_id=x_user_id,
        role=x_user_role,
        allowed_sites=allowed_list,
    )

    res = await copilot_agent.answer(
        question=req.query,
        user_ctx=user_ctx,
        session_id=req.session_id,
    )

    serialized_calls = [
        {
            "tool_name": tc.tool_name,
            "arguments": tc.arguments,
            "result": tc.result,
            "timestamp": tc.timestamp.isoformat(),
        }
        for tc in res.tool_calls
    ]

    return ChatResponse(
        query=res.question,
        answer=res.answer,
        status=res.status,
        citations=res.citations,
        tool_calls=serialized_calls,
        metadata=res.metadata,
    )


@router.post("/work-orders/{wo_id}/approve")
async def approve_draft_work_order(
    wo_id: int,
    req: ApproveWORequest | None = None,
    x_user_id: str = Header(default="supervisor-01"),
):
    """
    TC-AI-05: Human supervisor approval to promote a draft work order to 'open'.
    """
    approver = req.approved_by if req else x_user_id
    res = await tool_registry.approve_work_order(work_order_id=wo_id, approved_by=approver)
    if not res.get("success", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("error", "Failed to approve work order"),
        )
    return res


@router.get("/tools")
def list_available_tools():
    """List Copilot tool registry specifications."""
    return {
        "tools": [
            {
                "name": "search_assets",
                "description": "Find assets by name, type, or location",
                "access": "read",
            },
            {
                "name": "get_asset",
                "description": "Get asset details and current digital twin state",
                "access": "read",
            },
            {
                "name": "get_telemetry",
                "description": "Historical time-series telemetry with missing data checks",
                "access": "read",
            },
            {
                "name": "list_alarms",
                "description": "Query ISA-18.2 alarm events and history",
                "access": "read",
            },
            {
                "name": "list_work_orders",
                "description": "Maintenance history and work orders",
                "access": "read",
            },
            {
                "name": "search_docs",
                "description": "Semantic RAG search over equipment manuals and safety SOPs",
                "access": "read",
            },
            {
                "name": "get_kpis",
                "description": "OEE, MTBF, MTTR, and availability metrics",
                "access": "read",
            },
            {
                "name": "run_simulation",
                "description": "What-if simulation run on the digital twin sandbox",
                "access": "read_sandbox",
            },
            {
                "name": "draft_work_order",
                "description": "Create a draft work order (requires supervisor approval to open)",
                "access": "write_draft_only",
            },
        ],
        "guardrails": [
            "No PLC/SCADA write-back tools",
            "Tool-layer RBAC site authorization",
            "Grounded telemetry & alarm citations",
            "Transparent missing data reporting",
            "Prompt injection defense and logging",
        ],
    }


@router.get("/audit-logs")
def get_audit_logs():
    """Retrieve recent Copilot question and tool execution history for audit."""
    return {
        "count": len(copilot_agent.audit_history),
        "history": [
            {
                "question": item.question,
                "status": item.status,
                "tool_calls_count": len(item.tool_calls),
                "citations_count": len(item.citations),
                "metadata": item.metadata,
            }
            for item in copilot_agent.audit_history[-50:]
        ],
    }
