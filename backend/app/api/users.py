from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.app.db.session import get_db
from backend.app.models.entities import User
from backend.app.schemas.schemas import UserCreate, UserUpdate, UserOut
from backend.app.services.auth_service import require_permission, get_password_hash, validate_password_complexity
from backend.app.services.audit_service import log_audit

router = APIRouter(prefix="/users", tags=["User Management"])

ALLOWED_ROLES = ["Administrator", "Pharmacist", "Sales Clerk"]

@router.get("", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("user_management"))
):
    users = db.query(User).order_by(User.user_id).all()
    return [UserOut.from_orm(u) for u in users]

@router.post("", response_model=UserOut)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("user_management", require_write=True))
):
    if data.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role must be one of: {', '.join(ALLOWED_ROLES)}"
        )

    existing = db.query(User).filter(User.username == data.username.strip()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists.")

    valid, err_msg = validate_password_complexity(data.password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    user = User(
        full_name=data.full_name.strip(),
        username=data.username.strip(),
        password_hash=get_password_hash(data.password),
        role=data.role,
        email=data.email,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(db, action="CREATE_USER", user_id=admin.user_id, entity="users", entity_id=str(user.user_id), result="Success")
    return UserOut.from_orm(user)

@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("user_management", require_write=True))
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if data.role and data.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role specified.")

    update_data = data.dict(exclude_unset=True)
    for k, v in update_data.items():
        setattr(user, k, v)

    db.commit()
    db.refresh(user)
    log_audit(db, action="UPDATE_USER", user_id=admin.user_id, entity="users", entity_id=str(user.user_id), result="Success")
    return UserOut.from_orm(user)

@router.patch("/{user_id}/toggle-status", response_model=UserOut)
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("user_management", require_write=True))
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.user_id == admin.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own administrator account.")

    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    action_name = "REACTIVATE_USER" if user.is_active else "DEACTIVATE_USER"
    log_audit(db, action=action_name, user_id=admin.user_id, entity="users", entity_id=str(user.user_id), result="Success")
    return UserOut.from_orm(user)
