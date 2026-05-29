import time
from abc import ABC, abstractmethod

from agent.react_agent import ReActAgent
from agent.non_react_pipeline import NonReActPipeline
from agent.decision_engine import DecisionEngine, ReActStep
from agent.tools import get_all_tools
from agent.constants import BILLING_TERMS


class BaseProvider(ABC):
    name: str
    display_name: str
    latency_ms: int
    cost_per_call: float
    engine_type: str

    @abstractmethod
    def execute(self, customer_id: str, message: str) -> dict:
        ...

    def _simulate_latency(self) -> None:
        time.sleep(self.latency_ms / 1000)


class FastProvider(BaseProvider):
    name         = "fast-engine"
    display_name = "Fast Engine"
    latency_ms   = 50
    cost_per_call = 0.001
    engine_type  = "rule-based"

    def __init__(self):
        self._pipeline = NonReActPipeline()

    def execute(self, customer_id: str, message: str) -> dict:
        self._simulate_latency()
        r = self._pipeline.run(customer_id=customer_id, message=message)
        # Add compatibility keys so callers can treat all providers uniformly
        r["auto_response"]          = r.get("suggested_response")
        r["kb_category"]            = r.get("category")
        r["escalation_reason"]      = None
        r["estimated_response_time"] = None
        r["trace"] = [
            {
                "step":         s["step"],
                "thought":      s.get("description", ""),
                "action":       s.get("name"),
                "action_input": s.get("input"),
                "observation":  s.get("output"),
            }
            for s in r.get("steps", [])
        ]
        return r


class StandardProvider(BaseProvider):
    name         = "standard-engine"
    display_name = "Standard Engine"
    latency_ms   = 200
    cost_per_call = 0.005
    engine_type  = "rule-based"

    def __init__(self):
        self._agent = ReActAgent()

    def execute(self, customer_id: str, message: str) -> dict:
        self._simulate_latency()
        return self._agent.run(customer_id=customer_id, message=message)


class AdvancedDecisionEngine(DecisionEngine):
    """
    Extends DecisionEngine with three additional escalation checks:
    1. Enterprise customers at medium+ urgency always escalate (SLA requirement).
    2. KB search returns only one low-confidence match at medium urgency → escalate.
    3. Repeat billing pattern: current billing message + billing issue in past tickets → escalate.

    Also overrides decide_next_step to always pull customer history at step 1,
    giving the engine full context regardless of message type.
    """

    def decide_next_step(self, context: dict) -> ReActStep:
        history     = context.get("history", [])
        react_steps = [h for h in history if isinstance(h, ReActStep)]
        observations = {
            h["tool"]: h["result"]
            for h in history
            if isinstance(h, dict) and "tool" in h
        }
        step_count  = len(react_steps)
        customer_id = context.get("customer_id")

        # Always pull customer history at step 1 — advanced analysis needs full context
        if step_count == 1 and "get_customer_history" not in observations and customer_id:
            urgency = observations.get("check_urgency", {}).get("urgency", "low")
            return ReActStep(
                thought=(
                    f"Urgency is '{urgency}'. Advanced analysis always checks full customer context "
                    "before deciding — pulling account history now."
                ),
                action="get_customer_history",
                action_input={"customer_id": customer_id},
            )

        return super().decide_next_step(context)

    def _should_escalate(
        self, urgency: str, message: str, kb_result: dict, customer_result: dict
    ) -> bool:
        if super()._should_escalate(urgency, message, kb_result, customer_result):
            return True

        # Check 1: enterprise SLA — human review required at medium+ urgency
        if customer_result.get("plan") == "enterprise" and urgency in ("medium", "high", "critical"):
            return True

        # Check 2: low KB confidence at medium urgency is too risky for auto-response
        if urgency == "medium" and kb_result.get("total_matches", 0) <= 1:
            return True

        # Check 3: repeat billing pattern — same issue type coming back needs human review
        recent = customer_result.get("recent_issues", [])
        recent_text = " ".join(recent).lower()
        if (
            any(t in recent_text for t in self._billing_terms)
            and any(t in message.lower() for t in self._billing_terms)
        ):
            return True

        return False

    def _build_escalation_reason(
        self, urgency: str, message: str, customer_result: dict
    ) -> str:
        base = super()._build_escalation_reason(urgency, message, customer_result)
        extras = []

        if customer_result.get("plan") == "enterprise" and urgency in ("medium", "high", "critical"):
            extras.append("enterprise SLA requires human review at medium+ urgency")

        if any(
            t in " ".join(customer_result.get("recent_issues", [])).lower()
            for t in self._billing_terms
        ):
            extras.append("repeat billing issue pattern detected")

        return base + ("; " + "; ".join(extras) if extras else "")


class AdvancedProvider(BaseProvider):
    name         = "advanced-engine"
    display_name = "Advanced Engine"
    latency_ms   = 800
    cost_per_call = 0.020
    engine_type  = "rule-based"

    def __init__(self):
        self._agent = ReActAgent()
        self._agent.engine = AdvancedDecisionEngine()

    def execute(self, customer_id: str, message: str) -> dict:
        self._simulate_latency()
        return self._agent.run(customer_id=customer_id, message=message)
