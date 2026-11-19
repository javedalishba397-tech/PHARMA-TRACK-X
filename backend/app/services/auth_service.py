import uuid
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, List, Tuple

from sqlalchemy import func
from backend.app.models.entities import User, ActiveSession
from backend.app.schemas.schemas import UserCreate, UserUpdate, PasswordChange
from backend.app.core.security import verify_password, get_password_hash, validate_password_complexity, decode_access_token, create_access_token
from backend.app.services.audit_service import log_audit
from backend.app.services.settings_service import get_setting_int
from backend.app.db.session import get_db
from backend.app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Table 3.5 Role Permission Matrix
# Roles: Administrator, Pharmacist, Sales Clerk
# Permissions: F = full, V = view only, - = no access
ROLE_PERMISSIONS = {
    "user_management": {"Administrator": "F", "Pharmacist": "-", "Sales Clerk": "-"},
    "system_parameters": {"Administrator": "F", "Pharmacist": "V", "Sales Clerk": "-"},
    "medicines_and_batches": {"Administrator": "V", "Pharmacist": "F", "Sales Clerk": "V"},
    "suppliers": {"Administrator": "V", "Pharmacist": "F", "Sales Clerk": "-"},
    "purchase_orders": {"Administrator": "V", "Pharmacist": "F", "Sales Clerk": "-"},
    "sales_and_billing": {"Administrator": "V", "Pharmacist": "F", "Sales Clerk": "F"},
    "void_bill": {"Administrator": "-", "Pharmacist": "F", "Sales Clerk": "-"},
    "customers": {"Administrator": "V", "Pharmacist": "F", "Sales Clerk": "F"},
    "stock_adjustments": {"Administrator": "-", "Pharmacist": "F", "Sales Clerk": "-"},
    "dashboard_alerts": {"Administrator": "V", "Pharmacist": "F", "Sales Clerk": "V"},
    "forecasts_view": {"Administrator": "V", "Pharmacist": "F", "Sales Clerk": "-"},
    "recommendations_decision": {"Administrator": "-", "Pharmacist": "F", "Sales Clerk": "-"},
    "reports": {"Administrator": "F", "Pharmacist": "F", "Sales Clerk": "-"},
}

def authenticate_user(db: Session, username: str, password: str, ip_address: Optional[str] = None) -> User:
    uname = (username or "").strip()
    user = db.query(User).filter(func.lower(User.username) == uname.lower()).first()
    max_attempts = get_setting_int(db, "login_max_attempts", 5)
    lockout_minutes = get_setting_int(db, "lockout_minutes", 15)

    if not user:
        log_audit(db, action="LOGIN_FAILED", user_id=None, entity="users", entity_id=username, result="Failure", ip_address=ip_address)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    # Check if account is locked (FR-01, SEC-6)
    if user.locked_until and user.locked_until > datetime.utcnow():
        diff = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        log_audit(db, action="LOGIN_LOCKED", user_id=user.user_id, entity="users", entity_id=str(user.user_id), result="Failure", ip_address=ip_address)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is temporarily locked. Try again in {diff} minute(s)."
        )

    # Check if deactivated (FR-03)
    if not user.is_active:
        log_audit(db, action="LOGIN_DEACTIVATED", user_id=user.user_id, entity="users", entity_id=str(user.user_id), result="Failure", ip_address=ip_address)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact Administrator."
        )

    # Standard password verification only - no bypass or demo shortcuts
    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= max_attempts:
            user.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
            user.failed_attempts = 0
            db.commit()
            log_audit(db, action="ACCOUNT_LOCKED", user_id=user.user_id, entity="users", entity_id=str(user.user_id), result="Failure", ip_address=ip_address)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account locked for {lockout_minutes} minutes due to multiple failed login attempts."
            )
        db.commit()
        log_audit(db, action="LOGIN_FAILED", user_id=user.user_id, entity="users", entity_id=str(user.user_id), result="Failure", ip_address=ip_address)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    # Reset failed attempts and locked status on successful login
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
    log_audit(db, action="LOGIN", user_id=user.user_id, entity="users", entity_id=str(user.user_id), result="Success", ip_address=ip_address)
    return user

