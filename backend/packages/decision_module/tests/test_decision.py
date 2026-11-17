import pytest
import datetime
from decision_module.forecaster import DemandForecaster, ForecastResult
from decision_module.engine import DecisionEngine, BatchInput, ModuleParameters

def test_forecaster_low_history_confidence():
    forecaster = DemandForecaster(min_history_days=30, max_daily_cv=1.0)
    # Only 10 days of history
    daily_sales = [5.0, 6.0, 4.0, 5.0, 5.0, 7.0, 4.0, 6.0, 5.0, 5.0]
    result = forecaster.forecast_from_daily_sales(medicine_id=1, daily_sales=daily_sales)
    
    assert result.confidence_level == "Low"
    assert result.history_days == 10
    assert result.expected_demand > 0
    assert result.lower_bound <= result.expected_demand <= result.upper_bound

def test_forecaster_high_cv_low_confidence():
    forecaster = DemandForecaster(min_history_days=30, max_daily_cv=1.0)
    # 40 days, but very erratic sales (CV > 1.0)
    daily_sales = [0.0] * 35 + [50.0, 60.0, 0.0, 70.0, 0.0]
    result = forecaster.forecast_from_daily_sales(medicine_id=2, daily_sales=daily_sales)
    
    assert result.confidence_level == "Low"
    assert result.daily_cv > 1.0

def test_forecaster_high_confidence():
    forecaster = DemandForecaster(min_history_days=30, max_daily_cv=1.0)
    # 60 days, very stable sales
    daily_sales = [10.0 + (i % 2) for i in range(60)]
    result = forecaster.forecast_from_daily_sales(medicine_id=3, daily_sales=daily_sales)
    
    assert result.confidence_level == "High"
    assert result.history_days == 60
    assert result.daily_cv < 0.4

def test_decision_rule_1_review():
    engine = DecisionEngine()
    batch = BatchInput(
        batch_id=101,
        medicine_id=1,
        medicine_name="Amoxicillin 500mg",
        batch_number="B-101",
        qty_remaining=50,
        days_to_expiry=120,
        status="Active",
    )
    # Low confidence forecast
    forecast = ForecastResult(
        medicine_id=1,
        generated_at=datetime.datetime.now(),
        horizon_days=30,
        expected_demand=60.0,
        lower_bound=20.0,
        upper_bound=100.0,
        confidence_pct=80,
        confidence_level="Low",
        history_days=15,
        daily_cv=1.2,
        model_name="Baseline SMA",
        daily_mean=2.0,
        daily_std=2.4,
    )
    
    rec = engine.evaluate_batch(
        batch=batch,
        forecast=forecast,
        supplier_lead_time_days=7.0,
        usable_stock=50,
        all_active_batches_sorted_fefo=[batch],
        pending_orders_qty=0,
    )
    
    assert rec.action == "Review"
    assert rec.suggested_qty is None
    # Verify 5 mandatory inputs in explanation (FR-44, AC-5)
    assert "50 units" in rec.explanation or "stock" in rec.explanation.lower()
    assert "120 days" in rec.explanation or "expiry" in rec.explanation.lower()
    assert "Expected demand" in rec.explanation
    assert "Low confidence" in rec.explanation
    assert "7 days" in rec.explanation

def test_decision_rule_2_reorder():
    engine = DecisionEngine()
    batch = BatchInput(
        batch_id=102,
        medicine_id=2,
        medicine_name="Paracetamol 500mg",
        batch_number="B-102",
        qty_remaining=20,
        days_to_expiry=200,
        status="Active",
    )
    # High confidence forecast, high demand: expected 300, upper 330 -> ~11 units/day
    # Usable stock 20 -> stock cover 20 / 11 = ~1.8 days < supplier lead time 7 days
    forecast = ForecastResult(
        medicine_id=2,
        generated_at=datetime.datetime.now(),
        horizon_days=30,
        expected_demand=300.0,
        lower_bound=270.0,
        upper_bound=330.0,
        confidence_pct=80,
        confidence_level="High",
        history_days=60,
        daily_cv=0.2,
        model_name="Baseline SMA",
        daily_mean=10.0,
        daily_std=2.0,
    )
    
    rec = engine.evaluate_batch(
        batch=batch,
        forecast=forecast,
        supplier_lead_time_days=7.0,
        usable_stock=20,
        all_active_batches_sorted_fefo=[batch],
        pending_orders_qty=0,
    )
    
    assert rec.action == "Reorder"
    assert rec.suggested_qty is not None
    assert rec.suggested_qty > 0
    # Explanation checks
    assert "Expected demand" in rec.explanation
    assert "High confidence" in rec.explanation

def test_decision_rule_3_prioritize_fefo():
    engine = DecisionEngine(ModuleParameters(near_expiry_days=90))
    batch = BatchInput(
        batch_id=103,
        medicine_id=3,
        medicine_name="Insulin Regular",
        batch_number="B-103",
        qty_remaining=100,
        days_to_expiry=30,  # near expiry (<= 90)
        status="Near-Expiry",
    )
    # Demand lower bound is low: expected 30, lower 15 -> ~0.5 units/day
    # In 30 days, demand is only 15 units. 100 - 15 = 85 units projected unsold!
    forecast = ForecastResult(
        medicine_id=3,
        generated_at=datetime.datetime.now(),
        horizon_days=30,
        expected_demand=30.0,
        lower_bound=15.0,
        upper_bound=45.0,
        confidence_pct=80,
        confidence_level="Medium",
        history_days=45,
        daily_cv=0.5,
        model_name="Baseline SMA",
        daily_mean=1.0,
        daily_std=0.5,
    )
    
    rec = engine.evaluate_batch(
        batch=batch,
        forecast=forecast,
        supplier_lead_time_days=5.0,
        usable_stock=100,
        all_active_batches_sorted_fefo=[batch],
        pending_orders_qty=0,
    )
    
    assert rec.action == "Prioritize FEFO"
    assert rec.suggested_qty is None
    assert "Sell First" in rec.explanation or "sold first" in rec.explanation.lower()

def test_decision_rule_4_hold():
    engine = DecisionEngine(ModuleParameters(near_expiry_days=90))
    batch = BatchInput(
        batch_id=104,
        medicine_id=4,
        medicine_name="Cetirizine 10mg",
        batch_number="B-104",
        qty_remaining=100,
        days_to_expiry=365,  # 1 year away
        status="Active",
    )
    # Demand: 60 units in 30 days, lower 50, upper 70.
    # Stock cover = 100 / (70/30) = 42.8 days > lead time 5 days.
    # Expiry 365 days >> 90 days. Stock adequate.
    forecast = ForecastResult(
        medicine_id=4,
        generated_at=datetime.datetime.now(),
        horizon_days=30,
        expected_demand=60.0,
        lower_bound=50.0,
        upper_bound=70.0,
        confidence_pct=80,
        confidence_level="Medium",
        history_days=45,
        daily_cv=0.3,
        model_name="Baseline SMA",
        daily_mean=2.0,
        daily_std=0.6,
    )
    
    rec = engine.evaluate_batch(
        batch=batch,
        forecast=forecast,
        supplier_lead_time_days=5.0,
        usable_stock=100,
        all_active_batches_sorted_fefo=[batch],
        pending_orders_qty=0,
    )
    
    assert rec.action == "Hold"
    assert rec.suggested_qty is None
    assert "adequate" in rec.explanation.lower()
