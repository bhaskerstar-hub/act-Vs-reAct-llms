import pytest
from gateway.router import Router, RoutingPolicy


@pytest.fixture
def router():
    return Router()


class TestUrgencyDetection:
    def test_critical_terms(self, router):
        for term in ["outage", "data loss", "breach"]:
            assert router._estimate_urgency(f"We have a {term}") == "critical"

    def test_high_terms(self, router):
        for term in ["urgent", "asap", "system down"]:
            assert router._estimate_urgency(f"This is {term}") == "high"

    def test_medium_terms(self, router):
        for term in ["broken", "error", "not working", "bug"]:
            assert router._estimate_urgency(f"The app is {term}") == "medium"

    def test_low_default(self, router):
        assert router._estimate_urgency("How do I reset my password?") == "low"

    def test_critical_beats_high(self, router):
        assert router._estimate_urgency("urgent outage affecting all users") == "critical"


class TestAutoPolicy:
    def test_critical_always_advanced(self, router):
        provider, reason = router.select("CUST001", "We have a data loss incident", RoutingPolicy.AUTO)
        assert provider == "advanced-engine"
        assert "critical" in reason

    def test_high_urgency_enterprise_gets_advanced(self, router):
        provider, reason = router.select("CUST003", "System down urgently", RoutingPolicy.AUTO)
        assert provider == "advanced-engine"

    def test_high_urgency_non_enterprise_gets_standard(self, router):
        provider, reason = router.select("CUST001", "This is urgent please help", RoutingPolicy.AUTO)
        assert provider == "standard-engine"

    def test_medium_enterprise_gets_advanced(self, router):
        provider, reason = router.select("CUST003", "Something is broken", RoutingPolicy.AUTO)
        assert provider == "advanced-engine"
        assert "enterprise" in reason

    def test_medium_billing_gets_standard(self, router):
        provider, reason = router.select("CUST001", "There is an error with my invoice", RoutingPolicy.AUTO)
        assert provider == "standard-engine"
        assert "billing" in reason

    def test_medium_cancellation_gets_standard(self, router):
        provider, reason = router.select("CUST001", "Something is broken and I want to cancel", RoutingPolicy.AUTO)
        assert provider == "standard-engine"

    def test_low_urgency_gets_fast(self, router):
        provider, reason = router.select("CUST001", "How do I add a new user?", RoutingPolicy.AUTO)
        assert provider == "fast-engine"

    def test_enterprise_floor_is_standard(self, router):
        provider, _ = router.select("CUST003", "What are your business hours?", RoutingPolicy.AUTO)
        assert provider == "standard-engine"

    def test_unknown_customer_treated_as_non_enterprise(self, router):
        provider, _ = router.select("UNKNOWN", "How do I reset my password?", RoutingPolicy.AUTO)
        assert provider == "fast-engine"


class TestCostPolicy:
    def test_cost_critical_uses_advanced(self, router):
        provider, reason = router.select("CUST001", "We have a breach", RoutingPolicy.COST)
        assert provider == "advanced-engine"
        assert "critical" in reason

    def test_cost_high_uses_fast(self, router):
        provider, _ = router.select("CUST001", "This is urgent", RoutingPolicy.COST)
        assert provider == "fast-engine"

    def test_cost_low_uses_fast(self, router):
        provider, _ = router.select("CUST001", "General question", RoutingPolicy.COST)
        assert provider == "fast-engine"


class TestAccuracyPolicy:
    def test_accuracy_critical_uses_advanced(self, router):
        provider, _ = router.select("CUST001", "Security breach detected", RoutingPolicy.ACCURACY)
        assert provider == "advanced-engine"

    def test_accuracy_high_uses_advanced(self, router):
        provider, _ = router.select("CUST001", "System down urgent", RoutingPolicy.ACCURACY)
        assert provider == "advanced-engine"

    def test_accuracy_enterprise_uses_advanced(self, router):
        provider, _ = router.select("CUST003", "General question", RoutingPolicy.ACCURACY)
        assert provider == "advanced-engine"

    def test_accuracy_low_non_enterprise_uses_standard(self, router):
        provider, _ = router.select("CUST001", "How do I reset my password?", RoutingPolicy.ACCURACY)
        assert provider == "standard-engine"
