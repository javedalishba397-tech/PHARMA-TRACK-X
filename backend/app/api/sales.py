from fastapi import APIRouter, Depends, Query, Response, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from backend.app.db.session import get_db
from backend.app.models.entities import User, Sale
from backend.app.schemas.schemas import SaleCreate, SaleOut, SaleVoid
from backend.app.services.auth_service import require_permission, get_current_user
from backend.app.services.sale_service import create_sale, void_sale, get_sale_details
from backend.app.services.pdf_service import generate_invoice_pdf

router = APIRouter(prefix="/sales", tags=["Sales & Billing"])

@router.get("", response_model=List[SaleOut])
def list_sales(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sales_and_billing"))
):
    sales = db.query(Sale).order_by(Sale.sale_datetime.desc(), Sale.sale_id.desc()).limit(limit).all()
    return [get_sale_details(db, s.sale_id) for s in sales]

@router.post("", response_model=SaleOut)
def process_new_sale(
    data: SaleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sales_and_billing", require_write=True))
):
    sale = create_sale(db, data, user_id=user.user_id)
    return get_sale_details(db, sale.sale_id)

@router.get("/{sale_id}", response_model=SaleOut)
def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sales_and_billing"))
):
    return get_sale_details(db, sale_id)

@router.get("/{sale_id}/pdf")
def download_invoice_pdf(
    sale_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sales_and_billing"))
):
    sale_details = get_sale_details(db, sale_id)
    pdf_buffer = generate_invoice_pdf(sale_details)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=invoice_{sale_details['invoice_no']}.pdf"}
    )

@router.post("/{sale_id}/void", response_model=SaleOut)
def void_bill_endpoint(
    sale_id: int,
    data: SaleVoid,
    db: Session = Depends(get_db),
    pharmacist: User = Depends(require_permission("void_bill", require_write=True))
):
    """FR-27: Pharmacist can void a completed bill by entering a reason."""
    sale = void_sale(db, sale_id, data, pharmacist_user_id=pharmacist.user_id)
    return get_sale_details(db, sale.sale_id)
