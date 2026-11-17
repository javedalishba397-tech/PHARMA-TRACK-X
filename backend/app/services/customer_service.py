from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import or_

from backend.app.models.entities import Customer, Sale
from backend.app.schemas.schemas import CustomerCreate, CustomerUpdate
from backend.app.services.audit_service import log_audit

def create_customer(db: Session, data: CustomerCreate, user_id: int) -> Customer:
    existing = db.query(Customer).filter(Customer.phone == data.phone.strip()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Customer with phone '{data.phone}' already exists.")

    customer = Customer(
        name=data.name.strip(),
        phone=data.phone.strip(),
        email=data.email.strip() if data.email else None,
        address=data.address.strip() if data.address else None,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    log_audit(db, action="CREATE_CUSTOMER", user_id=user_id, entity="customers", entity_id=str(customer.customer_id), result="Success")
    return customer

def update_customer(db: Session, customer_id: int, data: CustomerUpdate, user_id: int) -> Customer:
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    update_dict = data.dict(exclude_unset=True)
    for k, v in update_dict.items():
        if k == "phone" and v:
            existing = db.query(Customer).filter(Customer.phone == v.strip(), Customer.customer_id != customer_id).first()
            if existing:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number already registered to another customer.")
        setattr(customer, k, v)

    db.commit()
    db.refresh(customer)
    log_audit(db, action="UPDATE_CUSTOMER", user_id=user_id, entity="customers", entity_id=str(customer.customer_id), result="Success")
    return customer

def search_customers(db: Session, query: Optional[str] = None) -> List[Customer]:
    q = db.query(Customer)
    if query:
        pattern = f"%{query.strip()}%"
        q = q.filter(or_(Customer.name.ilike(pattern), Customer.phone.ilike(pattern), Customer.email.ilike(pattern)))
    return q.order_by(Customer.name).all()

def get_customer_purchase_history(db: Session, customer_id: int) -> List[dict]:
    """FR-30: Display customer's purchase history with date, invoice number and items."""
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    sales = db.query(Sale).filter(Sale.customer_id == customer_id).order_by(Sale.sale_datetime.desc()).all()
    history = []
    for s in sales:
        items_summary = []
        for it in s.items:
            med_name = it.batch.medicine.name if it.batch and it.batch.medicine else "Medicine"
            items_summary.append({
                "medicine_name": med_name,
                "batch_number": it.batch.batch_number if it.batch else "",
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "line_total": it.line_total,
            })
        history.append({
            "sale_id": s.sale_id,
            "invoice_no": s.invoice_no,
            "sale_datetime": s.sale_datetime,
            "total_amount": s.total_amount,
            "status": s.status,
            "items": items_summary,
        })
    return history
