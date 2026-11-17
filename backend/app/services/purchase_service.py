from sqlalchemy.orm import Session
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from fastapi import HTTPException, status

from backend.app.models.entities import PurchaseOrder, PurchaseOrderItem, Supplier, Medicine, Batch
from backend.app.schemas.schemas import POCreate, POReceipt, POCancel
from backend.app.services.audit_service import log_audit
from backend.app.services.supplier_service import get_effective_lead_time, update_supplier_observed_lead_time
from backend.app.services.medicine_service import update_batch_statuses
from backend.app.services.settings_service import get_setting_int

def create_purchase_order(db: Session, data: POCreate, user_id: int, initial_status: str = "Pending") -> PurchaseOrder:
    supplier = db.query(Supplier).filter(Supplier.supplier_id == data.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")

    if not data.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Purchase order must contain at least one item.")

    today = date.today()
    lead_time = int(get_effective_lead_time(db, supplier.supplier_id))
    expected_delivery = today + timedelta(days=lead_time)

    total_amount = Decimal("0.0")
    po_items = []
    for item_data in data.items:
        med = db.query(Medicine).filter(Medicine.medicine_id == item_data.medicine_id).first()
        if not med:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Medicine ID {item_data.medicine_id} not found.")
        line_cost = Decimal(str(item_data.unit_cost)) * item_data.qty_ordered
        total_amount += line_cost
        po_items.append(
            PurchaseOrderItem(
                medicine_id=item_data.medicine_id,
                qty_ordered=item_data.qty_ordered,
                qty_received=0,
                unit_cost=item_data.unit_cost,
            )
        )

    po = PurchaseOrder(
        supplier_id=supplier.supplier_id,
        created_by=user_id,
        order_date=today,
        expected_delivery_date=expected_delivery,
        status=initial_status,
        total_amount=total_amount,
        notes=data.notes,
        items=po_items,
    )
    db.add(po)
    db.commit()
    db.refresh(po)
    log_audit(db, action="CREATE_PURCHASE_ORDER", user_id=user_id, entity="purchase_orders", entity_id=str(po.po_id), result="Success")
    return po

def receive_purchase_order(db: Session, po_id: int, data: POReceipt, user_id: int) -> PurchaseOrder:
    """
    FR-17: Record full or partial receipt by capturing actual delivery date and,
    for every received line, quantity, batch number, and expiry date.
    Creates batches, updates stock, sets status to Partially Received or Received.
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")

    if po.status in ("Cancelled", "Received"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot receive PO in '{po.status}' status.")

    today = date.today()
    delivery_date = data.actual_delivery_date or today
    po.actual_delivery_date = delivery_date

    near_expiry_days = get_setting_int(db, "near_expiry_days", 90)

    # Process receipt lines
    for line in data.lines:
        item = db.query(PurchaseOrderItem).filter(
            PurchaseOrderItem.po_item_id == line.po_item_id,
            PurchaseOrderItem.po_id == po_id
        ).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"PO line {line.po_item_id} not found in this order.")

        if line.expiry_date <= today:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Expiry date for batch {line.batch_number} must be in the future.")

        # Check duplicate batch number for medicine
        existing_batch = db.query(Batch).filter(
            Batch.medicine_id == item.medicine_id,
            Batch.batch_number == line.batch_number.strip()
        ).first()
        if existing_batch:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch '{line.batch_number}' already exists for this medicine."
            )

        item.qty_received += line.qty_received
        days_to_exp = (line.expiry_date - today).days
        batch_status = "Near-Expiry" if days_to_exp <= near_expiry_days else "Active"

        new_batch = Batch(
            medicine_id=item.medicine_id,
            po_item_id=item.po_item_id,
            batch_number=line.batch_number.strip(),
            expiry_date=line.expiry_date,
            received_date=delivery_date,
            qty_received=line.qty_received,
            qty_remaining=line.qty_received,
            purchase_price=line.purchase_price or item.unit_cost,
            status=batch_status,
            sell_first=False,
        )
        db.add(new_batch)

    # Determine PO status
    all_complete = True
    any_received = False
    for item in po.items:
        if item.qty_received < item.qty_ordered:
            all_complete = False
        if item.qty_received > 0:
            any_received = True

    if all_complete:
        po.status = "Received"
    elif any_received:
        po.status = "Partially Received"

    db.commit()
    db.refresh(po)

    # FR-14: Update observed lead time
    update_supplier_observed_lead_time(db, po.supplier_id)
    # FR-12: Update batch statuses
    update_batch_statuses(db)

    log_audit(db, action="RECEIVE_PURCHASE_ORDER", user_id=user_id, entity="purchase_orders", entity_id=str(po.po_id), result="Success")
    return po

def cancel_purchase_order(db: Session, po_id: int, data: POCancel, user_id: int) -> PurchaseOrder:
    """FR-18: Allow cancellation only while in Draft or Pending status, requires a reason."""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")

    if po.status not in ("Draft", "Pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel purchase order in '{po.status}' status."
        )

    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A cancellation reason is required.")

    po.status = "Cancelled"
    po.cancel_reason = data.reason.strip()
    db.commit()
    db.refresh(po)
    log_audit(db, action="CANCEL_PURCHASE_ORDER", user_id=user_id, entity="purchase_orders", entity_id=str(po.po_id), result="Success")
    return po

def get_purchase_orders(
    db: Session,
    supplier_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[dict]:
    """FR-19 & FR-20: List POs, filtering, flag as Overdue if expected_delivery_date passed and neither Received nor Cancelled."""
    today = date.today()
    q = db.query(PurchaseOrder)

    if supplier_id:
        q = q.filter(PurchaseOrder.supplier_id == supplier_id)
    if status_filter:
        if status_filter == "Overdue":
            q = q.filter(
                PurchaseOrder.expected_delivery_date < today,
                PurchaseOrder.status.notin_(["Received", "Cancelled"])
            )
        else:
            q = q.filter(PurchaseOrder.status == status_filter)
    if start_date:
        q = q.filter(PurchaseOrder.order_date >= start_date)
    if end_date:
        q = q.filter(PurchaseOrder.order_date <= end_date)

    orders = q.order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.po_id.desc()).all()
    results = []
    for po in orders:
        is_overdue = (po.expected_delivery_date < today and po.status not in ("Received", "Cancelled"))
        items_out = []
        for it in po.items:
            items_out.append({
                "po_item_id": it.po_item_id,
                "po_id": it.po_id,
                "medicine_id": it.medicine_id,
                "medicine_name": it.medicine.name if it.medicine else None,
                "qty_ordered": it.qty_ordered,
                "qty_received": it.qty_received,
                "unit_cost": it.unit_cost,
            })
        results.append({
            "po_id": po.po_id,
            "supplier_id": po.supplier_id,
            "supplier_name": po.supplier.name if po.supplier else None,
            "created_by": po.created_by,
            "creator_name": po.creator.full_name if po.creator else None,
            "order_date": po.order_date,
            "expected_delivery_date": po.expected_delivery_date,
            "actual_delivery_date": po.actual_delivery_date,
            "status": "Overdue" if is_overdue and po.status == "Pending" else po.status,
            "raw_status": po.status,
            "total_amount": po.total_amount,
            "cancel_reason": po.cancel_reason,
            "notes": po.notes,
            "is_overdue": is_overdue,
            "items": items_out,
        })
    return results
