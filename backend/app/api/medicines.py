from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.db.session import get_db
from backend.app.models.entities import User
from backend.app.schemas.schemas import MedicineCreate, MedicineUpdate, MedicineOut, BatchCreate, BatchOut
from backend.app.services.auth_service import require_permission, get_current_user
from backend.app.services.medicine_service import (
    search_medicines, create_medicine, update_medicine, deactivate_medicine, create_batch, update_batch_statuses
)

router = APIRouter(prefix="/medicines", tags=["Medicines & Batches"])

@router.get("", response_model=List[MedicineOut])
def get_medicines_list(
    query: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("medicines_and_batches"))
):
    update_batch_statuses(db)
    active_only = (user.role == "Sales Clerk")
    return search_medicines(db, query=query, category=category, active_only=active_only)

@router.post("", response_model=MedicineOut)
def add_new_medicine(
    data: MedicineCreate,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("medicines_and_batches", require_write=True))
):
    med = create_medicine(db, data, user_id=pharmacist.user_id)
    # Return formatted single record
    res = search_medicines(db, query=med.name, active_only=False)
    for r in res:
        if r["medicine_id"] == med.medicine_id:
            return r
    return res[0]

@router.put("/{medicine_id}", response_model=MedicineOut)
def edit_medicine(
    medicine_id: int,
    data: MedicineUpdate,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("medicines_and_batches", require_write=True))
):
    med = update_medicine(db, medicine_id, data, user_id=pharmacist.user_id)
    res = search_medicines(db, query=med.name, active_only=False)
    for r in res:
        if r["medicine_id"] == med.medicine_id:
            return r
    return res[0]

@router.delete("/{medicine_id}", response_model=MedicineOut)
def deactivate_medicine_endpoint(
    medicine_id: int,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("medicines_and_batches", require_write=True))
):
    med = deactivate_medicine(db, medicine_id, user_id=pharmacist.user_id)
    res = search_medicines(db, query=med.name, active_only=False)
    for r in res:
        if r["medicine_id"] == med.medicine_id:
            return r
    return res[0]

@router.post("/batches", response_model=BatchOut)
def add_batch(
    data: BatchCreate,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("medicines_and_batches", require_write=True))
):
    batch = create_batch(db, data, user_id=pharmacist.user_id)
    return BatchOut.from_orm(batch)
