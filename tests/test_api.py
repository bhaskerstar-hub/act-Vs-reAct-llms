import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestCustomers:
    def test_list_customers(self):
        r = client.get("/api/v1/customers")
        assert r.status_code == 200
        data = r.json()
        assert "customers" in data
        assert len(data["customers"]) == 7
        ids = {c["id"] for c in data["customers"]}
        assert "CUST001" in ids
        assert "CUST007" in ids


class TestSubmitTicket:
    def test_basic_ticket(self):
        r = client.post("/api/v1/tickets", json={"customer_id": "CUST001", "message": "How do I reset my password?"})
        assert r.status_code == 200
        data = r.json()
        assert data["ticket_id"].startswith("TKT-")
        assert data["customer_id"] == "CUST001"
        assert data["urgency"] in ("low", "medium", "high", "critical")
        assert data["status"] in ("auto_resolved", "escalated")
        assert "gateway_metadata" in data
        assert data["gateway_metadata"]["engine_type"] == "rule-based"

    def test_unknown_customer_returns_422(self):
        r = client.post("/api/v1/tickets", json={"customer_id": "NOTREAL", "message": "help"})
        assert r.status_code == 422
        assert "Unknown customer_id" in r.json()["detail"]

    def test_cost_policy(self):
        r = client.post("/api/v1/tickets?policy=cost", json={"customer_id": "CUST001", "message": "general question"})
        assert r.status_code == 200
        assert r.json()["gateway_metadata"]["policy"] == "cost"

    def test_accuracy_policy(self):
        r = client.post("/api/v1/tickets?policy=accuracy", json={"customer_id": "CUST001", "message": "general question"})
        assert r.status_code == 200
        assert r.json()["gateway_metadata"]["policy"] == "accuracy"

    def test_billing_medium_urgency_standard_engine(self):
        r = client.post("/api/v1/tickets", json={"customer_id": "CUST001", "message": "there is an error with my invoice"})
        assert r.status_code == 200
        gm = r.json()["gateway_metadata"]
        assert gm["provider_name"] == "standard-engine"

    def test_critical_urgency_advanced_engine(self):
        r = client.post("/api/v1/tickets", json={"customer_id": "CUST001", "message": "We have a data loss incident"})
        assert r.status_code == 200
        gm = r.json()["gateway_metadata"]
        assert gm["provider_name"] == "advanced-engine"

    def test_escalated_ticket_has_queue(self):
        r = client.post("/api/v1/tickets", json={"customer_id": "CUST001", "message": "urgent system down emergency"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "escalated"
        assert data["assigned_to"] != "auto-responder"

    def test_reasoning_trace_present(self):
        r = client.post("/api/v1/tickets", json={"customer_id": "CUST001", "message": "How do I configure the API?"})
        assert r.status_code == 200
        trace = r.json()["reasoning_trace"]
        assert len(trace) >= 1
        assert "thought" in trace[0]


class TestCompare:
    def test_compare_returns_both_sides(self):
        r = client.post("/api/v1/compare", json={"customer_id": "CUST001", "message": "How do I reset my password?"})
        assert r.status_code == 200
        data = r.json()
        assert "non_react" in data
        assert "react" in data
        assert "verdict" in data
        assert data["verdict"] in ("agree", "differ")

    def test_compare_unknown_customer_422(self):
        r = client.post("/api/v1/compare", json={"customer_id": "GHOST", "message": "help"})
        assert r.status_code == 422

    def test_compare_verdict_detail_present(self):
        r = client.post("/api/v1/compare", json={"customer_id": "CUST002", "message": "I want to cancel my subscription"})
        assert r.status_code == 200
        assert r.json()["verdict_detail"] != ""

    def test_compare_react_has_trace(self):
        r = client.post("/api/v1/compare", json={"customer_id": "CUST001", "message": "How do I reset my password?"})
        assert r.status_code == 200
        assert len(r.json()["react"]["trace"]) >= 1

    def test_compare_gateway_metadata_on_both(self):
        r = client.post("/api/v1/compare", json={"customer_id": "CUST001", "message": "General inquiry"})
        assert r.status_code == 200
        data = r.json()
        assert data["gateway"]["non_react_provider"]["provider_name"] == "fast-engine"


class TestGatewayStats:
    def test_stats_endpoint(self):
        client.post("/api/v1/tickets", json={"customer_id": "CUST001", "message": "test"})
        r = client.get("/api/v1/gateway/stats")
        assert r.status_code == 200
        stats = r.json()["stats"]
        assert "fast-engine" in stats
        assert "standard-engine" in stats
        assert "advanced-engine" in stats
        for provider_stats in stats.values():
            assert "call_count" in provider_stats
            assert "avg_latency" in provider_stats
            assert "total_cost" in provider_stats


class TestTicketPersistence:
    def test_submitted_ticket_retrievable(self):
        r = client.post("/api/v1/tickets", json={"customer_id": "CUST001", "message": "How do I add a team member?"})
        ticket_id = r.json()["ticket_id"]
        r2 = client.get(f"/api/v1/tickets/{ticket_id}")
        assert r2.status_code == 200
        assert r2.json()["id"] == ticket_id

    def test_unknown_ticket_404(self):
        r = client.get("/api/v1/tickets/TKT-NOTEXIST")
        assert r.status_code == 404

    def test_list_tickets_includes_submitted(self):
        r = client.post("/api/v1/tickets", json={"customer_id": "CUST005", "message": "How do I configure the API?"})
        ticket_id = r.json()["ticket_id"]
        r2 = client.get("/api/v1/tickets")
        ids = [t["id"] for t in r2.json()["tickets"]]
        assert ticket_id in ids