def create_user_session(db: Session, user: User, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> Tuple[str, str]:
    """Generates a fresh session ID and JWT to prevent session fixation and support revocation."""
    session_id = uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    sess = ActiveSession(
        session_id=session_id,
        user_id=user.user_id,
        created_at=datetime.utcnow(),
        expires_at=expires_at,
        is_active=True,
        ip_address=ip_address,
        user_agent=user_agent[:255] if user_agent else None
    )
    db.add(sess)
    db.commit()
    
    token = create_access_token(subject=user.user_id, role=user.role, session_id=session_id)
    return token, session_id

def invalidate_session(db: Session, session_id: str):
    """Destroys and invalidates user session server-side."""
    sess = db.query(ActiveSession).filter(ActiveSession.session_id == session_id).first()
    if sess:
        sess.is_active = False
        db.commit()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Validates session and token from either Bearer Authorization or HttpOnly cookie."""
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        if any(admin_path in request.url.path for admin_path in ("/settings", "/users")):
            ip = request.client.host if request.client else "127.0.0.1"
            log_audit(
                db,
                action="ADMIN_ACCESS_ATTEMPT_DENIED",
                user_id=None,
                entity="admin_api",
                entity_id=f"Unauthenticated request to {request.url.path}",
                result="Denied",
                ip_address=ip
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    
    sid = payload.get("sid")
    if sid:
        sess = db.query(ActiveSession).filter(ActiveSession.session_id == sid).first()
        if not sess or not sess.is_active or sess.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has expired or was terminated. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    user = db.query(User).filter(User.user_id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated.")
    return user

def require_permission(area: str, require_write: bool = False):
    """Dependency enforcing Table 3.5 RBAC and logging unauthorized attempts to Admin Audit."""
    def permission_checker(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        perms = ROLE_PERMISSIONS.get(area, {})
        user_perm = perms.get(current_user.role, "-")
        ip = request.client.host if request.client else "127.0.0.1"

        if user_perm == "-":
            action_name = "ADMIN_ACCESS_ATTEMPT_DENIED" if area in ("user_management", "system_parameters") else "UNAUTHORIZED_ACCESS_ATTEMPT"
            log_audit(
                db,
                action=action_name,
                user_id=current_user.user_id,
                entity=area,
                entity_id=f"Role '{current_user.role}' attempted access to {request.url.path}",
                result="Denied",
                ip_address=ip
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Role '{current_user.role}' has no access to {area}."
            )
        if require_write and user_perm != "F":
            action_name = "ADMIN_WRITE_ATTEMPT_DENIED" if area in ("user_management", "system_parameters") else "UNAUTHORIZED_WRITE_ATTEMPT"
            log_audit(
                db,
                action=action_name,
                user_id=current_user.user_id,
                entity=area,
                entity_id=f"Role '{current_user.role}' attempted write to {request.url.path}",
                result="Denied",
                ip_address=ip
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Role '{current_user.role}' does not have write permission for {area}."
            )
        return current_user
    return permission_checker

def require_admin(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    """Strictly verifies that user has Administrator role and logs violations in audit log."""
    if current_user.role != "Administrator":
        ip = request.client.host if request.client else "127.0.0.1"
        log_audit(
            db,
            action="ADMIN_ACCESS_ATTEMPT_DENIED",
            user_id=current_user.user_id,
            entity="admin_area",
            entity_id=request.url.path,
            result="Denied",
            ip_address=ip
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Administrator role required."
        )
    return current_user

def change_password(db: Session, user: User, data: PasswordChange):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    
    valid, err_msg = validate_password_complexity(data.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    user.password_hash = get_password_hash(data.new_password)
    db.commit()
    log_audit(db, action="PASSWORD_CHANGE", user_id=user.user_id, entity="users", entity_id=str(user.user_id), result="Success")
    return {"message": "Password changed successfully."}
