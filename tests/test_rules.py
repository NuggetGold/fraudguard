from datetime import datetime, timedelta, timezone

from app.engine.rules.amount_rule import AmountThresholdRule
from app.engine.rules.device_rule import SuspiciousDeviceRule
from app.engine.rules.geo_rule import ImpossibleTravelRule
from app.engine.rules.velocity_rule import VelocityRule
from app.enums import RiskLevel, TransactionStatus
from app.models.transaction import EvaluationResult, GeoLocation, TransactionRequest


def create_request(
    account_id: str = "ACC-01",
    recipient_id: str = "RECIP-01",
    amount: float = 5000.0,
    currency: str = "RUB",
    ip_address: str = "192.168.1.1",
    device_id: str = "DEV-01",
    city: str = "Москва",
    lat: float = 55.7558,
    lon: float = 37.6173,
    timestamp: datetime = None,
) -> TransactionRequest:
    return TransactionRequest(
        account_id=account_id,
        recipient_id=recipient_id,
        amount=amount,
        currency=currency,
        ip_address=ip_address,
        device_id=device_id,
        location=GeoLocation(city=city, latitude=lat, longitude=lon),
        timestamp=timestamp or datetime.now(timezone.utc),
    )


def create_history_item(
    account_id: str = "ACC-01",
    amount: float = 5000.0,
    device_id: str = "DEV-01",
    city: str = "Москва",
    lat: float = 55.7558,
    lon: float = 37.6173,
    timestamp: datetime = None,
) -> EvaluationResult:
    return EvaluationResult(
        transaction_id="tx-test-id",
        account_id=account_id,
        recipient_id="RECIP-01",
        amount=amount,
        currency="RUB",
        timestamp=timestamp or datetime.now(timezone.utc),
        location=GeoLocation(city=city, latitude=lat, longitude=lon),
        ip_address="192.168.1.1",
        device_id=device_id,
        status=TransactionStatus.APPROVED,
        risk_score=0,
        risk_level=RiskLevel.LOW,
        violations=[],
    )


def test_amount_rule_normal() -> None:
    rule = AmountThresholdRule()
    req = create_request(amount=10000.0)
    violation = rule.evaluate(req, [])
    assert violation is None


def test_amount_rule_medium_threshold() -> None:
    rule = AmountThresholdRule()
    req = create_request(amount=200000.0)
    violation = rule.evaluate(req, [])
    assert violation is not None
    assert violation.rule_id == "RULE_AMOUNT_THRESHOLD"
    assert violation.severity == RiskLevel.MEDIUM
    assert violation.risk_score_impact == 35


def test_amount_rule_critical_threshold() -> None:
    rule = AmountThresholdRule()
    req = create_request(amount=600000.0)
    violation = rule.evaluate(req, [])
    assert violation is not None
    assert violation.rule_id == "RULE_AMOUNT_THRESHOLD"
    assert violation.severity == RiskLevel.CRITICAL
    assert violation.risk_score_impact == 75


def test_amount_rule_spike() -> None:
    rule = AmountThresholdRule()
    now = datetime.now(timezone.utc)
    history = [
        create_history_item(
            account_id="ACC-SPIKE",
            amount=3000.0,
            timestamp=now - timedelta(days=3),
        ),
        create_history_item(
            account_id="ACC-SPIKE",
            amount=3500.0,
            timestamp=now - timedelta(days=2),
        ),
        create_history_item(
            account_id="ACC-SPIKE",
            amount=4000.0,
            timestamp=now - timedelta(days=1),
        ),
    ]
    req = create_request(account_id="ACC-SPIKE", amount=50000.0, timestamp=now)
    violation = rule.evaluate(req, history)
    assert violation is not None
    assert violation.rule_id == "RULE_AMOUNT_SPIKE"
    assert violation.severity == RiskLevel.HIGH
    assert violation.risk_score_impact == 40


def test_velocity_rule_normal() -> None:
    rule = VelocityRule()
    now = datetime.now(timezone.utc)
    history = [
        create_history_item(account_id="ACC-VEL", timestamp=now - timedelta(seconds=20)),
    ]
    req = create_request(account_id="ACC-VEL", timestamp=now)
    violation = rule.evaluate(req, history)
    assert violation is None


