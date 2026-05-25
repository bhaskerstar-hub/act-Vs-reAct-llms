from data.store import get_customer, search_kb
from typing import Any


class Tool:
    name: str
    description: str

    def run(self, inputs: dict) -> Any:
        raise NotImplementedError


class CheckUrgencyTool(Tool):
    name = "check_urgency"
    description = "Analyzes the message and returns an urgency level: low, medium, high, or critical"

    _critical_terms = ["outage", "data loss", "breach", "security incident", "all users affected"]
    _high_terms = ["urgent", "asap", "immediately", "critical", "system down", "emergency", "deleted"]
    _medium_terms = ["broken", "error", "not working", "bug", "failed", "wrong charge"]

    def run(self, inputs: dict) -> dict:
        message = inputs.get("message", "").lower()

        if any(term in message for term in self._critical_terms):
            level = "critical"
        elif any(term in message for term in self._high_terms):
            level = "high"
        elif any(term in message for term in self._medium_terms):
            level = "medium"
        else:
            level = "low"

        return {"urgency": level}


class GetCustomerHistoryTool(Tool):
    name = "get_customer_history"
    description = "Retrieves account info and ticket history for a given customer ID"

    def run(self, inputs: dict) -> dict:
        customer_id = inputs.get("customer_id")
        customer = get_customer(customer_id)

        if not customer:
            return {"found": False, "message": f"No account found for {customer_id}"}

        return {
            "found": True,
            "plan": customer["plan"],
            "account_age_days": customer["account_age_days"],
            "billing_status": customer["billing_status"],
            "open_tickets": customer["open_tickets"],
            "past_ticket_count": len(customer["past_tickets"]),
            "recent_issues": [t["issue"] for t in customer["past_tickets"][-2:]],
        }


class SearchKnowledgeBaseTool(Tool):
    name = "search_knowledge_base"
    description = "Searches the knowledge base for FAQ entries relevant to the customer query"

    def run(self, inputs: dict) -> dict:
        query = inputs.get("query", "")
        results = search_kb(query)

        if not results:
            return {"found": False, "results": []}

        top = results[0]
        return {
            "found": True,
            "kb_id": top["id"],
            "category": top["category"],
            "title": top["title"],
            "content": top["content"],
            "total_matches": len(results),
        }


class RouteToHumanTool(Tool):
    name = "route_to_human"
    description = "Escalates the ticket to a human support queue with a reason and priority"

    _queue_map = {
        "critical": "on-call-team",
        "high": "senior-support",
        "medium": "support-team",
        "low": "support-team",
    }

    _eta_map = {
        "critical": "15 minutes",
        "high": "2-4 hours",
        "medium": "24 hours",
        "low": "48 hours",
    }

    def run(self, inputs: dict) -> dict:
        urgency = inputs.get("urgency", "medium")
        reason = inputs.get("reason", "Requires human review")

        return {
            "routed": True,
            "queue": self._queue_map.get(urgency, "support-team"),
            "reason": reason,
            "estimated_response_time": self._eta_map.get(urgency, "24 hours"),
        }


class GenerateAutoResponseTool(Tool):
    name = "generate_auto_response"
    description = "Generates a templated response using a knowledge base entry when escalation is not needed"

    _templates = {
        "billing": "Thanks for reaching out about your billing. {content} Reply to this ticket if you need further help.",
        "technical": "We've noted your technical issue. {content} A support engineer will follow up if it persists.",
        "account": "Thanks for contacting us about your account. {content}",
        "feature": "Great question! {content} Feel free to reply if you need anything else.",
        "cancellation": "We've received your request. {content} Reply if you'd like to discuss your options.",
        "general": "Thank you for reaching out. {content} Let us know if there's anything else we can help with.",
    }

    def run(self, inputs: dict) -> dict:
        category = inputs.get("category", "general")
        kb_content = inputs.get("kb_content", "Our team will follow up shortly.")

        template = self._templates.get(category, self._templates["general"])
        response = template.format(content=kb_content)

        return {
            "response_generated": True,
            "category": category,
            "response": response,
        }


def get_all_tools() -> list:
    return [
        CheckUrgencyTool(),
        GetCustomerHistoryTool(),
        SearchKnowledgeBaseTool(),
        RouteToHumanTool(),
        GenerateAutoResponseTool(),
    ]
