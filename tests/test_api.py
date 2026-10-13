import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_repository
from app.enums import ReviewAction, TransactionStatus
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_repository() -> None:
    repo = get_repository()
    repo.clear()
    yield
    repo.clear()


def sample_payload(
    account_id: str = "ACC-API-1",
    amount: float = 2500.0,
    city: str = "Москва",
) -> dict:
    return {
        "account_id": account_id,
        "recipient_id": "RECIP-MERCHANT-1",
        "amount": amount,
        "currency": "RUB",
        "ip_address": "194.87.1.2",
        "device_id": "DEV-API-01",
        "location": {
            "city": city,
            "latitude": 55.7558,
            "longitude": 37.6173,
        },
    }


def test_evaluate_endpoint_success() -> None:
    response = client.post("/api/v1/transactions/evaluate", json=sample_payload())
    assert response.status_code == 200
    data = response.json()
    assert "transaction_id" in data
    assert data["account_id"] == "ACC-API-1"
    assert data["status"] == TransactionStatus.APPROVED.value
    assert data["risk_score"] == 0


def test_idempotency_key_behavior() -> None:
    headers = {"Idempotency-Key": "IDEM-KEY-UNIQUE-1"}
    first_res = client.post(
        "/api/v1/transactions/evaluate",
        headers=headers,
        json=sample_payload(amount=3000.0),
    )
    assert first_res.status_code == 200
    first_data = first_res.json()
    first_id = first_data["transaction_id"]

    second_res = client.post(
        "/api/v1/transactions/evaluate",
        headers=headers,
        json=sample_payload(amount=999999.0),
    )
    assert second_res.status_code == 200
    second_data = second_res.json()

    assert second_data["transaction_id"] == first_id
    assert second_data["amount"] == 3000.0


def test_list_transactions_with_filters() -> None:
    client.post("/api/v1/transactions/evaluate", json=sample_payload(amount=1000.0))
    client.post("/api/v1/transactions/evaluate", json=sample_payload(amount=600000.0))

    all_res = client.get("/api/v1/transactions")
    assert all_res.status_code == 200
    assert len(all_res.json()) == 2

    rejected_res = client.get("/api/v1/transactions?status=REJECTED")
    assert rejected_res.status_code == 200
    rejected_list = rejected_res.json()
    assert len(rejected_list) == 1
    assert rejected_list[0]["status"] == TransactionStatus.REJECTED.value

    approved_res = client.get("/api/v1/transactions?status=APPROVED")
    assert approved_res.status_code == 200
    approved_list = approved_res.json()
    assert len(approved_list) == 1
    assert approved_list[0]["status"] == TransactionStatus.APPROVED.value


def test_get_transaction_by_id_and_not_found() -> None:
    create_res = client.post("/api/v1/transactions/evaluate", json=sample_payload())
    created = create_res.json()
    tx_id = created["transaction_id"]

    get_res = client.get(f"/api/v1/transactions/{tx_id}")
    assert get_res.status_code == 200
    assert get_res.json()["transaction_id"] == tx_id

    missing_res = client.get("/api/v1/transactions/unknown-id-000")
    assert missing_res.status_code == 404
    assert missing_res.json()["detail"] == "Транзакция не найдена"


def test_review_transaction() -> None:
    create_res = client.post("/api/v1/transactions/evaluate", json=sample_payload(amount=200000.0))
    created = create_res.json()
    assert created["status"] == TransactionStatus.MANUAL_REVIEW.value
    tx_id = created["transaction_id"]

    review_res = client.post(
        f"/api/v1/transactions/{tx_id}/review",
        json={
            "action": ReviewAction.APPROVE.value,
            "reviewer_note": "Клиент подтвердил платеж по звонку",
        },
    )
    assert review_res.status_code == 200
    updated = review_res.json()
    assert updated["status"] == TransactionStatus.APPROVED.value
    assert updated["reviewer_note"] == "Клиент подтвердил платеж по звонку"
    assert updated["resolved_at"] is not None

    missing_review = client.post(
        "/api/v1/transactions/unknown-id/review",
        json={
            "action": ReviewAction.REJECT.value,
            "reviewer_note": "Отказ",
        },
    )
    assert missing_review.status_code == 404
    assert missing_review.json()["detail"] == "Транзакция не найдена"


def test_metrics_endpoint() -> None:
    client.post("/api/v1/transactions/evaluate", json=sample_payload(amount=2000.0))
    client.post("/api/v1/transactions/evaluate", json=sample_payload(amount=200000.0))
    client.post("/api/v1/transactions/evaluate", json=sample_payload(amount=700000.0))

    metrics_res = client.get("/api/v1/metrics")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()

    assert metrics["total_transactions"] == 3
    assert metrics["approved_count"] == 1
    assert metrics["review_count"] == 1
    assert metrics["rejected_count"] == 1
    assert metrics["average_risk_score"] > 0
