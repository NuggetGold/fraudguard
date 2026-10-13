from typing import List, Optional

from app.engine.evaluator import FraudEvaluator
from app.engine.rules.base import BaseFraudRule
from app.enums import RiskLevel, TransactionStatus
from app.models.transaction import (
    EvaluationResult,
    GeoLocation,
    RuleViolation,
    TransactionRequest,
)


def create_sample_request(amount: float = 3000.0) -> TransactionRequest:
    return TransactionRequest(
        account_id="ACC-EVAL-01",
        recipient_id="RECIP-01",
        amount=amount,
        currency="RUB",
        ip_address="192.168.1.100",
        device_id="DEV-OK",
        location=GeoLocation(city="Москва", latitude=55.7558, longitude=37.6173),
    )


class MockRule(BaseFraudRule):
    def __init__(self, violation: Optional[RuleViolation]) -> None:
        self._violation = violation

    @property
    def rule_id(self) -> str:
        return "MOCK_RULE"

    @property
    def rule_name(self) -> str:
        return "Тестовое правило"

    def evaluate(
        self,
        current: TransactionRequest,
        history: List[EvaluationResult]
    ) -> Optional[RuleViolation]:
        return self._violation


def test_evaluator_clean_transaction() -> None:
    evaluator = FraudEvaluator()
    req = create_sample_request(amount=2500.0)
    result = evaluator.evaluate(req, [])

    assert result.status == TransactionStatus.APPROVED
    assert result.risk_score == 0
    assert result.risk_level == RiskLevel.LOW
    assert len(result.violations) == 0


def test_evaluator_rejected_critical() -> None:
    evaluator = FraudEvaluator()
    req = create_sample_request(amount=600000.0)
    result = evaluator.evaluate(req, [])

    assert result.status == TransactionStatus.REJECTED
    assert result.risk_score >= 70
    assert result.risk_level == RiskLevel.CRITICAL
    assert len(result.violations) >= 1


def test_evaluator_manual_review_threshold() -> None:
    mock_violation = RuleViolation(
        rule_id="RULE_TEST_MEDIUM",
        rule_name="Подозрительное действие",
        description="Тестовое описание",
        risk_score_impact=35,
        severity=RiskLevel.MEDIUM,
    )
    evaluator = FraudEvaluator(rules=[MockRule(mock_violation)])
    req = create_sample_request()
    result = evaluator.evaluate(req, [])

    assert result.status == TransactionStatus.MANUAL_REVIEW
    assert result.risk_score == 35
    assert result.risk_level == RiskLevel.MEDIUM


def test_evaluator_high_severity_forces_review() -> None:
    mock_violation = RuleViolation(
        rule_id="RULE_TEST_HIGH",
        rule_name="Высокий риск",
        description="Тестовое описание",
        risk_score_impact=30,
        severity=RiskLevel.HIGH,
    )
    evaluator = FraudEvaluator(rules=[MockRule(mock_violation)])
    req = create_sample_request()
    result = evaluator.evaluate(req, [])

    assert result.status == TransactionStatus.MANUAL_REVIEW
    assert result.risk_level == RiskLevel.HIGH


def test_evaluator_score_capped_at_100() -> None:
    v1 = RuleViolation(
        rule_id="RULE_1",
        rule_name="Правило 1",
        description="Описание",
        risk_score_impact=60,
        severity=RiskLevel.HIGH,
    )
    v2 = RuleViolation(
        rule_id="RULE_2",
        rule_name="Правило 2",
        description="Описание",
        risk_score_impact=70,
        severity=RiskLevel.CRITICAL,
    )
    evaluator = FraudEvaluator(rules=[MockRule(v1), MockRule(v2)])
    req = create_sample_request()
    result = evaluator.evaluate(req, [])

    assert result.risk_score == 100
    assert result.status == TransactionStatus.REJECTED
    assert result.risk_level == RiskLevel.CRITICAL
