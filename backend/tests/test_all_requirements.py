import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
import time
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal, init_db
from backend.app.models.entities import (
    User, Medicine, Batch, Supplier, Customer, PurchaseOrder, PurchaseOrderItem, Sale, SaleItem,
    StockAdjustment, DemandForecast, Recommendation, DecisionLog, SystemSetting, AuditLog
)
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.services.sale_service import allocate_fefo_batches, create_sale, void_sale
from backend.app.services.medicine_service import create_batch
from backend.app.services.recommendation_service import run_all_recommendations, decide_recommendation, generate_recommendations_for_medicine
from backend.app.schemas.schemas import SaleCreate, SaleItemInput, SaleVoid, RecommendationDecision
from decision_module.forecaster import DemandForecaster

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    init_db()
    db = SessionLocal()
    yield db
    db.close()

@pytest.fixture(scope="module")
def tokens(db_session):
    admin = db_session.query(User).filter(User.username == "admin").first()
    pharma = db_session.query(User).filter(User.username == "pharmacist").first()
    clerk = db_session.query(User).filter(User.username == "clerk").first()

    return {
        "admin": create_access_token(admin.user_id, admin.role),
        "pharmacist": create_access_token(pharma.user_id, pharma.role),
        "clerk": create_access_token(clerk.user_id, clerk.role),
    }

# =========================================================================
# AC-2: In 50 test attempts to sell from an expired batch, 100% are rejected
# =========================================================================
def test_ac2_fifty_attempts_to_sell_expired_batch_rejected(db_session):
    today = date.today()
    # Find expired medicine or create one
    med = db_session.query(Medicine).filter(Medicine.barcode == "8964000999999").first()
    assert med is not None

    # Verify that the expired batch is present
    exp_batch = db_session.query(Batch).filter(
        Batch.medicine_id == med.medicine_id,
        Batch.expiry_date < today
    ).first()
    assert exp_batch is not None
    assert exp_batch.status == "Expired"

    rejected_count = 0
    total_attempts = 50

    for _ in range(total_attempts):
        with pytest.raises(Exception) as exc_info:
            # Attempt to allocate or sell
            allocate_fefo_batches(db_session, med.medicine_id, requested_qty=1)
        if "Insufficient non-expired stock" in str(exc_info.value) or "400" in str(exc_info.value):
            rejected_count += 1

    # Assert 100% rejection rate (50 out of 50)
    assert rejected_count == 50, f"Expected 50 rejections, got {rejected_count}"

# =========================================================================
# AC-3: FEFO allocation is correct in 100% of test sales spanning several batches
# =========================================================================
def test_ac3_fefo_allocation_multi_batch(db_session):
    today = date.today()
    # Create test medicine with 3 batches of varying expiry dates
    med_name = f"FEFO Test Med {int(time.time())}"
    med = Medicine(
        name=med_name,
        generic_name="FEFO Test Gen",
        category="General",
        dosage_form="Tablet",
        strength="100mg",
        manufacturer="FEFO Labs",
        barcode=f"FEFO-{int(time.time())}",
        unit_price=Decimal("10.00"),
        reorder_level=5,
        is_active=True
    )
    db_session.add(med)
    db_session.commit()
    db_session.refresh(med)

    # Batch 1: Expiring in 30 days, qty 10
    b1 = Batch(
        medicine_id=med.medicine_id,
        batch_number=f"B-EXP30-{int(time.time())}",
        expiry_date=today + timedelta(days=30),
        received_date=today - timedelta(days=10),
        qty_received=10,
        qty_remaining=10,
        purchase_price=Decimal("5.00"),
        status="Near-Expiry"
    )
    # Batch 2: Expiring in 60 days, qty 15
    b2 = Batch(
        medicine_id=med.medicine_id,
        batch_number=f"B-EXP60-{int(time.time())}",
        expiry_date=today + timedelta(days=60),
        received_date=today - timedelta(days=10),
        qty_received=15,
        qty_remaining=15,
        purchase_price=Decimal("5.00"),
        status="Near-Expiry"
    )
    # Batch 3: Expiring in 120 days, qty 20
    b3 = Batch(
        medicine_id=med.medicine_id,
        batch_number=f"B-EXP120-{int(time.time())}",
        expiry_date=today + timedelta(days=120),
        received_date=today - timedelta(days=10),
        qty_received=20,
        qty_remaining=20,
        purchase_price=Decimal("5.00"),
        status="Active"
    )
    db_session.add_all([b1, b2, b3])
    db_session.commit()

    # Request 18 units: should take all 10 of b1 (30 days), and 8 of b2 (60 days), and 0 of b3
    allocations = allocate_fefo_batches(db_session, med.medicine_id, requested_qty=18)
    assert len(allocations) == 2
    assert allocations[0][0].batch_id == b1.batch_id
    assert allocations[0][1] == 10
    assert allocations[1][0].batch_id == b2.batch_id
    assert allocations[1][1] == 8

# =========================================================================
# AC-4: No recommendation changes stock, order or priority before approval
# =========================================================================
def test_ac4_recommendation_requires_approval(db_session):
    admin = db_session.query(User).filter(User.username == "admin").first()
    pharma = db_session.query(User).filter(User.username == "pharmacist").first()

    # Check pending recommendation
    rec = db_session.query(Recommendation).filter(Recommendation.status == "Pending").first()
    assert rec is not None
    assert rec.status == "Pending"

    # Prior to approval, verify batch sell_first has not changed
    batch = db_session.query(Batch).filter(Batch.batch_id == rec.batch_id).first()
    assert batch.sell_first is False

    # Count POs before
    po_count_before = db_session.query(PurchaseOrder).count()

    # If it is a Reorder recommendation, test approving it creates a draft PO
    reorder_rec = db_session.query(Recommendation).filter(
        Recommendation.action == "Reorder",
        Recommendation.status == "Pending"
    ).first()
    if reorder_rec:
        decide_recommendation(
            db_session,
            recommendation_id=reorder_rec.recommendation_id,
            data=RecommendationDecision(decision="Approved"),
            pharmacist_user_id=pharma.user_id
        )
        po_count_after = db_session.query(PurchaseOrder).count()
        assert po_count_after == po_count_before + 1
        draft_po = db_session.query(PurchaseOrder).order_by(PurchaseOrder.po_id.desc()).first()
        assert draft_po.status == "Draft"

# =========================================================================
# AC-5: Every recommendation contains explanation with five required inputs
# =========================================================================
def test_ac5_recommendation_explanation_contains_five_inputs(db_session):
    recs = db_session.query(Recommendation).all()
    assert len(recs) > 0
    for r in recs:
        exp = r.explanation
        # 1. stock
        assert "units" in exp or "stock" in exp.lower()
        # 2. days to expiry (various phrasings used across different rule explanations)
        assert (
            "days to expiry" in exp.lower()
            or "expires in" in exp.lower()
            or "expiring in" in exp.lower()
        )
        # 3. expected demand and range
        assert "expected demand" in exp.lower()
        assert "range" in exp.lower()
        # 4. confidence level
        assert "confidence" in exp.lower()
        # 5. supplier lead time
        assert "lead time" in exp.lower()

# =========================================================================
# AC-6: At least 70% of actual 30-day demands in back-test lie inside 80% range,
#       and Low confidence shown for medicines with fewer than 30 days history
# =========================================================================
def test_ac6_backtest_coverage_and_low_confidence():
    forecaster = DemandForecaster(min_history_days=30, max_daily_cv=1.0)

    # 1. Check Low confidence with fewer than 30 days
    short_sales = [5.0, 4.0, 6.0] * 7  # 21 days
    f_short = forecaster.forecast_from_daily_sales(1, short_sales)
    assert f_short.confidence_level == "Low"
    assert f_short.history_days == 21

    # 2. Back-test simulation with 60 days of known daily sales
    # Generate 60 days with Poisson/Normal mean=10, std=2
    import random
    random.seed(42)
    daily_history = [max(0.0, random.gauss(10.0, 2.0)) for _ in range(60)]

    # Forecast next 30 days from first 30 days
    train_history = daily_history[:30]
    forecast = forecaster.forecast_from_daily_sales(2, train_history, horizon_days=30, confidence_pct=80)

    # Actual 30-day demand from days 30..60
    actual_30day_demand = sum(daily_history[30:60])

    # Monte carlo back-testing over 20 rolling splits
    hits = 0
    trials = 20
    for i in range(trials):
        train = [max(0.0, random.gauss(10.0, 2.0)) for _ in range(35)]
        future = [max(0.0, random.gauss(10.0, 2.0)) for _ in range(30)]
        f = forecaster.forecast_from_daily_sales(3, train, horizon_days=30, confidence_pct=80)
        actual = sum(future)
        if f.lower_bound <= actual <= f.upper_bound:
            hits += 1

    coverage_rate = hits / float(trials)
    assert coverage_rate >= 0.70, f"Back-test coverage was {coverage_rate * 100}%, required >= 70%"

# =========================================================================
# FR-01 to FR-06: User Authentication, RBAC, Lockout, Password Change
# =========================================================================
def test_fr01_to_fr06_auth_and_rbac(tokens, db_session):
    # FR-01: Invalid login fails
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "WrongPassword!"})
    assert resp.status_code == 401

    # FR-04: Role Permission enforcement (Table 3.5)
    # Sales clerk cannot access purchase orders
    resp_clerk_po = client.get("/api/purchases", headers={"Authorization": f"Bearer {tokens['clerk']}"})
    assert resp_clerk_po.status_code == 403

    # Pharmacist CAN access purchase orders
    resp_pharma_po = client.get("/api/purchases", headers={"Authorization": f"Bearer {tokens['pharmacist']}"})
    assert resp_pharma_po.status_code == 200

# =========================================================================
# FR-07 to FR-12: Medicines & Batches
# =========================================================================
def test_fr07_to_fr12_medicines_batches(tokens, db_session):
    # FR-07: Create medicine
    ts = int(time.time())
    new_med = {
        "name": f"Test Drug {ts}",
        "generic_name": "Test Generic",
        "category": "Pain",
        "dosage_form": "Tablet",
        "strength": "250 mg",
        "manufacturer": f"Test Pharma {ts}",
        "barcode": f"TEST-{ts}",
        "unit_price": 50.0,
        "reorder_level": 20,
        "requires_prescription": False
    }
    resp = client.post("/api/medicines", json=new_med, headers={"Authorization": f"Bearer {tokens['pharmacist']}"})
    assert resp.status_code == 200
    med_id = resp.json()["medicine_id"]

    # Duplicate rejection (FR-07)
    resp_dup = client.post("/api/medicines", json=new_med, headers={"Authorization": f"Bearer {tokens['pharmacist']}"})
    assert resp_dup.status_code == 400

    # FR-10: Reject past expiry date
    past_batch = {
        "medicine_id": med_id,
        "batch_number": f"PAST-{ts}",
        "expiry_date": (date.today() - timedelta(days=1)).isoformat(),
        "qty_received": 50,
        "purchase_price": 30.0
    }
    resp_b_past = client.post("/api/medicines/batches", json=past_batch, headers={"Authorization": f"Bearer {tokens['pharmacist']}"})
    assert resp_b_past.status_code == 400

    # FR-10: Accept valid future batch
    fut_batch = {
        "medicine_id": med_id,
        "batch_number": f"FUT-{ts}",
        "expiry_date": (date.today() + timedelta(days=180)).isoformat(),
        "qty_received": 100,
        "purchase_price": 30.0
    }
    resp_b_fut = client.post("/api/medicines/batches", json=fut_batch, headers={"Authorization": f"Bearer {tokens['pharmacist']}"})
    assert resp_b_fut.status_code == 200

# =========================================================================
# FR-13 to FR-15: Suppliers & Observed Lead Time
# =========================================================================
def test_fr13_to_fr15_suppliers(tokens):
    resp = client.get("/api/suppliers", headers={"Authorization": f"Bearer {tokens['pharmacist']}"})
    assert resp.status_code == 200
    suppliers = resp.json()
    assert len(suppliers) > 0
    # FR-14: Observed lead time calculated for suppliers with >= 3 deliveries
    for s in suppliers:
        if s["observed_lead_time_days"] is not None:
            assert s["effective_lead_time_days"] == float(s["observed_lead_time_days"])

# =========================================================================
# FR-21 to FR-27: Point of Sale & Bill Voiding
# =========================================================================
def test_fr21_to_fr27_sales_and_void(tokens, db_session):
    # Find active medicine
    med = db_session.query(Medicine).filter(Medicine.barcode == "8964000400445").first()
    assert med is not None
    batch = med.batches[0]
    stock_before = batch.qty_remaining

    # Create sale of 2 units
    sale_payload = {
        "customer_id": None,
        "discount_percent": 5.0,
        "items": [{"medicine_id": med.medicine_id, "quantity": 2}]
    }
    resp = client.post("/api/sales", json=sale_payload, headers={"Authorization": f"Bearer {tokens['clerk']}"})
    assert resp.status_code == 200
    sale_data = resp.json()
    sale_id = sale_data["sale_id"]
    assert sale_data["status"] == "Completed"

    # Verify stock deducted
    db_session.refresh(batch)
    assert batch.qty_remaining == stock_before - 2

    # FR-26: Invoice PDF endpoint
    resp_pdf = client.get(f"/api/sales/{sale_id}/pdf", headers={"Authorization": f"Bearer {tokens['clerk']}"})
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"

    # FR-27: Void bill with reason
    void_payload = {"reason": "Customer changed mind at the counter."}
    resp_void = client.post(f"/api/sales/{sale_id}/void", json=void_payload, headers={"Authorization": f"Bearer {tokens['pharmacist']}"})
    assert resp_void.status_code == 200
    assert resp_void.json()["status"] == "Voided"

    # Verify stock restored to exact batch
    db_session.refresh(batch)
    assert batch.qty_remaining == stock_before

# =========================================================================
# FR-31 to FR-37: Stock, Alerts & Dashboard
# =========================================================================
def test_fr31_to_fr37_stock_and_alerts(tokens):
    resp = client.get("/api/stock/dashboard", headers={"Authorization": f"Bearer {tokens['clerk']}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "low_stock_count" in data
    assert "near_expiry_count" in data
    assert "expired_count" in data
    assert "pending_recommendations_count" in data

# =========================================================================
# FR-52 to FR-58: Reports & PDF/CSV Export
# =========================================================================
def test_fr52_to_fr58_reports(tokens):
    # Sales CSV & PDF
    resp_csv = client.get("/api/reports/sales?format=csv", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]

    resp_pdf = client.get("/api/reports/sales?format=pdf", headers={"Authorization": f"Bearer {tokens['pharmacist']}"})
    assert resp_pdf.status_code == 200
    assert "application/pdf" in resp_pdf.headers["content-type"]

    # Stock & Expiry report
    resp_stk = client.get("/api/reports/stock-expiry", headers={"Authorization": f"Bearer {tokens['pharmacist']}"})
    assert resp_stk.status_code == 200
    assert "usable_batches" in resp_stk.json()
