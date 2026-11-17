from sqlalchemy.orm import Session
from datetime import datetime
from backend.app.models.entities import SystemSetting
from backend.app.core.config import settings

DEFAULT_SETTINGS = {
    "forecast_horizon_days": ("30", "Days ahead for which demand is forecast."),
    "forecast_confidence_pct": ("80", "Coverage of the forecast range (%)."),
    "near_expiry_days": ("90", "Days to expiry at or below which a batch is Near-Expiry."),
    "min_history_days": ("30", "Minimum days of sales history for a High/Medium confidence forecast."),
    "max_daily_cv": ("1.0", "Coefficient of variation above which confidence is Low."),
    "w_expiry_risk": ("0.5", "Weight of expiry risk in composite risk score."),
    "w_stockout_risk": ("0.3", "Weight of stock-out risk in composite risk score."),
    "w_uncertainty": ("0.2", "Weight of forecast uncertainty in composite risk score."),
    "risk_low_max": ("33", "Upper limit of Low risk band."),
    "risk_medium_max": ("66", "Upper limit of Medium risk band."),
    "min_lead_time_deliveries": ("3", "Completed deliveries needed before observed lead time is used."),
    "max_discount_percent": ("10.0", "Maximum discount allowed on a bill (%)."),
    "session_timeout_min": ("15", "Inactivity time after which a session ends (minutes)."),
    "login_max_attempts": ("5", "Failed logins before lock."),
    "lockout_minutes": ("15", "Lockout duration after failed attempts (minutes)."),
    "recommendation_run_time": ("02:00", "Time of daily automatic recommendation run."),
}

def init_system_settings(db: Session):
    for key, (val, desc) in DEFAULT_SETTINGS.items():
        existing = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        if not existing:
            setting = SystemSetting(
                setting_key=key,
                setting_value=val,
                description=desc,
                updated_at=datetime.utcnow()
            )
            db.add(setting)
    db.commit()

def get_setting(db: Session, key: str, default: str = "") -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    if setting:
        return setting.setting_value
    return DEFAULT_SETTINGS.get(key, (default, ""))[0]

def get_setting_int(db: Session, key: str, default: int = 0) -> int:
    val = get_setting(db, key, str(default))
    try:
        return int(float(val))
    except ValueError:
        return default

def get_setting_float(db: Session, key: str, default: float = 0.0) -> float:
    val = get_setting(db, key, str(default))
    try:
        return float(val)
    except ValueError:
        return default

def update_setting(db: Session, key: str, value: str, user_id: int):
    setting = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    if setting:
        setting.setting_value = str(value)
        setting.updated_by = user_id
        setting.updated_at = datetime.utcnow()
    else:
        setting = SystemSetting(
            setting_key=key,
            setting_value=str(value),
            description="",
            updated_by=user_id,
            updated_at=datetime.utcnow()
        )
        db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting
