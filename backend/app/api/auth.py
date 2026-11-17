from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from backend.app.db.session import get_db
from backend.app.schemas.schemas import UserLogin, TokenResponse, UserOut, PasswordChange
from backend.app.services.auth_service import authenticate_user, create_access_token, get_current_user, change_password
from backend.app.models.entities import User
from backend.app.services.audit_service import log_audit

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "127.0.0.1"
    user = authenticate_user(db, username=login_data.username, password=login_data.password, ip_address=ip)
    token = create_access_token(subject=user.user_id, role=user.role)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.from_orm(user),
    )

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.from_orm(current_user)

@router.post("/change-password")
def update_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return change_password(db, current_user, data)

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    log_audit(db, action="LOGOUT", user_id=current_user.user_id, entity="users", entity_id=str(current_user.user_id), result="Success")
    return {"message": "Logged out successfully."}
