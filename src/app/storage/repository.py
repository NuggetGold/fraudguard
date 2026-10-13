import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.enums import ReviewAction, TransactionStatus
from app.models.transaction import EvaluationResult, SystemMetrics


class TransactionRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._transactions: List[EvaluationResult] = []
        self._transactions_by_id: Dict[str, EvaluationResult] = {}
        self._idempotency_keys: Dict[str, EvaluationResult] = {}

    def save_transaction(self, result: EvaluationResult) -> EvaluationResult:
        with self._lock:
            self._transactions.append(result)
            self._transactions_by_id[result.transaction_id] = result
            return result

    def get_by_id(self, transaction_id: str) -> Optional[EvaluationResult]:
        with self._lock:
            return self._transactions_by_id.get(transaction_id)

    def get_by_idempotency_key(self, key: str) -> Optional[EvaluationResult]:
        with self._lock:
            return self._idempotency_keys.get(key)

    def save_idempotency(self, key: str, result: EvaluationResult) -> None:
        with self._lock:
            self._idempotency_keys[key] = result

    def list_transactions(
        self,
        status: Optional[TransactionStatus] = None,
        limit: int = 50
    ) -> List[EvaluationResult]:
        with self._lock:
            if status is None:
                return list(reversed(self._transactions))[:limit]
            filtered = [tx for tx in reversed(self._transactions) if tx.status == status]
            return filtered[:limit]

    def update_review(
        self,
        transaction_id: str,
        action: ReviewAction,
        note: str
    ) -> Optional[EvaluationResult]:
        with self._lock:
            current = self._transactions_by_id.get(transaction_id)
            if not current:
                return None

            new_status = (
                TransactionStatus.APPROVED
                if action == ReviewAction.APPROVE
                else TransactionStatus.REJECTED
            )

            updated = current.model_copy(
                update={
                    "status": new_status,
                    "reviewer_note": note,
                    "resolved_at": datetime.now(timezone.utc),
                }
            )

            self._transactions_by_id[transaction_id] = updated
            for index, item in enumerate(self._transactions):
                if item.transaction_id == transaction_id:
                    self._transactions[index] = updated
                    break

            return updated

    def get_metrics(self) -> SystemMetrics:
        with self._lock:
            total = len(self._transactions)
            approved = sum(
                1 for tx in self._transactions
                if tx.status == TransactionStatus.APPROVED
            )
            review = sum(
                1 for tx in self._transactions
                if tx.status == TransactionStatus.MANUAL_REVIEW
            )
            rejected = sum(
                1 for tx in self._transactions
                if tx.status == TransactionStatus.REJECTED
            )
            avg_risk = (
                round(sum(tx.risk_score for tx in self._transactions) / total, 2)
                if total > 0
                else 0.0
            )

            return SystemMetrics(
                total_transactions=total,
                approved_count=approved,
                review_count=review,
                rejected_count=rejected,
                average_risk_score=avg_risk,
            )

    def get_all(self) -> List[EvaluationResult]:
        with self._lock:
            return list(self._transactions)

    def clear(self) -> None:
        with self._lock:
            self._transactions.clear()
            self._transactions_by_id.clear()
            self._idempotency_keys.clear()
