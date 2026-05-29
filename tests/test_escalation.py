import pytest
from agent.decision_engine import DecisionEngine, ReActStep
from gateway.provider import AdvancedDecisionEngine


@pytest.fixture
def engine():
    return DecisionEngine()


@pytest.fixture
def advanced():
    return AdvancedDecisionEngine()


class TestBaseEscalation:
    def test_high_urgency_escalates(self, engine):
        assert engine._should_escalate("high", "urgent issue", {}, {}) is True

    def test_critical_urgency_escalates(self, engine):
        assert engine._should_escalate("critical", "outage", {}, {}) is True

    def test_no_kb_match_escalates(self, engine):
        assert engine._should_escalate("low", "some question", {"found": False}, {}) is True

    def test_overdue_billing_escalates(self, engine):
        assert engine._should_escalate(
            "low", "question about my invoice",
            {"found": True}, {"billing_status": "overdue"}
        ) is True

    def test_cancel_term_escalates(self, engine):
        assert engine._should_escalate(
            "low", "I want to cancel my subscription",
            {"found": True}, {}
        ) is True

    def test_low_urgency_kb_hit_no_escalation(self, engine):
        assert engine._should_escalate(
            "low", "how do I reset my password",
            {"found": True}, {"billing_status": "current"}
        ) is False


class TestAdvancedEscalation:
    def test_enterprise_medium_escalates(self, advanced):
        assert advanced._should_escalate(
            "medium", "something is broken",
            {"found": True, "total_matches": 3}, {"plan": "enterprise"}
        ) is True

    def test_enterprise_low_does_not_escalate_via_advanced_check(self, advanced):
        # base engine doesn't escalate low with kb hit; advanced check only triggers medium+
        assert advanced._should_escalate(
            "low", "general question",
            {"found": True, "total_matches": 3}, {"plan": "enterprise"}
        ) is False

    def test_low_kb_confidence_at_medium_escalates(self, advanced):
        assert advanced._should_escalate(
            "medium", "something is broken",
            {"found": True, "total_matches": 1}, {"plan": "basic"}
        ) is True

    def test_repeat_billing_pattern_escalates(self, advanced):
        assert advanced._should_escalate(
            "low", "I have a question about my invoice",
            {"found": True, "total_matches": 2},
            {"plan": "basic", "billing_status": "current", "recent_issues": ["payment failed last month"]}
        ) is True

    def test_no_repeat_billing_no_extra_escalation(self, advanced):
        assert advanced._should_escalate(
            "low", "I have a question about my invoice",
            {"found": True, "total_matches": 2},
            {"plan": "basic", "billing_status": "current", "recent_issues": ["login issue"]}
        ) is False


class TestReActLoop:
    def test_first_step_checks_urgency(self, engine):
        step = engine.decide_next_step({"message": "I need help", "history": [], "customer_id": "CUST001"})
        assert step.action == "check_urgency"

    def test_low_urgency_step2_searches_kb(self, engine):
        history = [
            ReActStep(thought="t", action="check_urgency"),
            {"tool": "check_urgency", "result": {"urgency": "low"}},
        ]
        step = engine.decide_next_step({"message": "how do I reset my password", "history": history, "customer_id": "CUST001"})
        assert step.action == "search_knowledge_base"

    def test_high_urgency_step2_fetches_customer(self, engine):
        history = [
            ReActStep(thought="t", action="check_urgency"),
            {"tool": "check_urgency", "result": {"urgency": "high"}},
        ]
        step = engine.decide_next_step({"message": "urgent issue", "history": history, "customer_id": "CUST001"})
        assert step.action == "get_customer_history"
