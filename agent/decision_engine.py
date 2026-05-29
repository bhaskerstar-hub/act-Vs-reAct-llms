from dataclasses import dataclass
from typing import Optional
from agent.constants import BILLING_TERMS, CANCEL_TERMS, CRITICAL_TERMS, HIGH_TERMS


@dataclass
class ReActStep:
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    is_final: bool = False
    final_answer: Optional[str] = None


class DecisionEngine:
    """
    Deterministic rule-based engine that drives the Reason + Act loop.
    In a production system this would be replaced with a real model API call.
    """

    _billing_terms = BILLING_TERMS
    _cancel_terms  = CANCEL_TERMS
    _urgent_terms  = CRITICAL_TERMS + HIGH_TERMS

    def decide_next_step(self, context: dict) -> ReActStep:
        message     = context.get("message", "").lower()
        history     = context.get("history", [])
        customer_id = context.get("customer_id")

        react_steps  = [h for h in history if isinstance(h, ReActStep)]
        observations = {
            h["tool"]: h["result"]
            for h in history
            if isinstance(h, dict) and "tool" in h
        }
        step_count = len(react_steps)

        if step_count == 0:
            return ReActStep(
                thought="First, I need to assess how urgent this request is before deciding what to do next.",
                action="check_urgency",
                action_input={"message": context["message"]},
            )

        urgency_result = observations.get("check_urgency", {})
        urgency = urgency_result.get("urgency", "low")

        if step_count == 1:
            needs_account_context = (
                urgency in ("high", "critical")
                or any(term in message for term in self._billing_terms)
                or any(term in message for term in self._cancel_terms)
            )
            if needs_account_context and customer_id:
                return ReActStep(
                    thought=(
                        f"Urgency is '{urgency}' and the topic suggests account-level context is needed. "
                        "Pulling the customer's history before deciding how to respond."
                    ),
                    action="get_customer_history",
                    action_input={"customer_id": customer_id},
                )
            return ReActStep(
                thought="Urgency is low and this looks like a general inquiry. Searching the knowledge base for a relevant answer.",
                action="search_knowledge_base",
                action_input={"query": context["message"]},
            )

        if step_count == 2 and "search_knowledge_base" not in observations:
            return ReActStep(
                thought="I have the customer's account context. Now searching the knowledge base to find a matching resolution.",
                action="search_knowledge_base",
                action_input={"query": context["message"]},
            )

        kb_result       = observations.get("search_knowledge_base", {})
        customer_result = observations.get("get_customer_history", {})

        if self._should_escalate(urgency, message, kb_result, customer_result):
            reason = self._build_escalation_reason(urgency, message, customer_result)
            return ReActStep(
                thought=(
                    f"Based on urgency '{urgency}' and the account details, this ticket needs a human agent. "
                    f"Reason: {reason}"
                ),
                action="route_to_human",
                action_input={"urgency": urgency, "reason": reason},
            )

        category   = kb_result.get("category", "general")
        kb_content = kb_result.get("content", "Our team will follow up with you shortly.")
        return ReActStep(
            thought="The knowledge base has a relevant answer and escalation is not needed. Generating an automated response.",
            action="generate_auto_response",
            action_input={"category": category, "kb_content": kb_content},
        )

    def _should_escalate(self, urgency: str, message: str, kb_result: dict, customer_result: dict) -> bool:
        if urgency in ("high", "critical"):
            return True
        if not kb_result.get("found"):
            return True
        if customer_result.get("billing_status") == "overdue" and any(t in message for t in self._billing_terms):
            return True
        if any(term in message for term in self._cancel_terms):
            return True
        return False

    def _build_escalation_reason(self, urgency: str, message: str, customer_result: dict) -> str:
        reasons = []
        if urgency in ("high", "critical"):
            reasons.append(f"{urgency.upper()} urgency issue reported")
        if customer_result.get("billing_status") == "overdue":
            reasons.append("account has an overdue balance")
        if customer_result.get("plan") == "enterprise":
            reasons.append("enterprise-tier customer")
        if any(t in message for t in self._cancel_terms):
            reasons.append("potential cancellation — retention opportunity")
        return "; ".join(reasons) if reasons else "Issue requires human judgment"
