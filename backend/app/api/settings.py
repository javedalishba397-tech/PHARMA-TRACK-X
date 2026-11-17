from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List

from backend.app.db.session import get_db
from backend.app.models.entities import User, SystemSetting, AuditLog
from backend.app.schemas.schemas import SettingOut, SettingUpdate, AuditLogOut
from backend.app.services.auth_service import require_permission
from backend.app.services.settings_service import update_setting, init_system_settings
from backend.app.services.audit_service import log_audit

router = APIRouter(prefix="/settings", tags=["System Parameters & Audit"])

@router.get("", response_model=List[SettingOut])
def list_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("system_parameters"))
):
    init_system_settings(db)
    settings = db.query(SystemSetting).order_by(SystemSetting.setting_key).all()
    return [SettingOut.from_orm(s) for s in settings]

@router.put("/{key}", response_model=SettingOut)
def update_parameter(
    key: str,
    data: SettingUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("system_parameters", require_write=True))
):
    setting = update_setting(db, key, data.setting_value, user_id=admin.user_id)
    log_audit(db, action="UPDATE_SETTING", user_id=admin.user_id, entity="system_settings", entity_id=key, result="Success")
    return SettingOut.from_orm(setting)

@router.get("/audit-logs", response_model=List[AuditLogOut])
def get_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("system_parameters", require_write=True))
):
    """SEC-7: View audit logs. Entries cannot be edited or deleted."""
    logs = db.query(AuditLog).order_by(AuditLog.logged_at.desc()).limit(limit).all()
    results = []
    for l in logs:
        results.append({
            "log_id": l.log_id,
            "user_id": l.user_id,
            "username": l.user.username if l.user else None,
            "action": l.action,
            "entity": l.entity,
            "entity_id": l.entity_id,
            "result": l.result,
            "ip_address": l.ip_address,
            "logged_at": l.logged_at,
        })
    return results
