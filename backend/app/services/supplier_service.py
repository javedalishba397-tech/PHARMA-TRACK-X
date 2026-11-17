from sqlalchemy.orm import Session
from decimal import Decimal
from typing import List, Optional
from fastapi import HTTPException, status
from backend.app.models.entities import Supplier, PurchaseOrder
from backend.app.schemas.schemas import SupplierCreate, SupplierUpdate
from backend.app.services.audit_service import log_audit
from backend.app.services.settings_service import get_setting_int

def update_supplier_observed_lead_time(db: Session, supplier_id: int):
    """
    FR-14: Calculate each supplier's observed average lead time
    (actual delivery date minus order date) from received purchase orders.
    """
    received_orders = db.query(PurchaseOrder).filter(
        PurchaseOrder.supplier_id == supplier_id,
        PurchaseOrder.status == "Received",
        PurchaseOrder.actual_delivery_date.isnot(None),
    ).all()

    supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    if not supplier:
        return

    if received_orders:
        diffs = [(po.actual_delivery_date - po.order_date).days for po in received_orders]
        avg_days = sum(diffs) / float(len(diffs))
        supplier.observed_lead_time_days = Decimal(f"{avg_days:.2f}")
    else:
        supplier.observed_lead_time_days = None

    db.commit()

def get_effective_lead_time(db: Session, supplier_id: int) -> float:
    """
    FR-14: The decision module shall use the observed value when the supplier
    has at least three completed deliveries, otherwise the stated value.
    """
    supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    if not supplier:
        return 7.0

    min_deliveries = get_setting_int(db, "min_lead_time_deliveries", 3)
    completed_count = db.query(PurchaseOrder).filter(
        PurchaseOrder.supplier_id == supplier_id,
        PurchaseOrder.status == "Received",
        PurchaseOrder.actual_delivery_date.isnot(None),
    ).count()

    if completed_count >= min_deliveries and supplier.observed_lead_time_days is not None:
        return float(supplier.observed_lead_time_days)
    return float(supplier.stated_lead_time_days)

def create_supplier(db: Session, data: SupplierCreate, user_id: int) -> Supplier:
    supplier = Supplier(
        name=data.name.strip(),
        contact_person=data.contact_person.strip() if data.contact_person else None,
        phone=data.phone.strip() if data.phone else None,
        email=data.email.strip() if data.email else None,
        address=data.address.strip() if data.address else None,
        stated_lead_time_days=data.stated_lead_time_days,
        observed_lead_time_days=None,
        is_active=True,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    log_audit(db, action="CREATE_SUPPLIER", user_id=user_id, entity="suppliers", entity_id=str(supplier.supplier_id), result="Success")
    return supplier

def update_supplier(db: Session, supplier_id: int, data: SupplierUpdate, user_id: int) -> Supplier:
    supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")

    update_dict = data.dict(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(supplier, k, v)

    db.commit()
    db.refresh(supplier)
    log_audit(db, action="UPDATE_SUPPLIER", user_id=user_id, entity="suppliers", entity_id=str(supplier.supplier_id), result="Success")
    return supplier

def get_suppliers(db: Session, active_only: bool = True) -> List[dict]:
    q = db.query(Supplier)
    if active_only:
        q = q.filter(Supplier.is_active == True)
    suppliers = q.order_by(Supplier.name).all()

    results = []
    for s in suppliers:
        eff_lead = get_effective_lead_time(db, s.supplier_id)
        results.append({
            "supplier_id": s.supplier_id,
            "name": s.name,
            "contact_person": s.contact_person,
            "phone": s.phone,
            "email": s.email,
            "address": s.address,
            "stated_lead_time_days": s.stated_lead_time_days,
            "observed_lead_time_days": s.observed_lead_time_days,
            "effective_lead_time_days": eff_lead,
            "is_active": s.is_active,
        })
    return results
