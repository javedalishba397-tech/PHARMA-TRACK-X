from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import math
import datetime

@dataclass
class ForecastResult:
    medicine_id: int
    generated_at: datetime.datetime
    horizon_days: int
    expected_demand: float
    lower_bound: float
    upper_bound: float
    confidence_pct: int
    confidence_level: str  # "High", "Medium", "Low"
    history_days: int
    daily_cv: float
    model_name: str
    daily_mean: float
    daily_std: float

class DemandForecaster:
    """
    Baseline statistical forecaster meeting C-2, FR-38, FR-39, FR-40.
    Uses daily moving average / exponential smoothing with standard error estimation
    for explainable demand forecasting and uncertainty bounds.
    """

    def __init__(
        self,
        default_horizon_days: int = 30,
        default_confidence_pct: int = 80,
        min_history_days: int = 30,
        max_daily_cv: float = 1.0,
    ):
        self.default_horizon_days = default_horizon_days
        self.default_confidence_pct = default_confidence_pct
        self.min_history_days = min_history_days
        self.max_daily_cv = max_daily_cv

    @staticmethod
    def _z_score_for_confidence(confidence_pct: int) -> float:
        """
        Normal distribution two-tailed critical value Z for given confidence percentage.
        80% -> ~1.2816
        90% -> ~1.6449
        95% -> ~1.9599
        """
        if confidence_pct >= 95:
            return 1.96
        elif confidence_pct >= 90:
            return 1.645
        elif confidence_pct >= 85:
            return 1.44
        elif confidence_pct >= 80:
            return 1.282
        elif confidence_pct >= 75:
            return 1.15
        elif confidence_pct >= 70:
            return 1.036
        return 1.282

    def forecast_from_daily_sales(
        self,
        medicine_id: int,
        daily_sales: List[float],
        horizon_days: Optional[int] = None,
        confidence_pct: Optional[int] = None,
        min_history_days: Optional[int] = None,
        max_daily_cv: Optional[float] = None,
    ) -> ForecastResult:
        horizon = horizon_days or self.default_horizon_days
        conf_pct = confidence_pct or self.default_confidence_pct
        min_hist = min_history_days or self.min_history_days
        max_cv = max_daily_cv if max_daily_cv is not None else self.max_daily_cv

        history_count = len(daily_sales)
        now = datetime.datetime.now()

        # Handle zero or empty history
        if history_count == 0:
            return ForecastResult(
                medicine_id=medicine_id,
                generated_at=now,
                horizon_days=horizon,
                expected_demand=0.0,
                lower_bound=0.0,
                upper_bound=0.0,
                confidence_pct=conf_pct,
                confidence_level="Low",
                history_days=0,
                daily_cv=0.0,
                model_name="Baseline SMA (Zero History)",
                daily_mean=0.0,
                daily_std=0.0,
            )

        mean_val = sum(daily_sales) / float(history_count)
        if history_count > 1:
            variance = sum((x - mean_val) ** 2 for x in daily_sales) / float(history_count - 1)
            std_val = math.sqrt(variance)
        else:
            std_val = mean_val * 0.5

        daily_cv = (std_val / mean_val) if mean_val > 1e-6 else 0.0

        # Assign confidence level per FR-40:
        # "The level shall be Low when fewer than 30 days of history exist or when the coefficient
        # of variation of daily sales exceeds the configured threshold (default 1.0)."
        if history_count < min_hist or daily_cv > max_cv:
            confidence_level = "Low"
        elif daily_cv <= 0.4 and history_count >= 60:
            confidence_level = "High"
        else:
            confidence_level = "Medium"

        # Baseline expected demand for the horizon:
        expected_demand = mean_val * horizon

        # Standard error calculation:
        # Standard error over sum of H independent days: std * sqrt(H).
        # We add history penalty multiplier: sqrt(1 + 1/N) * penalty if N < 30.
        # "The forecast range shall become wider as history decreases or variability increases"
        history_penalty = 1.0
        if history_count < min_hist:
            history_penalty = 1.0 + (min_hist - history_count) / float(min_hist)

        z = self._z_score_for_confidence(conf_pct)
        # Margin of error
        se_horizon = std_val * math.sqrt(horizon) * math.sqrt(1.0 + 1.0 / max(1, history_count)) * history_penalty
        margin = z * se_horizon

        # When standard deviation is zero (e.g. steady non-zero sales or zero sales),
        # allow a minimal cautious margin if confidence is Low
        if margin < 1.0 and mean_val > 0 and confidence_level == "Low":
            margin = expected_demand * 0.3

        lower_bound = max(0.0, round(expected_demand - margin, 1))
        upper_bound = max(lower_bound, round(expected_demand + margin, 1))
        expected_demand = round(expected_demand, 1)

        return ForecastResult(
            medicine_id=medicine_id,
            generated_at=now,
            horizon_days=horizon,
            expected_demand=expected_demand,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            confidence_pct=conf_pct,
            confidence_level=confidence_level,
            history_days=history_count,
            daily_cv=round(daily_cv, 3),
            model_name="Baseline SMA & Normal Prediction Interval",
            daily_mean=round(mean_val, 3),
            daily_std=round(std_val, 3),
        )
