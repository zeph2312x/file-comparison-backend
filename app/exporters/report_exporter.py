import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from app.models import ComparisonResult, ChangeType


# Color definitions matching PRD specs
COLOR_UNCHANGED_HEX = "E8F5E9"  # Light Green
COLOR_ADDED_HEX = "FFEBEE"      # Light Red
COLOR_MODIFIED_HEX = "FFF9C4"   # Light Yellow
COLOR_REMOVED_HEX = "EEEEEE"    # Light Gray


def sanitize_excel_cell(val):
    """Mitigate formula injection as required by NFR-004."""
    if isinstance(val, str) and len(val) > 0:
        if val[0] in ("=", "+", "-", "@"):
            return "'" + val
    return val


def export_csv_to_xlsx(result: ComparisonResult) -> io.BytesIO:
    wb = Workbook()

    # 1. Sheet: Summary
    ws_summary = wb.active
    ws_summary.title = "Summary"

    header_font = Font(name="Calibri", size=14, bold=True)
    bold_font = Font(name="Calibri", size=11, bold=True)
    reg_font = Font(name="Calibri", size=11)

    ws_summary["A1"] = "File Comparison Summary Report"
    ws_summary["A1"].font = header_font

    summary_data = [
        ("Baseline File (A)", result.summary.file_a_name),
        ("Comparison File (B)", result.summary.file_b_name),
        ("File Format", result.summary.format),
        ("Status", result.summary.status),
        ("Total Unchanged Items", result.summary.total_unchanged),
        ("Total Added Items", result.summary.total_added),
        ("Total Modified Items", result.summary.total_modified),
        ("Total Removed Items", result.summary.total_removed),
        ("Unit of Measurement", result.summary.unit),
        ("Notice", result.summary.positional_notice or "N/A"),
    ]

    for idx, (label, val) in enumerate(summary_data, start=3):
        ws_summary[f"A{idx}"] = label
        ws_summary[f"A{idx}"].font = bold_font
        ws_summary[f"B{idx}"] = str(val)
        ws_summary[f"B{idx}"].font = reg_font

    ws_summary.column_dimensions["A"].width = 25
    ws_summary.column_dimensions["B"].width = 45

    # Color Fills
    fill_unchanged = PatternFill(start_color=COLOR_UNCHANGED_HEX, end_color=COLOR_UNCHANGED_HEX, fill_type="solid")
    fill_added = PatternFill(start_color=COLOR_ADDED_HEX, end_color=COLOR_ADDED_HEX, fill_type="solid")
    fill_modified = PatternFill(start_color=COLOR_MODIFIED_HEX, end_color=COLOR_MODIFIED_HEX, fill_type="solid")
    fill_removed = PatternFill(start_color=COLOR_REMOVED_HEX, end_color=COLOR_REMOVED_HEX, fill_type="solid")

    def get_fill(ctype: str):
        if ctype == ChangeType.UNCHANGED.value:
            return fill_unchanged
        elif ctype == ChangeType.ADDED.value:
            return fill_added
        elif ctype == ChangeType.MODIFIED.value:
            return fill_modified
        elif ctype == ChangeType.REMOVED.value:
            return fill_removed
        return None

    # 2. Sheet: Baseline Data
    ws_base = wb.create_sheet(title="Baseline")
    headers = result.baseline_view.get("headers", [])
    ws_base.append([sanitize_excel_cell(h) for h in headers])
    for cell in ws_base[1]:
        cell.font = bold_font

    for row_cells in result.baseline_view.get("rows", []):
        row_vals = [sanitize_excel_cell(c.get("value", "")) for c in row_cells]
        ws_base.append(row_vals)
        last_row = ws_base.max_row
        for col_idx, c in enumerate(row_cells, start=1):
            fill = get_fill(c.get("type", ""))
            if fill:
                ws_base.cell(row=last_row, column=col_idx).fill = fill

    # 3. Sheet: Comparison Data
    ws_comp = wb.create_sheet(title="Comparison")
    ws_comp.append([sanitize_excel_cell(h) for h in headers])
    for cell in ws_comp[1]:
        cell.font = bold_font

    for row_cells in result.comparison_view.get("rows", []):
        row_vals = [sanitize_excel_cell(c.get("value", "")) for c in row_cells]
        ws_comp.append(row_vals)
        last_row = ws_comp.max_row
        for col_idx, c in enumerate(row_cells, start=1):
            fill = get_fill(c.get("type", ""))
            if fill:
                ws_comp.cell(row=last_row, column=col_idx).fill = fill

    # 4. Sheet: Change Log
    ws_log = wb.create_sheet(title="Change Log")
    log_headers = ["Change Type", "Location", "Original Value (File A)", "Updated Value (File B)", "Details"]
    ws_log.append(log_headers)
    for cell in ws_log[1]:
        cell.font = bold_font

    for change in result.changes:
        ws_log.append([
            change.type.value,
            change.location,
            sanitize_excel_cell(str(change.original_value or "")),
            sanitize_excel_cell(str(change.updated_value or "")),
            change.details or ""
        ])
        last_row = ws_log.max_row
        fill = get_fill(change.type.value)
        if fill:
            ws_log.cell(row=last_row, column=1).fill = fill

    for col in ("A", "B", "C", "D", "E"):
        ws_log.column_dimensions[col].width = 25

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def export_to_docx(result: ComparisonResult) -> io.BytesIO:
    doc = Document()

    # Title
    doc.add_heading(f"{result.summary.format} Comparison Report", level=0)

    # 1. Summary Section
    doc.add_heading("1. Comparison Summary", level=1)
    table = doc.add_table(rows=1, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Attribute"
    hdr_cells[1].text = "Value"

    summary_items = [
        ("Baseline File (A)", result.summary.file_a_name),
        ("Comparison File (B)", result.summary.file_b_name),
        ("Format", result.summary.format),
        ("Status", result.summary.status),
        ("Total Unchanged", f"{result.summary.total_unchanged} {result.summary.unit}"),
        ("Total Added", f"{result.summary.total_added} {result.summary.unit}"),
        ("Total Modified", f"{result.summary.total_modified} {result.summary.unit}"),
        ("Total Removed", f"{result.summary.total_removed} {result.summary.unit}"),
        ("Notice", result.summary.positional_notice or "None"),
    ]

    for item, val in summary_items:
        row_cells = table.add_row().cells
        row_cells[0].text = item
        row_cells[1].text = str(val)

    # 2. Detailed Change List
    doc.add_heading("2. Detailed Change Log", level=1)
    if not result.changes:
        doc.add_paragraph("No differences detected between File A and File B.")
    else:
        log_table = doc.add_table(rows=1, cols=4)
        c_hdr = log_table.rows[0].cells
        c_hdr[0].text = "Type"
        c_hdr[1].text = "Location"
        c_hdr[2].text = "Original Value (File A)"
        c_hdr[3].text = "Updated Value (File B)"

        for change in result.changes:
            row_cells = log_table.add_row().cells
            row_cells[0].text = change.type.value
            row_cells[1].text = change.location
            row_cells[2].text = str(change.original_value or "")
            row_cells[3].text = str(change.updated_value or "")

    # 3. Content Snapshots
    doc.add_heading("3. File Content Snapshots", level=1)
    doc.add_heading("Baseline File (A)", level=2)

    if result.summary.format == "TXT":
        for line in result.baseline_view:
            p = doc.add_paragraph()
            p.add_run(f"[{line.get('type')}] Line {line.get('line_num')}: {line.get('text')}")
        doc.add_heading("Comparison File (B)", level=2)
        for line in result.comparison_view:
            p = doc.add_paragraph()
            p.add_run(f"[{line.get('type')}] Line {line.get('line_num')}: {line.get('text')}")

    elif result.summary.format == "JSON":
        doc.add_paragraph("File A JSON Content:")
        base_text = "\n".join(result.baseline_view) if isinstance(result.baseline_view, list) else str(result.baseline_view)
        comp_text = "\n".join(result.comparison_view) if isinstance(result.comparison_view, list) else str(result.comparison_view)
        doc.add_paragraph(base_text)
        doc.add_heading("Comparison File (B)", level=2)
        doc.add_paragraph("File B JSON Content:")
        doc.add_paragraph(comp_text)

    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream
