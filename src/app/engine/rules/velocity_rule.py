from datetime import datetime, timezone
from typing import List, Optional

from app.config import settings
from app.engine.rules.base import BaseFraudRule
from app.enums import RiskLevel
from app.models.transaction import EvaluationResult, RuleViolation, TransactionRequest


class VelocityRule(BaseFraudRule):
    @property
    def rule_id(self) -> str:
        return "RULE_VELOCITY_BURST"

    @property
    def rule_name(self) -> str:
        return "Высокая частота транзакций"

    def evaluate(
        self,
        current: TransactionRequest,
        history: List[EvaluationResult]
    ) -> Optional[RuleViolation]:
        current_time = current.timestamp or datetime.now(timezone.utc)
        window_seconds = settings.velocity_window_seconds

        recent_txs = [
            item for item in history
            if item.account_id == current.account_id
            and (current_time - item.timestamp).total_seconds() <= window_seconds
            and (current_time - item.timestamp).total_seconds() >= 0
        ]

        tx_count = len(recent_txs) + 1

        if tx_count >= 5:
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                description=(
                    f"Обнаружена серия из {tx_count} операций за {window_seconds} сек. "
                    f"Подозрение на перебор или списание ботом"
                ),
                risk_score_impact=60,
                severity=RiskLevel.HIGH
            )

        if tx_count > settings.velocity_max_count:
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                description=(
                    f"Превышена допустимая частота: {tx_count} операций за "
                    f"{window_seconds} сек (максимум {settings.velocity_max_count})"
                ),
                risk_score_impact=40,
                severity=RiskLevel.MEDIUM
            )

        return None
