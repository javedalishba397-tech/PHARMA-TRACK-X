import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "PharmaTrack-X"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "pharmatrack-x-super-secret-key-ned-cis-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # FR-06, SEC-6: 15 minutes of inactivity
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./pharmatrack.db")

    # System Defaults (Appendix A.4)
    DEFAULT_FORECAST_HORIZON_DAYS: int = 30
    DEFAULT_FORECAST_CONFIDENCE_PCT: int = 80
    DEFAULT_NEAR_EXPIRY_DAYS: int = 90
    DEFAULT_MIN_HISTORY_DAYS: int = 30
    DEFAULT_MAX_DAILY_CV: float = 1.0
    DEFAULT_W_EXPIRY_RISK: float = 0.5
    DEFAULT_W_STOCKOUT_RISK: float = 0.3
    DEFAULT_W_UNCERTAINTY: float = 0.2
    DEFAULT_RISK_LOW_MAX: int = 33
    DEFAULT_RISK_MEDIUM_MAX: int = 66
    DEFAULT_MIN_LEAD_TIME_DELIVERIES: int = 3
    DEFAULT_MAX_DISCOUNT_PERCENT: float = 10.0
    DEFAULT_SESSION_TIMEOUT_MIN: int = 15
    DEFAULT_LOGIN_MAX_ATTEMPTS: int = 5
    DEFAULT_LOCKOUT_MINUTES: int = 15
    DEFAULT_RECOMMENDATION_RUN_TIME: str = "02:00"

    class Config:
        env_file = ".env"

settings = Settings()
