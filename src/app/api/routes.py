from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.dependencies import get_evaluator, get_repository
from app.engine.evaluator import FraudEvaluator
from app.enums import TransactionStatus
from app.models.transaction import (
    EvaluationResult,
    ManualReviewRequest,
    SystemMetrics,
    TransactionRequest,
)
from app.storage.repository import TransactionRepository

router = APIRouter(prefix="/api/v1")


@router.post(
    "/transactions/evaluate",
    response_model=EvaluationResult,
    status_code=status.HTTP_200_OK,
)
def evaluate_transaction(
    payload: TransactionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    repository: TransactionRepository = Depends(get_repository),
    evaluator: FraudEvaluator = Depends(get_evaluator),
) -> EvaluationResult:
    if idempotency_key:
        cached = repository.get_by_idempotency_key(idempotency_key)
        if cached:
            return cached

    history = repository.get_all()
    result = evaluator.evaluate(payload, history)
    repository.save_transaction(result)

    if idempotency_key:
        repository.save_idempotency(idempotency_key, result)

    return result


@router.get("/transactions", response_model=List[EvaluationResult])
def list_transactions(
    status_filter: Optional[TransactionStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    repository: TransactionRepository = Depends(get_repository),
) -> List[EvaluationResult]:
    return repository.list_transactions(status=status_filter, limit=limit)


@router.get("/transactions/{transaction_id}", response_model=EvaluationResult)
def get_transaction(
    transaction_id: str,
    repository: TransactionRepository = Depends(get_repository),
) -> EvaluationResult:
    tx = repository.get_by_id(transaction_id)
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Транзакция не найдена",
        )
    return tx


@router.post("/transactions/{transaction_id}/review", response_model=EvaluationResult)
def review_transaction(
    transaction_id: str,
    payload: ManualReviewRequest,
    repository: TransactionRepository = Depends(get_repository),
) -> EvaluationResult:
    updated = repository.update_review(
        transaction_id=transaction_id,
        action=payload.action,
        note=payload.reviewer_note,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Транзакция не найдена",
        )
    return updated


@router.get("/metrics", response_model=SystemMetrics)
def get_metrics(
    repository: TransactionRepository = Depends(get_repository),
) -> SystemMetrics:
    return repository.get_metrics()