def test_velocity_rule_medium_burst() -> None:
    rule = VelocityRule()
    now = datetime.now(timezone.utc)
    history = [
        create_history_item(account_id="ACC-VEL", timestamp=now - timedelta(seconds=30)),
        create_history_item(account_id="ACC-VEL", timestamp=now - timedelta(seconds=20)),
        create_history_item(account_id="ACC-VEL", timestamp=now - timedelta(seconds=10)),
    ]
    req = create_request(account_id="ACC-VEL", timestamp=now)
    violation = rule.evaluate(req, history)
    assert violation is not None
    assert violation.rule_id == "RULE_VELOCITY_BURST"
    assert violation.severity == RiskLevel.MEDIUM
    assert violation.risk_score_impact == 40


def test_velocity_rule_high_burst() -> None:
    rule = VelocityRule()
    now = datetime.now(timezone.utc)
    history = [
        create_history_item(account_id="ACC-VEL", timestamp=now - timedelta(seconds=40)),
        create_history_item(account_id="ACC-VEL", timestamp=now - timedelta(seconds=30)),
        create_history_item(account_id="ACC-VEL", timestamp=now - timedelta(seconds=20)),
        create_history_item(account_id="ACC-VEL", timestamp=now - timedelta(seconds=10)),
    ]
    req = create_request(account_id="ACC-VEL", timestamp=now)
    violation = rule.evaluate(req, history)
    assert violation is not None
    assert violation.rule_id == "RULE_VELOCITY_BURST"
    assert violation.severity == RiskLevel.HIGH
    assert violation.risk_score_impact == 60


def test_geo_rule_normal_travel() -> None:
    rule = ImpossibleTravelRule()
    now = datetime.now(timezone.utc)
    history = [
        create_history_item(
            account_id="ACC-GEO",
            city="Москва",
            lat=55.7558,
            lon=37.6173,
            timestamp=now - timedelta(hours=5),
        ),
    ]
    req = create_request(
        account_id="ACC-GEO",
        city="Санкт-Петербург",
        lat=59.9343,
        lon=30.3351,
        timestamp=now,
    )
    violation = rule.evaluate(req, history)
    assert violation is None


def test_geo_rule_impossible_travel() -> None:
    rule = ImpossibleTravelRule()
    now = datetime.now(timezone.utc)
    history = [
        create_history_item(
            account_id="ACC-GEO-FAST",
            city="Москва",
            lat=55.7558,
            lon=37.6173,
            timestamp=now - timedelta(seconds=10),
        ),
    ]
    req = create_request(
        account_id="ACC-GEO-FAST",
        city="Владивосток",
        lat=43.1155,
        lon=131.8855,
        timestamp=now,
    )
    violation = rule.evaluate(req, history)
    assert violation is not None
    assert violation.rule_id == "RULE_IMPOSSIBLE_TRAVEL"
    assert violation.severity == RiskLevel.HIGH
    assert violation.risk_score_impact == 70


def test_device_rule_farm() -> None:
    rule = SuspiciousDeviceRule()
    history = [
        create_history_item(account_id="USER-A", device_id="SHARED-DEV"),
        create_history_item(account_id="USER-B", device_id="SHARED-DEV"),
    ]
    req = create_request(account_id="USER-C", device_id="SHARED-DEV")
    violation = rule.evaluate(req, history)
    assert violation is not None
    assert violation.rule_id == "RULE_DEVICE_FARM"
    assert violation.severity == RiskLevel.HIGH


def test_device_rule_unknown_device_large_amount() -> None:
    rule = SuspiciousDeviceRule()
    history = [
        create_history_item(account_id="USER-ALONE", device_id="PHONE-01"),
    ]
    req = create_request(account_id="USER-ALONE", device_id="UNKNOWN-DEV", amount=70000.0)
    violation = rule.evaluate(req, history)
    assert violation is not None
    assert violation.rule_id == "RULE_DEVICE_ANOMALY"
    assert violation.severity == RiskLevel.MEDIUM
    assert violation.risk_score_impact == 30
