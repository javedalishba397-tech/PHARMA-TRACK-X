from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, List

from backend.app.models.entities import User
from backend.app.schemas.schemas import UserCreate, UserUpdate, PasswordChange
from backend.app.core.security import verify_password, get_password_hash, validate_password_complexity, decode_access_token, create_access_token
from backend.app.services.audit_service import log_audit
from backend.app.services.settings_service import get_setting_int
from backend.app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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
    user = db.query(User).filter(User.username == username).first()
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

    # Verify password
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

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
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
    
    user = db.query(User).filter(User.user_id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated.")
    return user

def require_permission(area: str, require_write: bool = False):
    """Dependency that enforces Table 3.5 role permission matrix."""
    def permission_checker(current_user: User = Depends(get_current_user)):
        perms = ROLE_PERMISSIONS.get(area, {})
        user_perm = perms.get(current_user.role, "-")
        if user_perm == "-":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Role '{current_user.role}' has no access to {area}."
            )
        if require_write and user_perm != "F":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Role '{current_user.role}' does not have write permission for {area}."
            )
        return current_user
    return permission_checker

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
