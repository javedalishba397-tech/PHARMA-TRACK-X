from dataclasses import dataclass
from typing import List, Optional
import math
import datetime
from .forecaster import ForecastResult

@dataclass
class BatchInput:
    batch_id: int
    medicine_id: int
    medicine_name: str
    batch_number: str
    qty_remaining: int
    days_to_expiry: int
    status: str  # "Active", "Near-Expiry", "Expired", etc.
    sell_first: bool = False

@dataclass
class ModuleParameters:
    forecast_horizon_days: int = 30
    forecast_confidence_pct: int = 80
    near_expiry_days: int = 90
    min_history_days: int = 30
    max_daily_cv: float = 1.0
    w_expiry_risk: float = 0.5
    w_stockout_risk: float = 0.3
    w_uncertainty: float = 0.2
    risk_low_max: int = 33
    risk_medium_max: int = 66
    min_lead_time_deliveries: int = 3
    max_discount_percent: float = 10.0

@dataclass
class RecommendationResult:
    batch_id: int
    forecast_id: Optional[int]
    generated_at: datetime.datetime
    lead_time_days_used: float
    risk_score: int
    risk_band: str  # "Low", "Medium", "High"
    action: str  # "Reorder", "Hold", "Prioritize FEFO", "Review"
    suggested_qty: Optional[int]
    explanation: str
    status: str = "Pending"

class DecisionEngine:
    """
    Expiry-Risk and Demand-Uncertainty-Aware Decision Engine.
    Implements Table 3.20, Figure 3.6, and FR-41 through FR-45.
    """

    def __init__(self, params: Optional[ModuleParameters] = None):
        self.params = params or ModuleParameters()

    def evaluate_batch(
        self,
        batch: BatchInput,
        forecast: ForecastResult,
        supplier_lead_time_days: float,
        usable_stock: int,
        all_active_batches_sorted_fefo: List[BatchInput],
        pending_orders_qty: int = 0,
        forecast_id: Optional[int] = None,
    ) -> RecommendationResult:
        """
        Evaluate a single batch using the 4-step decision hierarchy in Table 3.20.
        """
        now = datetime.datetime.now()
        horizon = forecast.horizon_days
        stock = batch.qty_remaining
        days_to_expiry = batch.days_to_expiry
        conf_level = forecast.confidence_level
        lead_time = supplier_lead_time_days

        # Daily demands using cautious bounds (FR-45):
        # Reorder assessments use upper demand bound;
        # Expiry assessments use lower demand bound.
        daily_upper = forecast.upper_bound / float(horizon) if horizon > 0 else 0.0
        daily_lower = forecast.lower_bound / float(horizon) if horizon > 0 else 0.0
        daily_expected = forecast.expected_demand / float(horizon) if horizon > 0 else 0.0

        # Stock cover in days based on usable stock and upper-bound daily demand
        if daily_upper > 1e-4:
            days_of_stock_cover = usable_stock / daily_upper
        else:
            days_of_stock_cover = 9999.0

        # FEFO simulation for projected unsold at expiry using lower-bound demand
        # Compute how much quantity from this batch will remain unsold at its expiry date
        # Lower bound daily sales means slowest expected consumption.
        demand_until_expiry = daily_lower * max(0, days_to_expiry)
        
        cumulative_prior_qty = 0
        for prior in all_active_batches_sorted_fefo:
            if prior.batch_id == batch.batch_id:
                break
            cumulative_prior_qty += prior.qty_remaining

        # Demand available for this batch after earlier batches are consumed
        demand_for_this_batch = max(0.0, demand_until_expiry - cumulative_prior_qty)
        projected_unsold_qty = max(0.0, float(stock) - demand_for_this_batch)
        unsold_ratio = (projected_unsold_qty / float(stock)) if stock > 0 else 0.0

        # Risk Score Components (FR-42):
        # 1. Expiry Risk (0 to 100): share of batch projected unsold at expiry
        comp_expiry_risk = min(100.0, max(0.0, unsold_ratio * 100.0))

        # 2. Stockout Risk (0 to 100):
        # Assesses whether usable stock (plus pending order) covers lead time demand
        lead_time_demand = daily_upper * lead_time
        if lead_time_demand > 1e-4:
            available_for_lead = usable_stock + pending_orders_qty
            if available_for_lead < lead_time_demand:
                comp_stockout_risk = min(100.0, max(0.0, (1.0 - (available_for_lead / lead_time_demand)) * 100.0))
            else:
                comp_stockout_risk = 0.0
        else:
            comp_stockout_risk = 0.0

        # 3. Forecast Uncertainty (0 to 100):
        # Range width relative to expected demand
        if forecast.expected_demand > 1e-4:
            range_width = forecast.upper_bound - forecast.lower_bound
            rel_uncertainty = range_width / forecast.expected_demand
            comp_uncertainty = min(100.0, rel_uncertainty * 50.0)
        else:
            comp_uncertainty = 90.0 if conf_level == "Low" else 30.0

        if conf_level == "Low":
            comp_uncertainty = max(comp_uncertainty, 80.0)

        raw_score = (
            self.params.w_expiry_risk * comp_expiry_risk +
            self.params.w_stockout_risk * comp_stockout_risk +
            self.params.w_uncertainty * comp_uncertainty
        )
        risk_score = int(min(100, max(0, round(raw_score))))

        if risk_score <= self.params.risk_low_max:
            risk_band = "Low"
        elif risk_score <= self.params.risk_medium_max:
            risk_band = "Medium"
        else:
            risk_band = "High"

        # Table 3.20 Decision Rules (evaluated in exact order)
        # Order 1: Review
        if forecast.history_days < self.params.min_history_days or conf_level == "Low" or forecast.history_days == 0:
            action = "Review"
            suggested_qty = None
            explanation = (
                f"Batch {batch.batch_number} has {stock} units in stock with {days_to_expiry} days to expiry. "
                f"Expected demand for the next {horizon} days is {int(forecast.expected_demand)} units "
                f"(range {int(forecast.lower_bound)}–{int(forecast.upper_bound)}, {conf_level} confidence). "
                f"Supplier lead time is {lead_time:.0f} days. "
                f"Rule 1 (Review) triggered: Sales history ({forecast.history_days} days) is below the minimum threshold "
                f"of {self.params.min_history_days} days or confidence is Low (CV={forecast.daily_cv:.2f}). "
                f"The system avoids automated ordering or holding until the pharmacist reviews this batch."
            )
            return RecommendationResult(
                batch_id=batch.batch_id,
                forecast_id=forecast_id,
                generated_at=now,
                lead_time_days_used=lead_time,
                risk_score=risk_score,
                risk_band=risk_band,
                action=action,
                suggested_qty=suggested_qty,
                explanation=explanation,
            )

        # Order 2: Reorder
        # Condition: Days of stock cover < supplier lead time and no pending order arrives in time
        effective_stock_with_pending = usable_stock + pending_orders_qty
        stock_cover_with_pending = effective_stock_with_pending / daily_upper if daily_upper > 1e-4 else 9999.0

        if days_of_stock_cover < lead_time and stock_cover_with_pending < lead_time:
            action = "Reorder"
            # Suggested quantity = upper-bound demand for (horizon + lead time) - usable stock - pending order
            total_target_period = horizon + lead_time
            target_upper_demand = daily_upper * total_target_period
            needed = target_upper_demand - usable_stock - pending_orders_qty
            suggested_qty = max(1, math.ceil(needed))
            explanation = (
                f"Batch {batch.batch_number} belongs to {batch.medicine_name} with current usable stock of {usable_stock} units "
                f"(this batch has {stock} units, expiring in {days_to_expiry} days). "
                f"Expected demand for the next {horizon} days is {int(forecast.expected_demand)} units "
                f"(range {int(forecast.lower_bound)}–{int(forecast.upper_bound)}, {conf_level} confidence). "
                f"Supplier lead time is {lead_time:.0f} days. "
                f"Rule 2 (Reorder) triggered: Days of stock cover ({days_of_stock_cover:.1f} days) is less than "
                f"the supplier lead time ({lead_time:.0f} days). A reorder of {suggested_qty} units is suggested."
            )
            return RecommendationResult(
                batch_id=batch.batch_id,
                forecast_id=forecast_id,
                generated_at=now,
                lead_time_days_used=lead_time,
                risk_score=risk_score,
                risk_band=risk_band,
                action=action,
                suggested_qty=suggested_qty,
                explanation=explanation,
            )

        # Order 3: Prioritize (FEFO)
        # Condition: Projected unsold quantity at expiry > 0 (using lower-bound demand) AND days to expiry <= near-expiry threshold
        if projected_unsold_qty > 0 and days_to_expiry <= self.params.near_expiry_days:
            action = "Prioritize FEFO"
            suggested_qty = None
            explanation = (
                f"Batch {batch.batch_number} has {stock} units and expires in {days_to_expiry} days. "
                f"Expected demand for the next {horizon} days is {int(forecast.expected_demand)} units "
                f"(range {int(forecast.lower_bound)}–{int(forecast.upper_bound)}, {conf_level} confidence). "
                f"Supplier lead time is {lead_time:.0f} days. "
                f"Rule 3 (Prioritize FEFO) triggered: At the lower demand estimate about {int(projected_unsold_qty)} units "
                f"would remain unsold at expiry (days to expiry {days_to_expiry} <= {self.params.near_expiry_days} threshold), "
                f"so this batch should be marked 'Sell First'."
            )
            return RecommendationResult(
                batch_id=batch.batch_id,
                forecast_id=forecast_id,
                generated_at=now,
                lead_time_days_used=lead_time,
                risk_score=risk_score,
                risk_band=risk_band,
                action=action,
                suggested_qty=suggested_qty,
                explanation=explanation,
            )

        # Order 4: Hold
        # Condition: None of the above: stock is adequate, so no new order should be placed
        action = "Hold"
        suggested_qty = None
        explanation = (
            f"Batch {batch.batch_number} has {stock} units with {days_to_expiry} days to expiry. "
            f"Expected demand for the next {horizon} days is {int(forecast.expected_demand)} units "
            f"(range {int(forecast.lower_bound)}–{int(forecast.upper_bound)}, {conf_level} confidence). "
            f"Supplier lead time is {lead_time:.0f} days. "
            f"Rule 4 (Hold) triggered: Current stock cover is adequate ({days_of_stock_cover:.1f} days) and "
            f"stock is projected to clear before expiry without significant waste. No reorder required."
        )
        return RecommendationResult(
            batch_id=batch.batch_id,
            forecast_id=forecast_id,
            generated_at=now,
            lead_time_days_used=lead_time,
            risk_score=risk_score,
            risk_band=risk_band,
            action=action,
            suggested_qty=suggested_qty,
            explanation=explanation,
        )
