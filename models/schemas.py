from pydantic import BaseModel
from typing import Optional, List, Any
from enum import Enum
from datetime import datetime


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(str, Enum):
    OPEN = "open"
    AUTO_RESOLVED = "auto_resolved"
    ESCALATED = "escalated"


class TicketRequest(BaseModel):
    customer_id: str
    message: str
    channel: Optional[str] = "web"


class ReActTraceStep(BaseModel):
    step: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    observation: Optional[Any] = None


class TicketResponse(BaseModel):
    ticket_id: str
    customer_id: str
    urgency: UrgencyLevel
    status: TicketStatus
    category: str
    suggested_response: str
    assigned_to: str
    reasoning_trace: List[ReActTraceStep]
    created_at: datetime
