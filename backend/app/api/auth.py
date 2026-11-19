from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional
from pydantic import BaseModel

from backend.app.db.session import get_db
from backend.app.schemas.schemas import UserLogin, TokenResponse, UserOut, PasswordChange
from backend.app.services.auth_service import (
    authenticate_user, create_user_session, invalidate_session, get_current_user, change_password
)
from backend.app.models.entities import User
from backend.app.services.audit_service import log_audit
from backend.app.core.config import settings
from backend.app.core.security import decode_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "127.0.0.1"
    user = authenticate_user(db, username=login_data.username, password=login_data.password, ip_address=ip)
    token, session_id = create_user_session(db, user, ip_address=ip, user_agent=request.headers.get("user-agent"))
    
    # Set secure HttpOnly session cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        samesite="lax",
        secure=False
    )
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
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Destroys and invalidates user server-side session and clears authentication cookie."""
    token = request.cookies.get("access_token")
    if not token and "Authorization" in request.headers:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    user_id = None
    if token:
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")
            sid = payload.get("sid")
            if sid:
                invalidate_session(db, sid)

    # Invalidate and expire authentication cookie
    response.delete_cookie(key="access_token", path="/", httponly=True, samesite="lax")
    response.headers["Set-Cookie"] = "access_token=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax"

    if user_id:
        log_audit(db, action="LOGOUT", user_id=int(user_id), entity="users", entity_id=str(user_id), result="Success")

    return {"message": "Logged out successfully."}


class UnauthorizedAttemptReport(BaseModel):
    path: str
    details: Optional[str] = None

@router.post("/report-unauthorized")
def report_unauthorized(
    data: UnauthorizedAttemptReport,
    request: Request,
    db: Session = Depends(get_db)
):
    """Audits direct unauthorized URL access attempts (e.g. entering /settings into the search bar) by guests or non-admin users."""
    ip = request.client.host if request.client else "127.0.0.1"
    token = request.cookies.get("access_token")
    if not token and "Authorization" in request.headers:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    user_id = None
    user_desc = "Unauthenticated Visitor"
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            user_id = int(payload.get("sub"))
            u = db.query(User).filter(User.user_id == user_id).first()
            if u:
                user_desc = f"{u.username} ({u.role})"

    log_audit(
        db,
        action="ADMIN_ACCESS_ATTEMPT_DENIED",
        user_id=user_id,
        entity="admin_site_url",
        entity_id=f"{user_desc} attempted access to {data.path}",
        result="Denied",
        ip_address=ip
    )
    return {"status": "recorded", "message": "Access denial logged in audit."}
