from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict
from fastapi import HTTPException, status
from sqlalchemy import func

from backend.app.models.entities import (
    Medicine, Batch, DemandForecast, Recommendation, DecisionLog, PurchaseOrder, PurchaseOrderItem, Sale, SaleItem, Supplier
)
from backend.app.schemas.schemas import RecommendationDecision, POCreate, POItemCreate
from backend.app.services.audit_service import log_audit
from backend.app.services.settings_service import (
    get_setting_int, get_setting_float
)
from backend.app.services.supplier_service import get_effective_lead_time
from backend.app.services.purchase_service import create_purchase_order

from decision_module.forecaster import DemandForecaster, ForecastResult
from decision_module.engine import DecisionEngine, BatchInput, ModuleParameters

def get_module_parameters(db: Session) -> ModuleParameters:
    return ModuleParameters(
        forecast_horizon_days=get_setting_int(db, "forecast_horizon_days", 30),
        forecast_confidence_pct=get_setting_int(db, "forecast_confidence_pct", 80),
        near_expiry_days=get_setting_int(db, "near_expiry_days", 90),
        min_history_days=get_setting_int(db, "min_history_days", 30),
        max_daily_cv=get_setting_float(db, "max_daily_cv", 1.0),
        w_expiry_risk=get_setting_float(db, "w_expiry_risk", 0.5),
        w_stockout_risk=get_setting_float(db, "w_stockout_risk", 0.3),
        w_uncertainty=get_setting_float(db, "w_uncertainty", 0.2),
        risk_low_max=get_setting_int(db, "risk_low_max", 33),
        risk_medium_max=get_setting_int(db, "risk_medium_max", 66),
        min_lead_time_deliveries=get_setting_int(db, "min_lead_time_deliveries", 3),
        max_discount_percent=get_setting_float(db, "max_discount_percent", 10.0),
    )

def aggregate_daily_sales(db: Session, medicine_id: int, lookback_days: int = 90) -> List[float]:
    """
    FR-38: Aggregate daily sold quantity per medicine from completed (non-voided) sales.
    Returns list of daily quantities in chronological order.
    """
    start_date = date.today() - timedelta(days=lookback_days)

    # Group completed sales by date
    daily_rows = db.query(
        func.date(Sale.sale_datetime).label("sale_date"),
        func.sum(SaleItem.quantity).label("daily_qty")
    ).join(SaleItem, Sale.sale_id == SaleItem.sale_id)\
     .join(Batch, SaleItem.batch_id == Batch.batch_id)\
     .filter(
        Batch.medicine_id == medicine_id,
        Sale.status == "Completed",
        func.date(Sale.sale_datetime) >= start_date
    ).group_by(func.date(Sale.sale_datetime)).all()

    sales_by_date = {row.sale_date: float(row.daily_qty) for row in daily_rows}
    
    # Fill full date range up to yesterday
    result_series = []
    for d in range(lookback_days, 0, -1):
        target_day = (date.today() - timedelta(days=d))
        target_day_str = target_day.isoformat()
        qty = sales_by_date.get(target_day, sales_by_date.get(target_day_str, 0.0))
        result_series.append(qty)

    return result_series

def get_pending_orders_quantity(db: Session, medicine_id: int) -> int:
    """FR-41: Check pending PO quantity for medicine."""
    pending_items = db.query(func.sum(PurchaseOrderItem.qty_ordered - PurchaseOrderItem.qty_received))\
        .join(PurchaseOrder, PurchaseOrderItem.po_id == PurchaseOrder.po_id)\
        .filter(
            PurchaseOrderItem.medicine_id == medicine_id,
            PurchaseOrder.status.in_(["Pending", "Partially Received"])
        ).scalar()
    return int(pending_items or 0)

def generate_recommendations_for_medicine(db: Session, medicine_id: int) -> List[Recommendation]:
    params = get_module_parameters(db)
    forecaster = DemandForecaster(
        default_horizon_days=params.forecast_horizon_days,
        default_confidence_pct=params.forecast_confidence_pct,
        min_history_days=params.min_history_days,
        max_daily_cv=params.max_daily_cv,
    )
    engine = DecisionEngine(params)

    medicine = db.query(Medicine).filter(Medicine.medicine_id == medicine_id).first()
    if not medicine or not medicine.is_active:
        return []

    # Daily sales series
    daily_sales = aggregate_daily_sales(db, medicine_id, lookback_days=params.forecast_horizon_days * 2)
    forecast_res = forecaster.forecast_from_daily_sales(
        medicine_id=medicine_id,
        daily_sales=daily_sales,
        horizon_days=params.forecast_horizon_days,
        confidence_pct=params.forecast_confidence_pct,
    )

    # Save forecast in DB
    db_forecast = DemandForecast(
        medicine_id=medicine_id,
        generated_at=forecast_res.generated_at,
        horizon_days=forecast_res.horizon_days,
        expected_demand=Decimal(str(forecast_res.expected_demand)),
        lower_bound=Decimal(str(forecast_res.lower_bound)),
        upper_bound=Decimal(str(forecast_res.upper_bound)),
        confidence_pct=forecast_res.confidence_pct,
        confidence_level=forecast_res.confidence_level,
        history_days=forecast_res.history_days,
        daily_cv=Decimal(str(forecast_res.daily_cv)),
        model_name=forecast_res.model_name,
    )
    db.add(db_forecast)
    db.commit()
    db.refresh(db_forecast)

    # Find supplier lead time (from recent PO supplier or first supplier)
    supplier_id = None
    recent_po = db.query(PurchaseOrder).join(PurchaseOrderItem).filter(PurchaseOrderItem.medicine_id == medicine_id).order_by(PurchaseOrder.po_id.desc()).first()
    if recent_po:
        supplier_id = recent_po.supplier_id
    else:
        first_supplier = db.query(Supplier).filter(Supplier.is_active == True).first()
        if first_supplier:
            supplier_id = first_supplier.supplier_id

    lead_time_days = get_effective_lead_time(db, supplier_id) if supplier_id else 7.0
    pending_qty = get_pending_orders_quantity(db, medicine_id)

    today = date.today()
    active_batches = db.query(Batch).filter(
        Batch.medicine_id == medicine_id,
        Batch.status.in_(["Active", "Near-Expiry"]),
        Batch.qty_remaining > 0
    ).order_by(Batch.expiry_date.asc()).all()

    usable_stock = sum(b.qty_remaining for b in active_batches)

    batch_inputs = []
    for b in active_batches:
        days = (b.expiry_date - today).days
        batch_inputs.append(
            BatchInput(
                batch_id=b.batch_id,
                medicine_id=b.medicine_id,
                medicine_name=medicine.name,
                batch_number=b.batch_number,
                qty_remaining=b.qty_remaining,
                days_to_expiry=days,
                status=b.status,
                sell_first=b.sell_first,
            )
        )

    recommendations = []
    for b_in in batch_inputs:
        rec_res = engine.evaluate_batch(
            batch=b_in,
            forecast=forecast_res,
            supplier_lead_time_days=lead_time_days,
            usable_stock=usable_stock,
            all_active_batches_sorted_fefo=batch_inputs,
            pending_orders_qty=pending_qty,
            forecast_id=db_forecast.forecast_id,
        )

        # FR-49: A new recommendation shall supersede an older Pending one for the same batch
        older_pending = db.query(Recommendation).filter(
            Recommendation.batch_id == b_in.batch_id,
            Recommendation.status == "Pending"
        ).all()
        for old in older_pending:
            old.status = "Superseded"

        db_rec = Recommendation(
            batch_id=b_in.batch_id,
            forecast_id=db_forecast.forecast_id,
            generated_at=rec_res.generated_at,
            lead_time_days_used=Decimal(str(rec_res.lead_time_days_used)),
            risk_score=rec_res.risk_score,
            risk_band=rec_res.risk_band,
            action=rec_res.action,
            suggested_qty=rec_res.suggested_qty,
            explanation=rec_res.explanation,
            status="Pending",
        )
        db.add(db_rec)
        recommendations.append(db_rec)

    db.commit()
    for r in recommendations:
        db.refresh(r)
    return recommendations

def run_all_recommendations(db: Session) -> int:
    """Executes the daily recommendation run across all active medicines."""
    medicines = db.query(Medicine).filter(Medicine.is_active == True).all()
    count = 0
    for med in medicines:
        recs = generate_recommendations_for_medicine(db, med.medicine_id)
        count += len(recs)
    return count

def decide_recommendation(
    db: Session,
    recommendation_id: int,
    data: RecommendationDecision,
    pharmacist_user_id: int
) -> Recommendation:
    """
    FR-47: The system shall let the Pharmacist Approve, Reject or Modify (change action or quantity)
    a recommendation with an optional comment.
    An approved Reorder shall create a pre-filled draft purchase order;
    An approved Prioritize shall mark the batch 'Sell First'.
    """
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found.")

    if rec.status != "Pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot decide on recommendation in '{rec.status}' status.")

    decision_type = data.decision.capitalize()
    if decision_type not in ("Approved", "Rejected", "Modified"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decision must be Approved, Rejected, or Modified.")

    final_action = data.final_action if data.final_action else rec.action
    final_qty = data.final_qty if data.final_qty is not None else rec.suggested_qty

    rec.status = decision_type

    # Execute approved actions
    if decision_type in ("Approved", "Modified"):
        if final_action == "Prioritize FEFO":
            batch = db.query(Batch).filter(Batch.batch_id == rec.batch_id).first()
            if batch:
                batch.sell_first = True
        elif final_action == "Reorder":
            # Create a pre-filled draft purchase order
            batch = db.query(Batch).filter(Batch.batch_id == rec.batch_id).first()
            if batch:
                med_id = batch.medicine_id
                # Find recent supplier or first supplier
                recent_po = db.query(PurchaseOrder).join(PurchaseOrderItem).filter(PurchaseOrderItem.medicine_id == med_id).order_by(PurchaseOrder.po_id.desc()).first()
                supplier_id = recent_po.supplier_id if recent_po else None
                if not supplier_id:
                    sup = db.query(Supplier).filter(Supplier.is_active == True).first()
                    supplier_id = sup.supplier_id if sup else 1

                reorder_qty = final_qty or 50
                med = db.query(Medicine).filter(Medicine.medicine_id == med_id).first()
                unit_cost = batch.purchase_price if batch.purchase_price > 0 else (med.unit_price * Decimal("0.7"))

                po_data = POCreate(
                    supplier_id=supplier_id,
                    items=[POItemCreate(medicine_id=med_id, qty_ordered=reorder_qty, unit_cost=unit_cost)],
                    notes=f"Draft PO generated from Recommendation #{rec.recommendation_id} ({rec.action})",
                )
                create_purchase_order(db, po_data, user_id=pharmacist_user_id, initial_status="Draft")

    # Record in decision_logs (FR-48)
    log_entry = DecisionLog(
        recommendation_id=rec.recommendation_id,
        user_id=pharmacist_user_id,
        decision=decision_type,
        final_action=final_action,
        final_qty=final_qty,
        comment=data.comment.strip() if data.comment else None,
        decided_at=datetime.utcnow(),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(rec)

    log_audit(
        db,
        action="DECIDE_RECOMMENDATION",
        user_id=pharmacist_user_id,
        entity="recommendations",
        entity_id=str(rec.recommendation_id),
        result=decision_type
    )
    return rec

def get_recommendations_list(
    db: Session,
    medicine_id: Optional[int] = None,
    action: Optional[str] = None,
    status_filter: Optional[str] = "Pending",
) -> List[dict]:
    """Figure 3.1 & FR-43: Filterable recommendations table."""
    q = db.query(Recommendation)
    if medicine_id:
        q = q.join(Batch).filter(Batch.medicine_id == medicine_id)
    if action and action != "All":
        q = q.filter(Recommendation.action == action)
    if status_filter and status_filter != "All":
        q = q.filter(Recommendation.status == status_filter)

    recs = q.order_by(Recommendation.risk_score.desc(), Recommendation.generated_at.desc()).all()
    today = date.today()
    results = []
    for r in recs:
        batch = r.batch
        med = batch.medicine if batch else None
        days = (batch.expiry_date - today).days if batch else 0
        forecast = r.forecast

        results.append({
            "recommendation_id": r.recommendation_id,
            "batch_id": r.batch_id,
            "batch_number": batch.batch_number if batch else "",
            "medicine_id": med.medicine_id if med else 0,
            "medicine_name": med.name if med else "Unknown",
            "stock": batch.qty_remaining if batch else 0,
            "days_to_expiry": days,
            "expected_demand": float(forecast.expected_demand) if forecast else 0.0,
            "lower_bound": float(forecast.lower_bound) if forecast else 0.0,
            "upper_bound": float(forecast.upper_bound) if forecast else 0.0,
            "confidence_level": forecast.confidence_level if forecast else "Medium",
            "lead_time_days_used": float(r.lead_time_days_used),
            "risk_score": r.risk_score,
            "risk_band": r.risk_band,
            "action": r.action,
            "suggested_qty": r.suggested_qty,
            "explanation": r.explanation,
            "status": r.status,
            "generated_at": r.generated_at,
        })
    return results
