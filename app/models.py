from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel


class ChangeType(str, Enum):
    UNCHANGED = "Unchanged"
    ADDED = "Added"
    MODIFIED = "Modified"
    REMOVED = "Removed"


class ChangeItem(BaseModel):
    type: ChangeType
    location: str  # e.g., "Row 2, Salary" or "$.user.age" or "Line 5"
    original_value: Optional[Any] = None
    updated_value: Optional[Any] = None
    details: Optional[str] = None


class DiffSummary(BaseModel):
    file_a_name: str
    file_b_name: str
    format: str
    total_unchanged: int = 0
    total_added: int = 0
    total_modified: int = 0
    total_removed: int = 0
    unit: str  # "cells", "nodes", "lines"
    status: str = "Differences detected"  # or "No differences"
    positional_notice: Optional[str] = None


class ComparisonResult(BaseModel):
    summary: DiffSummary
    changes: List[ChangeItem]
    # Raw structured payload for side-by-side rendering in the UI
    baseline_view: Any
    comparison_view: Any
