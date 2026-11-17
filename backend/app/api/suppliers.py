from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from backend.app.db.session import get_db
from backend.app.models.entities import User, PurchaseOrder
from backend.app.schemas.schemas import SupplierCreate, SupplierUpdate, SupplierOut, POOut
from backend.app.services.auth_service import require_permission
from backend.app.services.supplier_service import get_suppliers, create_supplier, update_supplier
from backend.app.services.purchase_service import get_purchase_orders

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

@router.get("", response_model=List[SupplierOut])
def list_suppliers(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("suppliers"))
):
    return get_suppliers(db, active_only=False)

@router.post("", response_model=SupplierOut)
def add_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("suppliers", require_write=True))
):
    s = create_supplier(db, data, user_id=pharmacist.user_id)
    all_s = get_suppliers(db, active_only=False)
    for sup in all_s:
        if sup["supplier_id"] == s.supplier_id:
            return sup
    return all_s[0]

@router.put("/{supplier_id}", response_model=SupplierOut)
def edit_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("suppliers", require_write=True))
):
    s = update_supplier(db, supplier_id, data, user_id=pharmacist.user_id)
    all_s = get_suppliers(db, active_only=False)
    for sup in all_s:
        if sup["supplier_id"] == s.supplier_id:
            return sup
    return all_s[0]

@router.get("/{supplier_id}/orders", response_model=List[POOut])
def get_supplier_orders(
    supplier_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("suppliers"))
):
    """FR-15: Display for each supplier the list of purchase orders with date, status and amount."""
    return get_purchase_orders(db, supplier_id=supplier_id)
