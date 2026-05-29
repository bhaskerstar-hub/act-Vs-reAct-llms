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


class GatewayMetadata(BaseModel):
    provider_name:  str
    display_name:   str
    routing_reason: str
    policy:         str
    latency_ms:     float
    cost:           float
    success:        bool
    engine_type:    str = "rule-based"


class ProviderStatsSchema(BaseModel):
    call_count:    int
    total_latency: float
    avg_latency:   float
    total_cost:    float
    avg_cost:      float
    error_count:   int


class GatewayStatsResponse(BaseModel):
    stats: dict[str, ProviderStatsSchema]


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
    gateway_metadata: Optional[GatewayMetadata] = None
