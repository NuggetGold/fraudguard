import uuid
from datetime import datetime, timezone
from typing import List

from app.engine.rules.amount_rule import AmountThresholdRule
from app.engine.rules.base import BaseFraudRule
from app.engine.rules.device_rule import SuspiciousDeviceRule
from app.engine.rules.geo_rule import ImpossibleTravelRule
from app.engine.rules.velocity_rule import VelocityRule
from app.enums import RiskLevel, TransactionStatus
from app.models.transaction import EvaluationResult, RuleViolation, TransactionRequest


class FraudEvaluator:
    def __init__(self, rules: List[BaseFraudRule] = None) -> None:
        if rules is None:
            self.rules: List[BaseFraudRule] = [
                AmountThresholdRule(),
                VelocityRule(),
                ImpossibleTravelRule(),
                SuspiciousDeviceRule(),
            ]
        else:
            self.rules = rules

    def evaluate(
        self,
        transaction: TransactionRequest,
        history: List[EvaluationResult]
    ) -> EvaluationResult:
        violations: List[RuleViolation] = []

        for rule in self.rules:
            violation = rule.evaluate(transaction, history)
            if violation:
                violations.append(violation)

        total_score = min(100, sum(v.risk_score_impact for v in violations))

        has_critical = any(v.severity == RiskLevel.CRITICAL for v in violations)
        has_high = any(v.severity == RiskLevel.HIGH for v in violations)

        if total_score >= 70 or has_critical:
            status = TransactionStatus.REJECTED
        elif total_score >= 35 or has_high:
            status = TransactionStatus.MANUAL_REVIEW
        else:
            status = TransactionStatus.APPROVED

        if total_score >= 80 or has_critical:
            risk_level = RiskLevel.CRITICAL
        elif total_score >= 50 or has_high:
            risk_level = RiskLevel.HIGH
        elif total_score >= 25:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        timestamp = transaction.timestamp or datetime.now(timezone.utc)

        return EvaluationResult(
            transaction_id=str(uuid.uuid4()),
            account_id=transaction.account_id,
            recipient_id=transaction.recipient_id,
            amount=transaction.amount,
            currency=transaction.currency,
            timestamp=timestamp,
            location=transaction.location,
            ip_address=transaction.ip_address,
            device_id=transaction.device_id,
            status=status,
            risk_score=total_score,
            risk_level=risk_level,
            violations=violations
        )
