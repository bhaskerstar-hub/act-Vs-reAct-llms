from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from models.schemas import (
    TicketRequest,
    TicketResponse,
    ReActTraceStep,
    UrgencyLevel,
    TicketStatus,
    GatewayMetadata,
    GatewayStatsResponse,
)
from gateway import get_gateway, RoutingPolicy
from data.store import save_ticket, get_all_tickets, get_ticket

router  = APIRouter(tags=["tickets"])
gateway = get_gateway()


@router.post("/tickets", response_model=TicketResponse)
def submit_ticket(request: TicketRequest, policy: str = "auto"):
    routing_policy = RoutingPolicy(policy) if policy in ("auto", "cost", "accuracy") else RoutingPolicy.AUTO
    result = gateway.execute(
        customer_id=request.customer_id,
        message=request.message,
        policy=routing_policy,
    )

    status       = TicketStatus.ESCALATED if result["routed_to_human"] else TicketStatus.AUTO_RESOLVED
    assigned_to  = result.get("queue") or "auto-responder"

    if result["routed_to_human"]:
        eta    = result.get("estimated_response_time", "varies")
        reason = result.get("escalation_reason", "requires review")
        suggested_response = (
            f"Your ticket has been escalated to our {assigned_to}. "
            f"Reason: {reason}. Estimated response time: {eta}."
        )
    else:
        suggested_response = result.get("auto_response", "Thank you for contacting support.")

    trace_steps = [
        ReActTraceStep(
            step=t["step"],
            thought=t["thought"],
            action=t.get("action"),
            action_input=t.get("action_input"),
            observation=t.get("observation"),
        )
        for t in result["trace"]
    ]

    created_at = datetime.now(timezone.utc)

    ticket_data = {
        "customer_id":      request.customer_id,
        "message":          request.message,
        "channel":          request.channel,
        "urgency":          result["urgency"],
        "status":           status.value,
        "category":         result.get("kb_category") or "general",
        "suggested_response": suggested_response,
        "assigned_to":      assigned_to,
        "trace":            [t.model_dump() for t in trace_steps],
        "created_at":       created_at.isoformat(),
    }

    ticket_id = save_ticket(ticket_data)

    gm = result.get("gateway_metadata")

    return TicketResponse(
        ticket_id=ticket_id,
        customer_id=request.customer_id,
        urgency=UrgencyLevel(result["urgency"]),
        status=status,
        category=ticket_data["category"],
        suggested_response=suggested_response,
        assigned_to=assigned_to,
        reasoning_trace=trace_steps,
        created_at=created_at,
        gateway_metadata=GatewayMetadata(**gm) if gm else None,
    )


@router.post("/compare")
def compare_approaches(request: TicketRequest, policy: str = "auto"):
    routing_policy = RoutingPolicy(policy) if policy in ("auto", "cost", "accuracy") else RoutingPolicy.AUTO

    # Non-ReAct side: always the fast engine (fixed pipeline, no reasoning loop)
    nr = gateway.execute(
        customer_id=request.customer_id,
        message=request.message,
        policy=routing_policy,
        _force_provider="fast-engine",
    )

    # ReAct side: auto-routed based on policy, urgency, and customer tier
    ra = gateway.execute(
        customer_id=request.customer_id,
        message=request.message,
        policy=routing_policy,
    )

    # Build suggested response for the ReAct result
    if ra["routed_to_human"]:
        eta    = ra.get("estimated_response_time", "varies")
        reason = ra.get("escalation_reason", "requires review")
        queue  = ra.get("queue", "support-team")
        ra_response = f"Escalated to {queue}. Reason: {reason}. ETA: {eta}."
    else:
        ra_response = ra.get("auto_response", "Thank you for contacting support.")

    # Collect context the ReAct agent actually gathered
    ra_context = []
    for step in ra["trace"]:
        action = step.get("action")
        if action == "check_urgency":
            ra_context.append("message_keywords")
        elif action == "get_customer_history":
            ra_context.append("customer_account_history")
            obs = step.get("observation") or {}
            if isinstance(obs, dict) and obs.get("billing_status") == "overdue":
                ra_context.append("overdue_billing_detected")
            if isinstance(obs, dict) and obs.get("plan") == "enterprise":
                ra_context.append("enterprise_tier_detected")
        elif action == "search_knowledge_base":
            ra_context.append("knowledge_base")

    same_outcome = nr["routed_to_human"] == ra["routed_to_human"]

    if same_outcome:
        verdict = "agree"
        extra   = [c for c in ra_context if c not in nr["context_checked"]]
        verdict_detail = (
            "Both approaches reached the same routing decision. "
            + (f"ReAct gathered additional context ({', '.join(extra)}) that could prevent misrouting on edge cases." if extra else "")
        )
    else:
        nr_label    = "auto-responded" if not nr["routed_to_human"] else f"escalated to {nr['queue']}"
        ra_label    = "auto-responded" if not ra["routed_to_human"] else f"escalated to {ra.get('queue', 'support')}"
        extra_ctx   = [c for c in ra_context if c not in nr["context_checked"]]
        verdict     = "differ"
        verdict_detail = (
            f"Non-ReAct {nr_label} — it only checked urgency keywords and the knowledge base. "
            f"ReAct {ra_label} after also checking: {', '.join(extra_ctx)}. "
            "The extra context changed the routing outcome."
        )

    return {
        "customer_id":  request.customer_id,
        "message":      request.message,
        "non_react": {
            **{k: v for k, v in nr.items() if k != "gateway_metadata"},
            "gateway_metadata": nr.get("gateway_metadata"),
        },
        "react": {
            "urgency":          ra["urgency"],
            "category":         ra.get("kb_category") or "general",
            "routed_to_human":  ra["routed_to_human"],
            "queue":            ra.get("queue") or "auto-responder",
            "suggested_response": ra_response,
            "steps_count":      len(ra["trace"]),
            "trace":            ra["trace"],
            "context_checked":  ra_context,
            "context_skipped":  [],
            "gateway_metadata": ra.get("gateway_metadata"),
        },
        "same_outcome":  same_outcome,
        "verdict":       verdict,
        "verdict_detail": verdict_detail,
        "gateway": {
            "policy":             routing_policy.value,
            "non_react_provider": nr.get("gateway_metadata"),
            "react_provider":     ra.get("gateway_metadata"),
        },
    }


@router.get("/gateway/stats", response_model=GatewayStatsResponse)
def get_gateway_stats():
    return GatewayStatsResponse(stats=gateway.get_stats())


@router.get("/tickets")
def list_tickets():
    return {"tickets": get_all_tickets()}


@router.get("/tickets/{ticket_id}")
def fetch_ticket(ticket_id: str):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket
