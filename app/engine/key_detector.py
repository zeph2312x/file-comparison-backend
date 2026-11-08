import re
from typing import Any, Dict, List, Tuple
from app.models import ChangeItem, ChangeType, ComparisonResult, DiffSummary
import difflib
import json


def find_candidate_key_column(headers_a: List[str], headers_b: List[str], rows_a: List[List[str]], rows_b: List[List[str]]) -> str:
    """Finds an ID or key column present in both files where values are mostly unique."""
    common_headers = [h for h in headers_a if h in headers_b]
    if not common_headers:
        return ""

    # Priority 1: Common ID/key names
    candidate_names = ["id", "employee_id", "emp_id", "key", "uuid", "code", "email", "username", "name"]
    for c in candidate_names:
        for h in common_headers:
            if h.lower() == c or h.lower().endswith("_id"):
                idx_a = headers_a.index(h)
                vals_a = [r[idx_a] for r in rows_a if idx_a < len(r)]
                # Check uniqueness in A
                if len(vals_a) == len(set(vals_a)) and len(vals_a) > 0:
                    return h

    # Priority 2: Check any column that is 100% unique in both files
    for h in common_headers:
        idx_a = headers_a.index(h)
        idx_b = headers_b.index(h)
        vals_a = [r[idx_a] for r in rows_a if idx_a < len(r)]
        vals_b = [r[idx_b] for r in rows_b if idx_b < len(r)]
        if len(vals_a) == len(set(vals_a)) and len(vals_b) == len(set(vals_b)) and len(vals_a) > 0:
            return h

    return ""
