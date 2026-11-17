from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.db.session import get_db
from backend.app.models.entities import User, DecisionLog
from backend.app.schemas.schemas import RecommendationOut, RecommendationDecision, DecisionLogOut
from backend.app.services.auth_service import require_permission
from backend.app.services.recommendation_service import (
    get_recommendations_list, run_all_recommendations, generate_recommendations_for_medicine, decide_recommendation
)

router = APIRouter(prefix="/recommendations", tags=["Expiry-Risk Decision Support"])

@router.get("", response_model=List[RecommendationOut])
def list_recommendations(
    medicine_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    status: Optional[str] = Query("Pending"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("forecasts_view"))
):
    """Figure 3.1: Table of batches with stock, days to expiry, expected demand and range, confidence label, risk score, recommended action."""
    return get_recommendations_list(db, medicine_id=medicine_id, action=action, status_filter=status)

@router.post("/run-all")
def trigger_all_recommendations(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("forecasts_view"))
):
    """FR-49: Automated daily run or batch refresh."""
    count = run_all_recommendations(db)
    return {"message": f"Evaluated batches and generated recommendations.", "count": count}

@router.post("/on-demand/{medicine_id}")
def run_on_demand(
    medicine_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("forecasts_view"))
):
    """FR-49: Generate recommendations on demand for a selected medicine."""
    recs = generate_recommendations_for_medicine(db, medicine_id)
    return {"message": f"Generated {len(recs)} recommendation(s) for medicine ID {medicine_id}."}

@router.post("/{recommendation_id}/decide", response_model=RecommendationOut)
def record_decision(
    recommendation_id: int,
    data: RecommendationDecision,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("recommendations_decision", require_write=True))
):
    """
    FR-46, FR-47, FR-48: Pharmacist approves, rejects, or modifies recommendation.
    Approved Reorder creates draft PO; approved Prioritize marks batch Sell First.
    """
    decide_recommendation(db, recommendation_id, data, pharmacist_user_id=pharmacist.user_id)
    all_recs = get_recommendations_list(db, status_filter="All")
    for r in all_recs:
        if r["recommendation_id"] == recommendation_id:
            return r
    return all_recs[0]

@router.get("/decision-history", response_model=List[DecisionLogOut])
def get_decision_history(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("forecasts_view"))
):
    """FR-51: Display history of recommendations and decisions."""
    logs = db.query(DecisionLog).order_by(DecisionLog.decided_at.desc()).limit(limit).all()
    results = []
    for l in logs:
        rec = l.recommendation
        batch = rec.batch if rec else None
        med = batch.medicine if batch else None

        results.append({
            "decision_id": l.decision_id,
            "recommendation_id": l.recommendation_id,
            "user_id": l.user_id,
            "user_name": l.user.full_name if l.user else None,
            "medicine_name": med.name if med else None,
            "batch_number": batch.batch_number if batch else None,
            "decision": l.decision,
            "final_action": l.final_action,
            "final_qty": l.final_qty,
            "comment": l.comment,
            "decided_at": l.decided_at,
        })
    return results
