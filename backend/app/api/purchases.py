from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from backend.app.db.session import get_db
from backend.app.models.entities import User
from backend.app.schemas.schemas import POCreate, POOut, POReceipt, POCancel
from backend.app.services.auth_service import require_permission
from backend.app.services.purchase_service import (
    create_purchase_order, receive_purchase_order, cancel_purchase_order, get_purchase_orders
)
from backend.app.services.pdf_service import generate_po_pdf

router = APIRouter(prefix="/purchases", tags=["Purchase Management"])

@router.get("", response_model=List[POOut])
def list_pos(
    supplier_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("purchase_orders"))
):
    return get_purchase_orders(
        db,
        supplier_id=supplier_id,
        status_filter=status,
        start_date=start_date,
        end_date=end_date
    )

@router.post("", response_model=POOut)
def create_po_endpoint(
    data: POCreate,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("purchase_orders", require_write=True))
):
    po = create_purchase_order(db, data, user_id=pharmacist.user_id, initial_status="Pending")
    all_pos = get_purchase_orders(db)
    for p in all_pos:
        if p["po_id"] == po.po_id:
            return p
    return all_pos[0]

@router.post("/{po_id}/receive", response_model=POOut)
def receive_goods(
    po_id: int,
    data: POReceipt,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("purchase_orders", require_write=True))
):
    po = receive_purchase_order(db, po_id, data, user_id=pharmacist.user_id)
    all_pos = get_purchase_orders(db)
    for p in all_pos:
        if p["po_id"] == po.po_id:
            return p
    return all_pos[0]

@router.post("/{po_id}/cancel", response_model=POOut)
def cancel_po_endpoint(
    po_id: int,
    data: POCancel,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("purchase_orders", require_write=True))
):
    po = cancel_purchase_order(db, po_id, data, user_id=pharmacist.user_id)
    all_pos = get_purchase_orders(db)
    for p in all_pos:
        if p["po_id"] == po.po_id:
            return p
    return all_pos[0]

@router.get("/{po_id}/pdf")
def download_po_pdf(
    po_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("purchase_orders"))
):
    orders = get_purchase_orders(db)
    target = next((p for p in orders if p["po_id"] == po_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    
    pdf_buffer = generate_po_pdf(target)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=purchase_order_{po_id}.pdf"}
    )
