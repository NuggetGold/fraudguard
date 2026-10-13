from typing import List, Optional

from app.engine.rules.base import BaseFraudRule
from app.enums import RiskLevel
from app.models.transaction import EvaluationResult, RuleViolation, TransactionRequest


class SuspiciousDeviceRule(BaseFraudRule):
    @property
    def rule_id(self) -> str:
        return "RULE_DEVICE_ANOMALY"

    @property
    def rule_name(self) -> str:
        return "Аномалия устройства"

    def evaluate(
        self,
        current: TransactionRequest,
        history: List[EvaluationResult]
    ) -> Optional[RuleViolation]:
        device_accounts = {
            item.account_id for item in history
            if item.device_id == current.device_id
        }

        if len(device_accounts - {current.account_id}) >= 2:
            return RuleViolation(
                rule_id="RULE_DEVICE_FARM",
                rule_name="Устройство связано с несколькими аккаунтами",
                description=(
                    f"Устройство {current.device_id} уже использовалось для "
                    f"{len(device_accounts)} разных аккаунтов. Признак фермы аккаунтов"
                ),
                risk_score_impact=50,
                severity=RiskLevel.HIGH
            )

        user_devices = {
            item.device_id for item in history
            if item.account_id == current.account_id
        }

        if user_devices and current.device_id not in user_devices and current.amount >= 50000.0:
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                description=(
                    f"Вход с нового неизвестного устройства {current.device_id} "
                    f"при переводе крупной суммы ({current.amount:,.2f} {current.currency})"
                ),
                risk_score_impact=30,
                severity=RiskLevel.MEDIUM
            )

        return None
