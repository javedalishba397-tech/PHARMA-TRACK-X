# PharmaTrack-X v1.0
### Expiry-Risk and Demand-Uncertainty-Aware Pharmacy Inventory Decision Support System

PharmaTrack-X is a full-stack pharmacy inventory and decision support system developed in accordance with the NED CIS 2026 Software Requirements Specification (SRS). It combines strict First-Expired, First-Out (FEFO) dispensing with dynamic demand forecasting, expiry risk scoring, and a human-in-the-loop clinical decision support module.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ (Python 3.13 venv included)
- Node.js 18+ and npm
- Windows PowerShell / Command Prompt

### 1. Start the Backend Server
Run the PowerShell startup script or execute directly:
```powershell
Set-Location "c:\Users\Admin\Desktop\PHARMA TRACK-X"
.\start_backend.ps1
```
*Backend runs on `http://127.0.0.1:8000` with interactive API docs at `http://127.0.0.1:8000/docs`.*

### 2. Start the Frontend Application
In a separate terminal:
```powershell
Set-Location "c:\Users\Admin\Desktop\PHARMA TRACK-X"
.\start_frontend.ps1
```
*Frontend opens at `http://localhost:5173`.*

---

## 👥 Default Demo Credentials

All accounts are pre-seeded in `pharmatrack.db` with roles matching **Table 3.5 (Role Permission Matrix)**:

| Username | Password | Role | System Permissions |
|---|---|---|---|
| `admin` | `Admin123!` | Administrator | User Management, System Parameters, Audit Log, System Reports |
| `pharmacist` | `Pharma123!` | Pharmacist | Decision Support (Approve/Reject/Modify), Purchases, Stock Adjustments, Void Bill, POS |
| `clerk` | `Clerk123!` | Sales Clerk | Point of Sale (POS), Medicine Search, Customer Management |

---

## 🏛️ System Architecture

```
PHARMA TRACK-X/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI REST routers (auth, medicines, purchases, sales, stock, recommendations, reports, settings)
│   │   ├── core/           # Security (bcrypt, JWT), settings configuration
│   │   ├── db/             # SQLAlchemy engine & session factory
│   │   ├── models/         # 15 relational entities matching Appendix A schema
│   │   ├── schemas/        # Pydantic v2 validation and serialization models
│   │   ├── services/       # Business logic (FEFO allocation, audit logging, PDF generation, reports)
│   │   └── scripts/        # Database initialization and demo seed script
│   ├── packages/
│   │   └── decision_module/# Standalone Python package (DemandForecaster + DecisionEngine)
│   └── tests/              # 18 automated unit and acceptance tests (AC-1 to AC-7, FR-01 to FR-58)
├── frontend/
│   ├── src/
│   │   ├── api/            # Axios API client with automatic JWT bearer interceptor
│   │   ├── components/     # Layout, Badge, FormComponents, Modal, ProtectedRoute, Spinner
│   │   ├── context/        # AuthContext with 15-minute inactivity warning & auto-logout
│   │   └── pages/          # Login, Dashboard, Medicines, Sales, Purchases, Stock, Recommendations, Reports, Settings
│   └── vite.config.js      # Vite configuration with Tailwind CSS and /api proxy
├── start_backend.ps1       # One-click backend startup script
├── start_frontend.ps1      # One-click frontend startup script
└── pharmatrack.db          # Pre-seeded SQLite database
```

---

## 🧠 Decision Support Module (`pharmatrack-decision`)

The standalone Python package `backend/packages/decision_module` implements the core algorithms:
- **`DemandForecaster`**: Computes moving average demand, volatility (Coefficient of Variation), and confidence intervals ($[\mu - z\sigma, \mu + z\sigma]$). Low sales history ($<30$ days) or high CV triggers low-confidence classification.
- **`DecisionEngine`**: Evaluates batches across 4 rules (Table 3.20):
  1. **Rule 1 (Review)**: Insufficient history ($<30$ days) or low confidence.
  2. **Rule 2 (Reorder)**: Projected stock at supplier lead time drops below safety stock threshold.
  3. **Rule 3 (Prioritize FEFO)**: Unsold units projected at expiry date ($\le 90$ days threshold); marks batch `Sell First`.
  4. **Rule 4 (Hold)**: Adequate stock cover with zero projected expiry waste.
- **Human-in-the-Loop Safety**: Every recommendation remains `Pending` until explicitly evaluated by a registered Pharmacist.

---

## 🧪 Running Automated Tests

To run the complete acceptance test suite:
```powershell
Set-Location "c:\Users\Admin\Desktop\PHARMA TRACK-X"
$env:PYTHONPATH=".;backend;backend/packages/decision_module"
.\venv\Scripts\pytest backend/tests/test_all_requirements.py backend/packages/decision_module/tests -v
```
All 18 tests verify:
- **AC-2**: 50 attempts to sell an expired batch are 100% rejected.
- **AC-3**: Multi-batch FEFO allocation prioritizing `sell_first` batches.
- **AC-4**: Recommendations remain `Pending` until Pharmacist decision.
- **AC-5**: Recommendation explanation cards contain all 5 required inputs (Stock, Expiry, Demand, Confidence, Lead Time).
- **AC-6**: Backtest coverage and low confidence handling.
- **RBAC**: Strict role enforcement matching Table 3.5.
- **Auditing**: Append-only audit logs for all security and stock operations.
