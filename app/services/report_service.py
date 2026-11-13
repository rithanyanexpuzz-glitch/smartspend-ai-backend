"""Report generation service - PDF and Excel."""

import io
import csv
from datetime import date
from decimal import Decimal
from sqlalchemy import func, extract

from app.extensions import db
from app.models.expense import Expense
from app.models.income import Income


def generate_csv_report(user_id, month=None, category=None):
    """Generate CSV report for expenses."""
    if month:
        year, mon = map(int, month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month

    query = Expense.query.filter(
        Expense.user_id == user_id,
        extract("year", Expense.expense_date) == year,
        extract("month", Expense.expense_date) == mon,
    )
    if category:
        query = query.filter(Expense.category_name == category)

    expenses = query.order_by(Expense.expense_date).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Description", "Category", "Amount (INR)"])

    total = 0
    for exp in expenses:
        amount = float(exp.amount)
        total += amount
        writer.writerow([
            exp.expense_date.isoformat(),
            exp.description,
            exp.category_name,
            f"{amount:.2f}",
        ])

    writer.writerow([])
    writer.writerow(["", "", "TOTAL", f"{total:.2f}"])

    return output.getvalue(), len(expenses)


def generate_excel_report(user_id, month=None, category=None):
    """Generate Excel report for expenses."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        raise ImportError("openpyxl is required for Excel reports. Install: pip install openpyxl")

    if month:
        year, mon = map(int, month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month

    query = Expense.query.filter(
        Expense.user_id == user_id,
        extract("year", Expense.expense_date) == year,
        extract("month", Expense.expense_date) == mon,
    )
    if category:
        query = query.filter(Expense.category_name == category)

    expenses = query.order_by(Expense.expense_date).all()

    wb = Workbook()
    ws = wb.active
    ws.title = f"Expenses {year}-{mon:02d}"

    # Styles
    header_font = Font(name="Calibri", bold=True, size=12, color="FFFFFF")
    header_fill = PatternFill(start_color="176A57", end_color="176A57", fill_type="solid")
    title_font = Font(name="Calibri", bold=True, size=16, color="1B2C28")
    currency_fmt = '#,##0.00'
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    # Title
    ws.merge_cells("A1:D1")
    ws["A1"] = f"SmartSpend AI - Expense Report ({year}-{mon:02d})"
    ws["A1"].font = title_font
    ws.row_dimensions[1].height = 30

    # Headers
    headers = ["Date", "Description", "Category", "Amount (₹)"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    # Data
    total = 0
    for row_idx, exp in enumerate(expenses, 4):
        amount = float(exp.amount)
        total += amount
        ws.cell(row=row_idx, column=1, value=exp.expense_date.isoformat()).border = thin_border
        ws.cell(row=row_idx, column=2, value=exp.description).border = thin_border
        ws.cell(row=row_idx, column=3, value=exp.category_name).border = thin_border
        cell = ws.cell(row=row_idx, column=4, value=amount)
        cell.number_format = currency_fmt
        cell.border = thin_border

    # Total row
    total_row = len(expenses) + 4
    ws.cell(row=total_row, column=3, value="TOTAL").font = Font(bold=True)
    total_cell = ws.cell(row=total_row, column=4, value=total)
    total_cell.font = Font(bold=True)
    total_cell.number_format = currency_fmt

    # Column widths
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 16

    # Category summary sheet
    ws2 = wb.create_sheet("Category Summary")
    ws2.merge_cells("A1:B1")
    ws2["A1"] = "Category-wise Summary"
    ws2["A1"].font = title_font

    cat_headers = ["Category", "Total (₹)"]
    for col, header in enumerate(cat_headers, 1):
        cell = ws2.cell(row=3, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border

    cat_totals = db.session.query(
        Expense.category_name, func.sum(Expense.amount)
    ).filter(
        Expense.user_id == user_id,
        extract("year", Expense.expense_date) == year,
        extract("month", Expense.expense_date) == mon,
    ).group_by(Expense.category_name).order_by(func.sum(Expense.amount).desc()).all()

    for idx, (cat_name, cat_total) in enumerate(cat_totals, 4):
        ws2.cell(row=idx, column=1, value=cat_name).border = thin_border
        cell = ws2.cell(row=idx, column=2, value=float(cat_total))
        cell.number_format = currency_fmt
        cell.border = thin_border

    ws2.column_dimensions["A"].width = 20
    ws2.column_dimensions["B"].width = 16

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output, len(expenses)


def generate_pdf_report(user_id, month=None, category=None):
    """Generate PDF report for expenses."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise ImportError("reportlab is required for PDF reports. Install: pip install reportlab")

    if month:
        year, mon = map(int, month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month

    query = Expense.query.filter(
        Expense.user_id == user_id,
        extract("year", Expense.expense_date) == year,
        extract("month", Expense.expense_date) == mon,
    )
    if category:
        query = query.filter(Expense.category_name == category)

    expenses = query.order_by(Expense.expense_date).all()

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Heading1"],
        fontSize=18, textColor=colors.HexColor("#1B2C28"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#75817b"),
        spaceAfter=16,
    )

    elements = []
    elements.append(Paragraph("SmartSpend AI - Expense Report", title_style))
    elements.append(Paragraph(f"Period: {year}-{mon:02d}" + (f" | Category: {category}" if category else ""), subtitle_style))
    elements.append(Spacer(1, 10))

    # Table
    data = [["Date", "Description", "Category", "Amount (₹)"]]
    total = 0
    for exp in expenses:
        amount = float(exp.amount)
        total += amount
        data.append([
            exp.expense_date.isoformat(),
            exp.description[:50],
            exp.category_name,
            f"₹{amount:,.2f}",
        ])
    data.append(["", "", "TOTAL", f"₹{total:,.2f}"])

    col_widths = [70, 200, 90, 90]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#176A57")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e7e1")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e9f1ec")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8faf7")]),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)

    doc.build(elements)
    output.seek(0)
    return output, len(expenses)


def generate_income_vs_expense_report(user_id, months=6):
    """Generate income vs expense comparison data."""
    today = date.today()
    data = []
    for i in range(months - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1

        income = db.session.query(
            func.coalesce(func.sum(Income.amount), 0)
        ).filter(
            Income.user_id == user_id,
            extract("year", Income.income_date) == y,
            extract("month", Income.income_date) == m,
        ).scalar()

        expense = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            Expense.user_id == user_id,
            extract("year", Expense.expense_date) == y,
            extract("month", Expense.expense_date) == m,
        ).scalar()

        data.append({
            "month": f"{y}-{m:02d}",
            "income": float(income),
            "expenses": float(expense),
            "savings": float(income) - float(expense),
        })

    return data
