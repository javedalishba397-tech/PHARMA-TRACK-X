from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List

from backend.app.db.session import get_db
from backend.app.models.entities import User, StockAdjustment
from backend.app.schemas.schemas import StockAdjustmentCreate, StockAdjustmentOut, DashboardMetrics
from backend.app.services.auth_service import require_permission
from backend.app.services.stock_service import (
    get_stock_overview, write_off_stock, adjust_stock, get_dashboard_metrics
)

router = APIRouter(prefix="/stock", tags=["Stock & Alerts"])

@router.get("/dashboard", response_model=DashboardMetrics)
def dashboard_metrics_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dashboard_alerts"))
):
    return get_dashboard_metrics(db)

@router.get("/overview")
def stock_overview_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dashboard_alerts"))
):
    return get_stock_overview(db)

@router.post("/write-off")
def write_off_endpoint(
    data: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("stock_adjustments", require_write=True))
):
    """FR-35: Write off expired or damaged quantity with quantity and reason."""
    batch = write_off_stock(
        db,
        batch_id=data.batch_id,
        quantity=abs(data.quantity_change),
        reason=data.reason,
        user_id=pharmacist.user_id
    )
    return {"message": "Stock written off successfully.", "batch_id": batch.batch_id, "remaining_qty": batch.qty_remaining}

@router.post("/adjust")
def adjust_stock_endpoint(
    data: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("stock_adjustments", require_write=True))
):
    """FR-36: Adjust batch quantity (increase or decrease) with mandatory reason."""
    batch = adjust_stock(
        db,
        batch_id=data.batch_id,
        quantity_change=data.quantity_change,
        reason=data.reason,
        user_id=pharmacist.user_id,
        adjustment_type=data.adjustment_type or "Correction"
    )
    return {"message": "Stock adjusted successfully.", "batch_id": batch.batch_id, "remaining_qty": batch.qty_remaining}

@router.get("/adjustments", response_model=List[StockAdjustmentOut])
def list_adjustments(
    limit: int = 50,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("stock_adjustments"))
):
    adjs = db.query(StockAdjustment).order_by(StockAdjustment.adjusted_at.desc()).limit(limit).all()
    results = []
    for a in adjs:
        results.append({
            "adjustment_id": a.adjustment_id,
            "batch_id": a.batch_id,
            "batch_number": a.batch.batch_number if a.batch else None,
            "medicine_name": a.batch.medicine.name if a.batch and a.batch.medicine else None,
            "user_id": a.user_id,
            "user_name": a.user.full_name if a.user else None,
            "adjustment_type": a.adjustment_type,
            "quantity_change": a.quantity_change,
            "reason": a.reason,
            "adjusted_at": a.adjusted_at,
        })
    return results
