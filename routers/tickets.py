from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from models.schemas import (
    TicketRequest,
    TicketResponse,
    ReActTraceStep,
    UrgencyLevel,
    TicketStatus,
)
from agent.react_agent import ReActAgent
from agent.non_react_pipeline import NonReActPipeline
from data.store import save_ticket, get_all_tickets, get_ticket

router = APIRouter(tags=["tickets"])
agent = ReActAgent()
non_react = NonReActPipeline()


@router.post("/tickets", response_model=TicketResponse)
def submit_ticket(request: TicketRequest):
    result = agent.run(customer_id=request.customer_id, message=request.message)

    status = TicketStatus.ESCALATED if result["routed_to_human"] else TicketStatus.AUTO_RESOLVED
    assigned_to = result.get("queue") or "auto-responder"

    if result["routed_to_human"]:
        eta = result.get("estimated_response_time", "varies")
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
        "customer_id": request.customer_id,
        "message": request.message,
        "channel": request.channel,
        "urgency": result["urgency"],
        "status": status.value,
        "category": result.get("kb_category") or "general",
        "suggested_response": suggested_response,
        "assigned_to": assigned_to,
        "trace": [t.model_dump() for t in trace_steps],
        "created_at": created_at.isoformat(),
    }

    ticket_id = save_ticket(ticket_data)

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
    )


@router.post("/compare")
def compare_approaches(request: TicketRequest):
    nr = non_react.run(customer_id=request.customer_id, message=request.message)
    ra = agent.run(customer_id=request.customer_id, message=request.message)

    # Build suggested response for the ReAct result
    if ra["routed_to_human"]:
        eta = ra.get("estimated_response_time", "varies")
        reason = ra.get("escalation_reason", "requires review")
        queue = ra.get("queue", "support-team")
        ra_response = f"Escalated to {queue}. Reason: {reason}. ETA: {eta}."
    else:
        ra_response = ra.get("auto_response", "Thank you for contacting support.")

    # Collect what context ReAct actually gathered
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

    # Determine verdict
    same_outcome = nr["routed_to_human"] == ra["routed_to_human"]

    if same_outcome:
        verdict = "agree"
        extra = [c for c in ra_context if c not in nr["context_checked"]]
        verdict_detail = (
            "Both approaches reached the same routing decision. "
            + (f"ReAct gathered additional context ({', '.join(extra)}) that could prevent misrouting on edge cases." if extra else "")
        )
    else:
        nr_label = "auto-responded" if not nr["routed_to_human"] else f"escalated to {nr['queue']}"
        ra_label = "auto-responded" if not ra["routed_to_human"] else f"escalated to {ra.get('queue', 'support')}"
        extra_ctx = [c for c in ra_context if c not in nr["context_checked"]]
        verdict = "differ"
        verdict_detail = (
            f"Non-ReAct {nr_label} — it only checked urgency keywords and the knowledge base. "
            f"ReAct {ra_label} after also checking: {', '.join(extra_ctx)}. "
            "The extra context changed the routing outcome."
        )

    return {
        "customer_id": request.customer_id,
        "message": request.message,
        "non_react": nr,
        "react": {
            "urgency": ra["urgency"],
            "category": ra.get("kb_category") or "general",
            "routed_to_human": ra["routed_to_human"],
            "queue": ra.get("queue") or "auto-responder",
            "suggested_response": ra_response,
            "steps_count": len(ra["trace"]),
            "trace": ra["trace"],
            "context_checked": ra_context,
            "context_skipped": [],
        },
        "same_outcome": same_outcome,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
    }


@router.get("/tickets")
def list_tickets():
    return {"tickets": get_all_tickets()}


@router.get("/tickets/{ticket_id}")
def fetch_ticket(ticket_id: str):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket
