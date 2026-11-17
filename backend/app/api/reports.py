from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from backend.app.db.session import get_db
from backend.app.models.entities import User
from backend.app.services.auth_service import require_permission
from backend.app.services.report_service import (
    get_sales_report, get_stock_expiry_report, get_purchase_report,
    get_wastage_report, get_recommendation_report, export_report_csv
)
from backend.app.services.pdf_service import generate_report_pdf

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/sales")
def sales_report_endpoint(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    group_by: str = Query("day"),
    format: str = Query("json"),  # json, csv, pdf
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports"))
):
    data = get_sales_report(db, start_date=start_date, end_date=end_date, group_by=group_by)
    if format == "csv":
        csv_str = export_report_csv(data)
        return Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sales_report.csv"})
    elif format == "pdf":
        pdf_buf = generate_report_pdf(data)
        return Response(content=pdf_buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "inline; filename=sales_report.pdf"})
    return data

@router.get("/stock-expiry")
def stock_expiry_report_endpoint(
    format: str = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports"))
):
    data = get_stock_expiry_report(db)
    if format == "csv":
        csv_str = export_report_csv(data)
        return Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=stock_expiry_report.csv"})
    elif format == "pdf":
        pdf_buf = generate_report_pdf(data)
        return Response(content=pdf_buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "inline; filename=stock_expiry_report.pdf"})
    return data

@router.get("/purchases")
def purchase_report_endpoint(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    supplier_id: Optional[int] = Query(None),
    format: str = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports"))
):
    data = get_purchase_report(db, start_date=start_date, end_date=end_date, supplier_id=supplier_id)
    if format == "csv":
        csv_str = export_report_csv(data)
        return Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=purchase_report.csv"})
    elif format == "pdf":
        pdf_buf = generate_report_pdf(data)
        return Response(content=pdf_buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "inline; filename=purchase_report.pdf"})
    return data

@router.get("/wastage")
def wastage_report_endpoint(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    format: str = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports"))
):
    data = get_wastage_report(db, start_date=start_date, end_date=end_date)
    if format == "csv":
        csv_str = export_report_csv(data)
        return Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=wastage_report.csv"})
    elif format == "pdf":
        pdf_buf = generate_report_pdf(data)
        return Response(content=pdf_buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "inline; filename=wastage_report.pdf"})
    return data

@router.get("/recommendations")
def recommendations_report_endpoint(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    format: str = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports"))
):
    data = get_recommendation_report(db, start_date=start_date, end_date=end_date)
    if format == "csv":
        csv_str = export_report_csv(data)
        return Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=recommendations_report.csv"})
    elif format == "pdf":
        pdf_buf = generate_report_pdf(data)
        return Response(content=pdf_buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "inline; filename=recommendations_report.pdf"})
    return data
