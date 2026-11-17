from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Tuple
from fastapi import HTTPException, status

from backend.app.models.entities import Sale, SaleItem, Medicine, Batch, Customer
from backend.app.schemas.schemas import SaleCreate, SaleItemInput, SaleVoid
from backend.app.services.audit_service import log_audit
from backend.app.services.settings_service import get_setting_float
from backend.app.services.medicine_service import update_batch_statuses

def allocate_fefo_batches(db: Session, medicine_id: int, requested_qty: int) -> List[Tuple[Batch, int]]:
    """
    FR-22 & FR-23 & AC-2 & AC-3:
    Allocate requested quantity from non-expired batches using FEFO (earliest expiry first),
    prioritizing sell_first batches if any, then earliest expiry_date.
    Reject completely if requested_qty exceeds available non-expired stock or if batch is expired.
    """
    today = date.today()
    medicine = db.query(Medicine).filter(Medicine.medicine_id == medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found.")

    if not medicine.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Medicine '{medicine.name}' is inactive.")

    # Get non-expired batches with positive remaining quantity
    # Order: batches marked sell_first=True first, then earliest expiry_date ascending (FEFO)
    candidate_batches = db.query(Batch).filter(
        Batch.medicine_id == medicine_id,
        Batch.expiry_date >= today,
        Batch.qty_remaining > 0,
        Batch.status.in_(["Active", "Near-Expiry"])
    ).order_by(
        Batch.sell_first.desc(),
        Batch.expiry_date.asc(),
        Batch.batch_id.asc()
    ).all()

    total_available = sum(b.qty_remaining for b in candidate_batches)
    if requested_qty > total_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient non-expired stock for '{medicine.name}'. Available: {total_available}, Requested: {requested_qty}."
        )

    allocations: List[Tuple[Batch, int]] = []
    qty_needed = requested_qty

    for batch in candidate_batches:
        # Strict server-side safety check (NFR-S1): Never allocate an expired batch
        if batch.expiry_date < today or batch.status == "Expired":
            continue

        take = min(qty_needed, batch.qty_remaining)
        allocations.append((batch, take))
        qty_needed -= take
        if qty_needed <= 0:
            break

    if qty_needed > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not allocate full quantity for '{medicine.name}' from valid non-expired batches."
        )

    return allocations

def generate_invoice_number(db: Session) -> str:
    today_str = datetime.utcnow().strftime("%Y%m%d")
    count_today = db.query(Sale).filter(Sale.invoice_no.like(f"INV-{today_str}-%")).count()
    return f"INV-{today_str}-{(count_today + 1):04d}"

def create_sale(db: Session, data: SaleCreate, user_id: int) -> Sale:
    """
    FR-21 to FR-25: Process sale, apply FEFO allocation, check max discount,
    record transaction atomically, deduct stock.
    """
    if not data.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sale must contain at least one item.")

    max_discount = Decimal(str(get_setting_float(db, "max_discount_percent", 10.0)))
    if data.discount_percent > max_discount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Discount of {data.discount_percent}% exceeds the allowed maximum of {max_discount}%."
        )

    customer_id = data.customer_id
    if customer_id:
        cust = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if not cust:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    invoice_no = generate_invoice_number(db)
    subtotal = Decimal("0.0")
    sale_items = []
    today = date.today()

    try:
        for item_in in data.items:
            med = db.query(Medicine).filter(Medicine.medicine_id == item_in.medicine_id).first()
            if not med:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Medicine ID {item_in.medicine_id} not found.")

            allocations = allocate_fefo_batches(db, med.medicine_id, item_in.quantity)
            for batch, qty in allocations:
                # Deduct stock
                batch.qty_remaining -= qty
                if batch.qty_remaining == 0:
                    batch.status = "Depleted"

                line_tot = Decimal(str(med.unit_price)) * qty
                subtotal += line_tot

                sale_items.append(
                    SaleItem(
                        batch_id=batch.batch_id,
                        quantity=qty,
                        unit_price=med.unit_price,
                        line_total=line_tot,
                    )
                )

        discount_amount = (subtotal * data.discount_percent) / Decimal("100.0")
        total_amount = subtotal - discount_amount

        sale = Sale(
            invoice_no=invoice_no,
            customer_id=customer_id,
            user_id=user_id,
            sale_datetime=datetime.utcnow(),
            subtotal=subtotal,
            discount_percent=data.discount_percent,
            total_amount=total_amount,
            status="Completed",
            items=sale_items,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        log_audit(db, action="SALE_COMPLETED", user_id=user_id, entity="sales", entity_id=str(sale.sale_id), result="Success")
        return sale
    except Exception as e:
        db.rollback()
        raise e

def void_sale(db: Session, sale_id: int, data: SaleVoid, pharmacist_user_id: int) -> Sale:
    """
    FR-27: Pharmacist can void a completed bill by entering a reason;
    stock shall be restored to the same batches and the bill marked Voided.
    """
    sale = db.query(Sale).filter(Sale.sale_id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found.")

    if sale.status == "Voided":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sale is already voided.")

    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required to void a bill.")

    try:
        # Restore stock to exact batches
        for item in sale.items:
            batch = db.query(Batch).filter(Batch.batch_id == item.batch_id).first()
            if batch:
                batch.qty_remaining += item.quantity
                # Update status
                today = date.today()
                near_expiry_days = int(get_setting_float(db, "near_expiry_days", 90))
                if batch.expiry_date < today:
                    batch.status = "Expired"
                elif (batch.expiry_date - today).days <= near_expiry_days:
                    batch.status = "Near-Expiry"
                else:
                    batch.status = "Active"

        sale.status = "Voided"
        sale.void_reason = data.reason.strip()
        sale.voided_by = pharmacist_user_id
        sale.voided_at = datetime.utcnow()

        db.commit()
        db.refresh(sale)
        log_audit(db, action="VOID_BILL", user_id=pharmacist_user_id, entity="sales", entity_id=str(sale.sale_id), result="Success")
        return sale
    except Exception as e:
        db.rollback()
        raise e

def get_sale_details(db: Session, sale_id: int) -> dict:
    sale = db.query(Sale).filter(Sale.sale_id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found.")

    items_out = []
    for it in sale.items:
        items_out.append({
            "sale_item_id": it.sale_item_id,
            "batch_id": it.batch_id,
            "batch_number": it.batch.batch_number if it.batch else None,
            "medicine_name": it.batch.medicine.name if it.batch and it.batch.medicine else None,
            "expiry_date": it.batch.expiry_date if it.batch else None,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "line_total": it.line_total,
        })

    return {
        "sale_id": sale.sale_id,
        "invoice_no": sale.invoice_no,
        "customer_id": sale.customer_id,
        "customer_name": sale.customer.name if sale.customer else None,
        "user_id": sale.user_id,
        "cashier_name": sale.user.full_name if sale.user else None,
        "sale_datetime": sale.sale_datetime,
        "subtotal": sale.subtotal,
        "discount_percent": sale.discount_percent,
        "total_amount": sale.total_amount,
        "status": sale.status,
        "void_reason": sale.void_reason,
        "items": items_out,
    }
