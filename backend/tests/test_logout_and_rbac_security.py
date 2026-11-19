import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.session import SessionLocal, init_db
from backend.app.models.entities import User, ActiveSession, AuditLog

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_db():
    init_db()
    db = SessionLocal()
    yield db
    db.close()

def test_cache_control_headers_present():
    """Requirement 4: Verify cache-control headers on protected APIs and auth endpoints."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert "no-store" in resp.headers.get("Cache-Control", "")
    assert "no-cache" in resp.headers.get("Cache-Control", "")
    assert resp.headers.get("Pragma") == "no-cache"
    assert resp.headers.get("Expires") == "0"

def test_secure_login_and_logout_session_invalidation(setup_db):
    """Requirements 2, 3, 6: Server-side session invalidation on logout."""
    db = setup_db
    
    # 1. Login as pharmacist
    login_resp = client.post("/api/auth/login", json={"username": "pharmacist", "password": "Pharma123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert "access_token" in login_resp.cookies or token is not None

    # Verify session exists in DB and is active
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "pharmacist"

    # 2. Perform POST logout
    logout_resp = client.post("/api/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    # Cookie must be cleared/expired
    set_cookie = logout_resp.headers.get("Set-Cookie", "")
    assert "Max-Age=0" in set_cookie or "expires" in set_cookie.lower()

    # 3. Old token/session MUST now be rejected with 401
    post_logout_me = client.get("/api/auth/me", headers=headers)
    assert post_logout_me.status_code == 401
    assert "Session" in post_logout_me.json()["detail"] or "invalid" in post_logout_me.json()["detail"].lower()

    # 4. Protected data endpoint must also reject with 401
    post_logout_po = client.get("/api/purchases", headers=headers)
    assert post_logout_po.status_code == 401

def test_admin_rbac_and_audit_logging(setup_db):
    """Critical Requirement: Admin RBAC & logging unauthorized attempts in audit log."""
    db = setup_db

    # 1. Login as normal user (clerk)
    login_clerk = client.post("/api/auth/login", json={"username": "clerk", "password": "Clerk123!"})
    assert login_clerk.status_code == 200
    clerk_token = login_clerk.json()["access_token"]
    clerk_headers = {"Authorization": f"Bearer {clerk_token}"}

    # 2. Clerk attempts direct access to admin-only API /api/settings/audit-logs
    unauth_resp = client.get("/api/settings/audit-logs", headers=clerk_headers)
    assert unauth_resp.status_code == 403

    # Clerk attempts direct access to admin-only API /api/users
    unauth_users = client.get("/api/users", headers=clerk_headers)
    assert unauth_users.status_code == 403

    # 3. Verify audit log recorded the violation for Admin review
    denied_audit = db.query(AuditLog).filter(
        AuditLog.action.in_(["ADMIN_ACCESS_ATTEMPT_DENIED", "UNAUTHORIZED_ACCESS_ATTEMPT"]),
        AuditLog.result == "Denied"
    ).order_by(AuditLog.logged_at.desc()).first()
    assert denied_audit is not None
    assert denied_audit.result == "Denied"

    # 4. Verify unauthenticated request to admin API returns 401
    client.cookies.clear()
    no_auth_resp = client.get("/api/settings/audit-logs")
    assert no_auth_resp.status_code == 401

    # 5. Verify legitimate admin access succeeds
    login_admin = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert login_admin.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}
    admin_resp = client.get("/api/settings/audit-logs", headers=admin_headers)
    assert admin_resp.status_code == 200

def test_report_unauthorized_url_search_bar_attempt(setup_db):
    """User Request: When anyone enters /settings into the search bar, it must be added to Admin Audit."""
    db = setup_db
    client.cookies.clear()

    # Unauthenticated visitor tries entering /settings in the browser URL bar
    resp = client.post("/api/auth/report-unauthorized", json={
        "path": "/settings",
        "details": "Unauthenticated visitor attempted direct URL search bar navigation to /settings"
    })
    assert resp.status_code == 200

    # Verify that it is immediately present in the Admin Audit logs
    latest_log = db.query(AuditLog).filter(
        AuditLog.action == "ADMIN_ACCESS_ATTEMPT_DENIED",
        AuditLog.entity == "admin_site_url"
    ).order_by(AuditLog.logged_at.desc()).first()

    assert latest_log is not None
    assert latest_log.result == "Denied"
    assert "/settings" in latest_log.entity_id
