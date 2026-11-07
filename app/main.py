import json
from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.models import ComparisonResult
from app.parsers.file_parsers import (
    FileValidationError,
    parse_csv,
    parse_json,
    parse_txt,
    validate_file_size,
)
from app.engine.diff_engine import (
    compare_csv_data,
    compare_json_data,
    compare_txt_data,
)
from app.exporters.report_exporter import export_csv_to_xlsx, export_to_docx

app = FastAPI(
    title="File Comparison API",
    description="Deterministic two-file comparison engine for CSV, JSON, and TXT files",
    version="1.0.0",
)

# Enable CORS for decoupled frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/v1/compare", response_model=ComparisonResult)
async def compare_files(
    format: str = Form(..., description="File format: csv, json, or txt"),
    file_a: UploadFile = File(..., description="Baseline file (A)"),
    file_b: UploadFile = File(..., description="Comparison file (B)"),
):
    format_clean = format.lower().strip()
    if format_clean not in ("csv", "json", "txt"):
        raise HTTPException(status_code=400, detail=f"Unsupported format '{format}'. Supported: csv, json, txt.")

    # Validate file extension
    ext_a = file_a.filename.split(".")[-1].lower() if "." in file_a.filename else ""
    ext_b = file_b.filename.split(".")[-1].lower() if "." in file_b.filename else ""

    if ext_a != format_clean or ext_b != format_clean:
        raise HTTPException(
            status_code=400,
            detail=f"Both files must have the extension '.{format_clean}'. Got '{file_a.filename}' and '{file_b.filename}'."
        )

    content_a = await file_a.read()
    content_b = await file_b.read()

    try:
        validate_file_size(content_a, max_mb=10)
        validate_file_size(content_b, max_mb=10)
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        if format_clean == "csv":
            headers_a, rows_a = parse_csv(content_a)
            headers_b, rows_b = parse_csv(content_b)
            return compare_csv_data(file_a.filename, file_b.filename, headers_a, rows_a, headers_b, rows_b)

        elif format_clean == "json":
            json_a = parse_json(content_a)
            json_b = parse_json(content_b)
            return compare_json_data(file_a.filename, file_b.filename, json_a, json_b)

        elif format_clean == "txt":
            lines_a = parse_txt(content_a)
            lines_b = parse_txt(content_b)
            return compare_txt_data(file_a.filename, file_b.filename, lines_a, lines_b)

    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@app.post("/api/v1/export")
async def export_report(result_json: str = Form(..., description="ComparisonResult JSON string")):
    try:
        data = json.loads(result_json)
        result = ComparisonResult(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid comparison result structure: {str(e)}")

    if result.summary.format.upper() == "CSV":
        stream = export_csv_to_xlsx(result)
        filename = f"comparison_report_{result.summary.file_a_name}.xlsx"
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    else:
        stream = export_to_docx(result)
        filename = f"comparison_report_{result.summary.file_a_name}.docx"
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
