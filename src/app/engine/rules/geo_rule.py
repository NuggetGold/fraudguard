import math
from datetime import datetime, timezone
from typing import List, Optional

from app.config import settings
from app.engine.rules.base import BaseFraudRule
from app.enums import RiskLevel
from app.models.transaction import EvaluationResult, RuleViolation, TransactionRequest


class ImpossibleTravelRule(BaseFraudRule):
    @property
    def rule_id(self) -> str:
        return "RULE_IMPOSSIBLE_TRAVEL"

    @property
    def rule_name(self) -> str:
        return "Невозможная скорость перемещения"

    @staticmethod
    def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius_km = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return radius_km * c

    def evaluate(
        self,
        current: TransactionRequest,
        history: List[EvaluationResult]
    ) -> Optional[RuleViolation]:
        current_time = current.timestamp or datetime.now(timezone.utc)
        user_history = [
            item for item in history
            if item.account_id == current.account_id
        ]
        if not user_history:
            return None

        previous = user_history[-1]
        time_diff_seconds = abs((current_time - previous.timestamp).total_seconds())

        if time_diff_seconds <= 0:
            time_diff_seconds = 1.0

        time_diff_hours = time_diff_seconds / 3600.0

        distance_km = self._haversine_distance_km(
            previous.location.latitude,
            previous.location.longitude,
            current.location.latitude,
            current.location.longitude,
        )

        if distance_km < 30.0:
            return None

        speed_kmh = distance_km / time_diff_hours

        if speed_kmh > settings.geo_max_speed_kmh:
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                description=(
                    f"Перемещение между {previous.location.city} и {current.location.city} "
                    f"({distance_km:.1f} км за {int(time_diff_seconds)} сек.) требует скорости "
                    f"{speed_kmh:.0f} км/ч (порог {settings.geo_max_speed_kmh:.0f} км/ч)"
                ),
                risk_score_impact=70,
                severity=RiskLevel.HIGH
            )

        return None
