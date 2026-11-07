import csv
import io
import json
from typing import Any, List, Tuple


class FileValidationError(Exception):
    pass


def validate_file_size(content: bytes, max_mb: int = 10):
    if len(content) > max_mb * 1024 * 1024:
        raise FileValidationError(f"File exceeds maximum allowed size of {max_mb}MB.")
    if len(content) == 0:
        raise FileValidationError("File is empty (0 bytes).")


def parse_csv(content: bytes) -> Tuple[List[str], List[List[str]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception as e:
            raise FileValidationError(f"Could not decode CSV text: {str(e)}")

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise FileValidationError("CSV file contains no valid rows.")

    reader = csv.reader(lines)
    all_rows = list(reader)
    if not all_rows:
        raise FileValidationError("CSV file contains no readable data.")

    headers = [h.strip() for h in all_rows[0]]
    if len(headers) != len(set(headers)):
        raise FileValidationError("CSV file contains duplicate column headers which are ambiguous.")

    data_rows = all_rows[1:]
    return headers, data_rows


def parse_json(content: bytes) -> Any:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FileValidationError("JSON file must be UTF-8 encoded.")

    if not text.strip():
        raise FileValidationError("JSON file contains no content.")

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise FileValidationError(f"Invalid JSON syntax: {e.msg} (line {e.lineno}, column {e.colno})")


def parse_txt(content: bytes) -> List[str]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception as e:
            raise FileValidationError(f"Could not decode plain text: {str(e)}")

    # Normalize line endings CRLF -> LF
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.split("\n")
