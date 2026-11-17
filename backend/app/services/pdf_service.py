import io
from typing import Dict, Any
from decimal import Decimal
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_invoice_pdf(sale_data: Dict[str, Any]) -> io.BytesIO:
    """FR-26: Generate invoice PDF showing invoice number, date, items with batch number and expiry date, prices, discount and total."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    # Title & Header
    title_style = ParagraphStyle(name="TitleStyle", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#0f766e"), spaceAfter=6)
    elements.append(Paragraph("PharmaTrack-X Pharmacy", title_style))
    elements.append(Paragraph("Tax Invoice / Cash Receipt", styles["Heading3"]))
    elements.append(Spacer(1, 10))

    # Meta info
    meta_data = [
        [f"Invoice No: {sale_data['invoice_no']}", f"Date: {sale_data['sale_datetime'].strftime('%d/%m/%Y %H:%M')}"],
        [f"Customer: {sale_data.get('customer_name') or 'Walk-in Customer'}", f"Cashier: {sale_data.get('cashier_name') or 'Counter Clerk'}"],
        [f"Status: {sale_data['status']}", f"Currency: PKR"]
    ]
    t_meta = Table(meta_data, colWidths=[260, 260])
    t_meta.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 15))

    # Items Table
    table_data = [["Item / Medicine", "Batch", "Expiry", "Qty", "Price (PKR)", "Total (PKR)"]]
    for item in sale_data["items"]:
        exp_str = item["expiry_date"].strftime("%d/%m/%Y") if item.get("expiry_date") else "-"
        table_data.append([
            item["medicine_name"],
            item["batch_number"],
            exp_str,
            str(item["quantity"]),
            f"{float(item['unit_price']):.2f}",
            f"{float(item['line_total']):.2f}"
        ])

    table_data.append(["", "", "", "", "Subtotal:", f"PKR {float(sale_data['subtotal']):.2f}"])
    table_data.append(["", "", "", "", f"Discount ({float(sale_data['discount_percent'])}%):", f"- PKR {(float(sale_data['subtotal']) * float(sale_data['discount_percent'])/100.0):.2f}"])
    table_data.append(["", "", "", "", "Grand Total:", f"PKR {float(sale_data['total_amount']):.2f}"])

    item_table = Table(table_data, colWidths=[170, 75, 75, 45, 75, 80])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, len(sale_data["items"])), 0.5, colors.HexColor("#cbd5e1")),
        ('LINEABOVE', (3, -3), (-1, -1), 1, colors.HexColor("#0f766e")),
        ('FONTNAME', (3, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Thank you for your visit. Goods once sold cannot be returned without original receipt.", styles["Italic"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_po_pdf(po_data: Dict[str, Any]) -> io.BytesIO:
    """FR-16: Purchase order PDF export."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name="POTitleStyle", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#1e3a8a"), spaceAfter=6)
    elements.append(Paragraph("PharmaTrack-X", title_style))
    elements.append(Paragraph(f"PURCHASE ORDER #{po_data['po_id']}", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    meta_data = [
        [f"Supplier: {po_data.get('supplier_name')}", f"Order Date: {po_data['order_date'].strftime('%d/%m/%Y')}"],
        [f"Created By: {po_data.get('creator_name') or 'Pharmacist'}", f"Expected Delivery: {po_data['expected_delivery_date'].strftime('%d/%m/%Y')}"],
        [f"Status: {po_data['status']}", f"Notes: {po_data.get('notes') or 'N/A'}"]
    ]
    t_meta = Table(meta_data, colWidths=[260, 260])
    t_meta.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 15))

    table_data = [["Medicine", "Qty Ordered", "Unit Cost (PKR)", "Line Cost (PKR)"]]
    for item in po_data["items"]:
        line_total = float(item["qty_ordered"]) * float(item["unit_cost"])
        table_data.append([
            item.get("medicine_name") or f"Medicine #{item['medicine_id']}",
            str(item["qty_ordered"]),
            f"{float(item['unit_cost']):.2f}",
            f"{line_total:.2f}"
        ])
    table_data.append(["", "", "Total PO Amount:", f"PKR {float(po_data['total_amount']):.2f}"])

    item_table = Table(table_data, colWidths=[260, 80, 90, 90])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, len(po_data["items"])), 0.5, colors.HexColor("#cbd5e1")),
        ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(item_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_report_pdf(report_data: Dict[str, Any]) -> io.BytesIO:
    """FR-57: PDF export of reports."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    rep_type = report_data.get("report_type")
    title = f"PharmaTrack-X {rep_type.replace('_', ' ').title()} Report"
    elements.append(Paragraph(title, styles["Heading1"]))
    elements.append(Paragraph(f"Date: {report_data.get('start_date', '')} to {report_data.get('end_date', '')}", styles["Normal"]))
    elements.append(Spacer(1, 15))

    if rep_type == "sales":
        elements.append(Paragraph(f"Total Sales: PKR {report_data['total_amount']:.2f} | Total Invoices: {report_data['total_bills']}", styles["Heading3"]))
        elements.append(Spacer(1, 10))
        table_data = [["Group Key", "Bills / Units", "Total Amount (PKR)"]]
        for r in report_data.get("rows", []):
            table_data.append([str(r.get("group_key")), str(r.get("bills_count", r.get("quantity"))), f"{r.get('total_amount'):.2f}"])
        t = Table(table_data, colWidths=[250, 120, 150])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f766e")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(t)
    elif rep_type == "stock_expiry":
        elements.append(Paragraph(f"Total Stock Valuation: PKR {report_data['total_stock_value']:.2f}", styles["Heading3"]))
        elements.append(Paragraph(f"Usable Batches: {report_data['usable_count']} | Near-Expiry: {report_data['near_expiry_count']} | Expired: {report_data['expired_count']}", styles["Normal"]))
        elements.append(Spacer(1, 10))
        table_data = [["Medicine", "Batch", "Expiry", "Days", "Stock", "Status"]]
        all_b = report_data.get("usable_batches", []) + report_data.get("near_expiry_batches", []) + report_data.get("expired_batches", [])
        for r in all_b[:30]:  # Up to 30 for PDF page fitting
            table_data.append([r["medicine_name"], r["batch_number"], r["expiry_date"], str(r["days_to_expiry"]), str(r["qty_remaining"]), r["status"]])
        t = Table(table_data, colWidths=[160, 70, 70, 50, 60, 110])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f766e")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
    else:
        # Generic summary
        table_data = [["Metric", "Value"]]
        for k, v in report_data.items():
            if not isinstance(v, (list, dict)):
                table_data.append([str(k), str(v)])
        t = Table(table_data, colWidths=[250, 270])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f766e")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        elements.append(t)

    doc.build(elements)
    buffer.seek(0)
    return buffer
