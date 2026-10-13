from typing import List, Optional

from app.config import settings
from app.engine.rules.base import BaseFraudRule
from app.enums import RiskLevel
from app.models.transaction import EvaluationResult, RuleViolation, TransactionRequest


class AmountThresholdRule(BaseFraudRule):
    @property
    def rule_id(self) -> str:
        return "RULE_AMOUNT_THRESHOLD"

    @property
    def rule_name(self) -> str:
        return "Аномальная сумма транзакции"

    def evaluate(
        self,
        current: TransactionRequest,
        history: List[EvaluationResult]
    ) -> Optional[RuleViolation]:
        if current.amount >= settings.critical_transaction_amount:
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                description=(
                    f"Сумма транзакции ({current.amount:,.2f} {current.currency}) "
                    f"превышает критический лимит ({settings.critical_transaction_amount:,.2f} "
                    f"{current.currency})"
                ),
                risk_score_impact=75,
                severity=RiskLevel.CRITICAL
            )

        if current.amount >= settings.max_transaction_amount:
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                description=(
                    f"Сумма транзакции ({current.amount:,.2f} {current.currency}) "
                    f"превышает стандартный лимит контроля ({settings.max_transaction_amount:,.2f} "
                    f"{current.currency})"
                ),
                risk_score_impact=35,
                severity=RiskLevel.MEDIUM
            )

        user_history = [item for item in history if item.account_id == current.account_id]
        if len(user_history) >= 3:
            avg_amount = sum(item.amount for item in user_history) / len(user_history)
            if current.amount >= avg_amount * 5.0 and current.amount > 30000.0:
                return RuleViolation(
                    rule_id="RULE_AMOUNT_SPIKE",
                    rule_name="Резкое отклонение от среднего чека",
                    description=(
                        f"Сумма {current.amount:,.2f} {current.currency} превышает "
                        f"средний чек пользователя ({avg_amount:,.2f} {current.currency}) "
                        f"более чем в 5 раз"
                    ),
                    risk_score_impact=40,
                    severity=RiskLevel.HIGH
                )

        return None
