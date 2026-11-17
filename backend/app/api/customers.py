from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.db.session import get_db
from backend.app.models.entities import User, Customer
from backend.app.schemas.schemas import CustomerCreate, CustomerUpdate, CustomerOut
from backend.app.services.auth_service import require_permission
from backend.app.services.customer_service import create_customer, update_customer, search_customers, get_customer_purchase_history

router = APIRouter(prefix="/customers", tags=["Customer Management"])

@router.get("", response_model=List[CustomerOut])
def list_customers(
    query: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers"))
):
    customers = search_customers(db, query=query)
    return [CustomerOut.from_orm(c) for c in customers]

@router.post("", response_model=CustomerOut)
def register_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers", require_write=True))
):
    customer = create_customer(db, data, user_id=user.user_id)
    return CustomerOut.from_orm(customer)

@router.put("/{customer_id}", response_model=CustomerOut)
def edit_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers", require_write=True))
):
    customer = update_customer(db, customer_id, data, user_id=user.user_id)
    return CustomerOut.from_orm(customer)

@router.get("/{customer_id}/history")
def get_customer_history(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers"))
):
    """FR-30: Display customer's purchase history with date, invoice number and items."""
    return get_customer_purchase_history(db, customer_id)
