from app.engine.evaluator import FraudEvaluator
from app.storage.repository import TransactionRepository

_repository = TransactionRepository()
_evaluator = FraudEvaluator()


def get_repository() -> TransactionRepository:
    return _repository


def get_evaluator() -> FraudEvaluator:
    return _evaluator
