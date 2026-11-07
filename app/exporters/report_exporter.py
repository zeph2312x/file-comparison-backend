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

    # Sheet: Change Log (Only changes and compared files reference)
    ws_log = wb.active
    ws_log.title = "Changes"

    header_font = Font(name="Calibri", size=14, bold=True)
    bold_font = Font(name="Calibri", size=11, bold=True)
    reg_font = Font(name="Calibri", size=11)

    ws_log["A1"] = "File Comparison Changes Report"
    ws_log["A1"].font = header_font

    ws_log["A3"] = "Target File (Changes Shown):"
    ws_log["A3"].font = bold_font
    ws_log["B3"] = result.summary.file_b_name
    ws_log["B3"].font = reg_font

    ws_log["A4"] = "Compared Against (Reference):"
    ws_log["A4"].font = bold_font
    ws_log["B4"] = result.summary.file_a_name
    ws_log["B4"].font = reg_font

    ws_log["A5"] = "Format:"
    ws_log["A5"].font = bold_font
    ws_log["B5"] = result.summary.format
    ws_log["B5"].font = reg_font

    # Color Fills
    fill_added = PatternFill(start_color=COLOR_ADDED_HEX, end_color=COLOR_ADDED_HEX, fill_type="solid")
    fill_modified = PatternFill(start_color=COLOR_MODIFIED_HEX, end_color=COLOR_MODIFIED_HEX, fill_type="solid")
    fill_removed = PatternFill(start_color=COLOR_REMOVED_HEX, end_color=COLOR_REMOVED_HEX, fill_type="solid")

    def get_fill(ctype: str):
        if ctype == ChangeType.ADDED.value:
            return fill_added
        elif ctype == ChangeType.MODIFIED.value:
            return fill_modified
        elif ctype == ChangeType.REMOVED.value:
            return fill_removed
        return None

    # Table Header at Row 7
    log_headers = ["Change Type", "Location", f"Reference Value ({result.summary.file_a_name})", f"Target Value ({result.summary.file_b_name})", "Details"]
    ws_log.append([])
    ws_log.append(log_headers)
    for cell in ws_log[7]:
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
        ws_log.column_dimensions[col].width = 28

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def export_to_docx(result: ComparisonResult) -> io.BytesIO:
    doc = Document()

    # Title
    doc.add_heading("File Comparison Report", level=0)

    # 1. Comparison Reference Section
    doc.add_heading("Comparison Files", level=1)
    p = doc.add_paragraph()
    p.add_run("Target File (Changes shown): ").bold = True
    p.add_run(f"{result.summary.file_b_name}\n")
    p.add_run("Compared Against (Reference File): ").bold = True
    p.add_run(f"{result.summary.file_a_name}\n")
    p.add_run("Format: ").bold = True
    p.add_run(f"{result.summary.format}\n")
    p.add_run("Status: ").bold = True
    p.add_run(f"{result.summary.status}")

    # 2. Changes Section
    doc.add_heading("Changes", level=1)
    if not result.changes:
        doc.add_paragraph("No differences detected between the compared files.")
    else:
        log_table = doc.add_table(rows=1, cols=4)
        c_hdr = log_table.rows[0].cells
        c_hdr[0].text = "Change Type"
        c_hdr[1].text = "Location"
        c_hdr[2].text = f"Reference Value ({result.summary.file_a_name})"
        c_hdr[3].text = f"Target Value ({result.summary.file_b_name})"

        for change in result.changes:
            row_cells = log_table.add_row().cells
            row_cells[0].text = change.type.value
            row_cells[1].text = change.location
            row_cells[2].text = str(change.original_value if change.original_value is not None else "-")
            row_cells[3].text = str(change.updated_value if change.updated_value is not None else "-")

    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream
