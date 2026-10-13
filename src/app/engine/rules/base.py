from abc import ABC, abstractmethod
from typing import List, Optional

from app.models.transaction import EvaluationResult, RuleViolation, TransactionRequest


class BaseFraudRule(ABC):
    @property
    @abstractmethod
    def rule_id(self) -> str:
        pass

    @property
    @abstractmethod
    def rule_name(self) -> str:
        pass

    @abstractmethod
    def evaluate(
        self,
        current: TransactionRequest,
        history: List[EvaluationResult]
    ) -> Optional[RuleViolation]:
        pass
