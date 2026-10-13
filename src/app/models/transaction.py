import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.enums import ReviewAction, RiskLevel, TransactionStatus


class GeoLocation(BaseModel):
    city: str = Field(..., min_length=1)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class TransactionRequest(BaseModel):
    account_id: str = Field(..., min_length=3)
    recipient_id: str = Field(..., min_length=3)
    amount: float = Field(..., gt=0.0)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    ip_address: str = Field(..., min_length=7)
    device_id: str = Field(..., min_length=3)
    location: GeoLocation
    timestamp: Optional[datetime] = None


class RuleViolation(BaseModel):
    rule_id: str
    rule_name: str
    description: str
    risk_score_impact: int
    severity: RiskLevel


class EvaluationResult(BaseModel):
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str
    recipient_id: str
    amount: float
    currency: str
    timestamp: datetime
    location: GeoLocation
    ip_address: str
    device_id: str
    status: TransactionStatus
    risk_score: int
    risk_level: RiskLevel
    violations: List[RuleViolation]
    reviewer_note: Optional[str] = None
    resolved_at: Optional[datetime] = None


class ManualReviewRequest(BaseModel):
    action: ReviewAction
    reviewer_note: str = Field(..., min_length=2)


class SystemMetrics(BaseModel):
    total_transactions: int
    approved_count: int
    review_count: int
    rejected_count: int
    average_risk_score: float
