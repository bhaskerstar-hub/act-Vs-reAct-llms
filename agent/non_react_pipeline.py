from data.store import search_kb


class NonReActPipeline:
    """
    Fixed 3-step pipeline that mimics a traditional (non-agentic) support system.
    Steps are predetermined and always execute in the same order regardless of
    what each step finds. No reasoning loop, no adaptive branching.
    """

    _critical_terms = ["outage", "data loss", "breach", "security incident", "all users affected"]
    _high_terms = ["urgent", "asap", "immediately", "critical", "system down", "emergency", "deleted"]
    _medium_terms = ["broken", "error", "not working", "bug", "failed", "wrong charge"]

    def run(self, customer_id: str, message: str) -> dict:
        steps = []

        # Step 1 — Classify urgency from keywords alone (no account context)
        urgency = self._classify_urgency(message)
        steps.append({
            "step": 1,
            "name": "classify_urgency",
            "description": "Scan message text for urgency keywords",
            "input": {"message": message},
            "output": {"urgency": urgency},
        })

        # Step 2 — Search knowledge base (always runs, no matter what step 1 found)
        results = search_kb(message)
        kb_hit = results[0] if results else None
        steps.append({
            "step": 2,
            "name": "search_knowledge_base",
            "description": "Retrieve the best matching FAQ entry",
            "input": {"query": message},
            "output": {
                "found": bool(kb_hit),
                "category": kb_hit["category"] if kb_hit else None,
                "title": kb_hit["title"] if kb_hit else None,
                "content": kb_hit["content"] if kb_hit else None,
            },
        })

        # Step 3 — Route based only on urgency; account history is never consulted
        if urgency in ("high", "critical"):
            routed = True
            queue = "on-call-team" if urgency == "critical" else "senior-support"
            response = (
                f"Your issue has been escalated due to {urgency} urgency. "
                "A support agent will contact you shortly."
            )
        elif kb_hit:
            routed = False
            queue = "auto-responder"
            response = kb_hit["content"]
        else:
            routed = True
            queue = "support-team"
            response = "We could not find an automated answer. A support agent will follow up."

        category = kb_hit["category"] if kb_hit else "general"

        steps.append({
            "step": 3,
            "name": "route_and_respond",
            "description": "Route based on urgency score only — no account context used",
            "input": {"urgency": urgency, "kb_found": bool(kb_hit)},
            "output": {"routed_to_human": routed, "queue": queue},
        })

        return {
            "urgency": urgency,
            "category": category,
            "routed_to_human": routed,
            "queue": queue,
            "suggested_response": response,
            "steps": steps,
            "context_checked": ["message_keywords", "knowledge_base"],
            "context_skipped": [
                "customer_account_history",
                "billing_status",
                "account_tier",
                "past_ticket_patterns",
                "cancellation_signals",
            ],
        }

    def _classify_urgency(self, message: str) -> str:
        msg = message.lower()
        if any(t in msg for t in self._critical_terms):
            return "critical"
        if any(t in msg for t in self._high_terms):
            return "high"
        if any(t in msg for t in self._medium_terms):
            return "medium"
        return "low"
