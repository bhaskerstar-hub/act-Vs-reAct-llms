import json
import uuid
from pathlib import Path
from typing import Optional

CUSTOMERS = {
    "CUST001": {
        "id": "CUST001",
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "plan": "premium",
        "account_age_days": 365,
        "billing_status": "current",
        "open_tickets": 0,
        "past_tickets": [
            {"id": "T-101", "issue": "billing discrepancy", "resolved": True, "date": "2024-01-15"},
            {"id": "T-089", "issue": "login issue", "resolved": True, "date": "2023-11-20"},
        ],
    },
    "CUST002": {
        "id": "CUST002",
        "name": "Bob Martinez",
        "email": "bob@example.com",
        "plan": "basic",
        "account_age_days": 45,
        "billing_status": "overdue",
        "open_tickets": 0,
        "past_tickets": [],
    },
    "CUST003": {
        "id": "CUST003",
        "name": "Carol White",
        "email": "carol@example.com",
        "plan": "enterprise",
        "account_age_days": 730,
        "billing_status": "current",
        "open_tickets": 0,
        "past_tickets": [
            {"id": "T-200", "issue": "API rate limit", "resolved": True, "date": "2024-03-01"},
        ],
    },
    "CUST004": {
        "id": "CUST004",
        "name": "David Kim",
        "email": "david@example.com",
        "plan": "premium",
        "account_age_days": 180,
        "billing_status": "current",
        "open_tickets": 1,
        "past_tickets": [
            {"id": "T-310", "issue": "wrong charge on invoice", "resolved": False, "date": "2024-05-10"},
            {"id": "T-295", "issue": "payment failed", "resolved": True, "date": "2024-04-22"},
        ],
    },
    "CUST005": {
        "id": "CUST005",
        "name": "Eva Rossi",
        "email": "eva@example.com",
        "plan": "basic",
        "account_age_days": 12,
        "billing_status": "current",
        "open_tickets": 0,
        "past_tickets": [],
    },
    "CUST006": {
        "id": "CUST006",
        "name": "Frank Nguyen",
        "email": "frank@example.com",
        "plan": "enterprise",
        "account_age_days": 1095,
        "billing_status": "overdue",
        "open_tickets": 2,
        "past_tickets": [
            {"id": "T-401", "issue": "system outage affecting all users", "resolved": True, "date": "2024-02-14"},
            {"id": "T-388", "issue": "data export failed", "resolved": True, "date": "2024-01-30"},
        ],
    },
    "CUST007": {
        "id": "CUST007",
        "name": "Grace Lee",
        "email": "grace@example.com",
        "plan": "premium",
        "account_age_days": 540,
        "billing_status": "current",
        "open_tickets": 0,
        "past_tickets": [
            {"id": "T-502", "issue": "cancel subscription request", "resolved": True, "date": "2024-03-20"},
        ],
    },
}

KNOWLEDGE_BASE = [
    {
        "id": "KB-001",
        "category": "billing",
        "keywords": ["invoice", "charge", "bill", "payment", "refund", "subscription", "charged", "money", "price"],
        "title": "Billing and Payment FAQ",
        "content": (
            "You can view all invoices under Account > Billing. Refunds are processed within 5-7 business days. "
            "For disputed charges, email billing@support.example.com with your invoice number."
        ),
    },
    {
        "id": "KB-002",
        "category": "technical",
        "keywords": ["error", "bug", "not working", "broken", "crash", "failed", "500", "timeout", "slow"],
        "title": "Troubleshooting Common Errors",
        "content": (
            "Start by clearing your browser cache and retrying. Check our status page at status.example.com "
            "for any ongoing incidents. If the problem persists beyond one hour, a support engineer will investigate."
        ),
    },
    {
        "id": "KB-003",
        "category": "account",
        "keywords": ["login", "password", "access", "locked", "account", "reset", "sign in", "2fa", "mfa"],
        "title": "Account Access and Login Help",
        "content": (
            "Reset your password at /forgot-password. Account lockouts are automatically lifted after 30 minutes. "
            "If you still can't access your account, contact support with your registered email address."
        ),
    },
    {
        "id": "KB-004",
        "category": "feature",
        "keywords": ["how to", "feature", "setup", "configure", "integrate", "api", "documentation", "guide"],
        "title": "Product Features and Setup Guides",
        "content": (
            "Full documentation is available at docs.example.com. API integration guides are at docs.example.com/api. "
            "Premium and enterprise plans include free onboarding calls — book one from your dashboard."
        ),
    },
    {
        "id": "KB-005",
        "category": "cancellation",
        "keywords": ["cancel", "cancellation", "unsubscribe", "close account", "quit", "stop service", "downgrade"],
        "title": "Cancellation and Downgrade Policy",
        "content": (
            "You can cancel at any time from Account > Subscription. Cancellations take effect at the end of your "
            "current billing period. Account data is retained for 30 days after cancellation."
        ),
    },
]

_TICKETS_FILE = Path(__file__).parent / "tickets.json"


def _load_tickets() -> dict:
    if _TICKETS_FILE.exists():
        try:
            return json.loads(_TICKETS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _persist_tickets(tickets: dict) -> None:
    try:
        _TICKETS_FILE.write_text(json.dumps(tickets, indent=2, default=str))
    except OSError:
        pass


_tickets: dict = _load_tickets()


def get_customer(customer_id: str) -> Optional[dict]:
    return CUSTOMERS.get(customer_id)


def list_customers() -> list[dict]:
    return [{"id": c["id"], "name": c["name"], "plan": c["plan"]} for c in CUSTOMERS.values()]


def search_kb(query: str) -> list:
    query_lower = query.lower()
    scored = []
    for entry in KNOWLEDGE_BASE:
        score = sum(1 for kw in entry["keywords"] if kw in query_lower)
        if score > 0:
            scored.append({**entry, "relevance_score": score})
    return sorted(scored, key=lambda x: x["relevance_score"], reverse=True)


def save_ticket(ticket: dict) -> str:
    ticket_id = f"TKT-{str(uuid.uuid4())[:8].upper()}"
    ticket["id"] = ticket_id
    _tickets[ticket_id] = ticket
    _persist_tickets(_tickets)
    return ticket_id


def get_all_tickets() -> list:
    return list(_tickets.values())


def get_ticket(ticket_id: str) -> Optional[dict]:
    return _tickets.get(ticket_id)
