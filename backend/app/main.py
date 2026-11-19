from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from backend.app.core.config import settings
from backend.app.db.session import init_db, SessionLocal
from backend.app.services.settings_service import init_system_settings
from backend.app.services.medicine_service import update_batch_statuses
from backend.app.services.recommendation_service import run_all_recommendations

from backend.app.api import (
    auth, users, medicines, suppliers, purchases, sales, customers, stock, recommendations, reports, settings as settings_api
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PharmaTrack-X")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Initializing PharmaTrack-X database and settings...")
    init_db()
    with SessionLocal() as db:
        init_system_settings(db)
        update_batch_statuses(db)
    logger.info("PharmaTrack-X backend initialized successfully.")
    yield
    # Shutdown tasks
    logger.info("PharmaTrack-X backend shutting down.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="An Expiry-Risk and Demand-Uncertainty-Aware Pharmacy Inventory Decision Support System",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for React web client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_and_cache_control_headers(request: Request, call_next):
    """Enforces no-store cache control on all protected APIs and sensitive endpoints."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Vary"] = "Cookie, Authorization"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

# Include Routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(medicines.router, prefix="/api")
app.include_router(suppliers.router, prefix="/api")
app.include_router(purchases.router, prefix="/api")
app.include_router(sales.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(stock.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0", "system": "PharmaTrack-X"}
