from enum import Enum
from data.store import get_customer
from agent.constants import CRITICAL_TERMS, HIGH_TERMS, MEDIUM_TERMS, BILLING_TERMS, CANCEL_TERMS


class RoutingPolicy(str, Enum):
    AUTO     = "auto"
    COST     = "cost"
    ACCURACY = "accuracy"


class Router:
    """
    Selects a provider based on message urgency, customer tier, and routing policy.
    Returns (provider_name, routing_reason).
    """

    _critical_terms = CRITICAL_TERMS
    _high_terms     = HIGH_TERMS
    _medium_terms   = MEDIUM_TERMS
    _billing_terms  = BILLING_TERMS
    _cancel_terms   = CANCEL_TERMS

    def select(
        self,
        customer_id: str,
        message: str,
        policy: RoutingPolicy = RoutingPolicy.AUTO,
    ) -> tuple[str, str]:
        urgency   = self._estimate_urgency(message)
        customer  = get_customer(customer_id)
        plan      = customer["plan"] if customer else "unknown"
        msg_lower = message.lower()

        if policy == RoutingPolicy.COST:
            if urgency == "critical":
                return "advanced-engine", "cost policy: critical urgency requires advanced engine"
            return "fast-engine", f"cost policy: fast engine selected for {urgency} urgency"

        if policy == RoutingPolicy.ACCURACY:
            if urgency in ("critical", "high") or plan == "enterprise":
                return "advanced-engine", f"accuracy policy: {urgency} urgency / {plan} plan requires advanced engine"
            return "standard-engine", "accuracy policy: standard engine minimum for all requests"

        # AUTO policy — evaluated in priority order
        if urgency == "critical":
            return "advanced-engine", "critical urgency — advanced engine required"

        if urgency == "high" and plan == "enterprise":
            return "advanced-engine", "high urgency + enterprise customer — advanced engine"

        if urgency == "high":
            return "standard-engine", "high urgency — standard engine"

        if urgency == "medium" and plan == "enterprise":
            return "advanced-engine", "enterprise customer at medium urgency — advanced engine (SLA)"

        if urgency == "medium" and any(t in msg_lower for t in self._billing_terms):
            return "standard-engine", "medium urgency with billing topic — standard engine"

        if urgency == "medium" and any(t in msg_lower for t in self._cancel_terms):
            return "standard-engine", "medium urgency with cancellation topic — standard engine"

        if plan == "enterprise":
            return "standard-engine", "enterprise customer — standard engine minimum tier"

        if urgency == "low":
            return "fast-engine", "low urgency general inquiry — fast engine"

        return "standard-engine", "default routing — standard engine"

    def _estimate_urgency(self, message: str) -> str:
        msg = message.lower()
        if any(t in msg for t in self._critical_terms):
            return "critical"
        if any(t in msg for t in self._high_terms):
            return "high"
        if any(t in msg for t in self._medium_terms):
            return "medium"
        return "low"
