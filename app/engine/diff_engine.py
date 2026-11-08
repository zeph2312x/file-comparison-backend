import difflib
import json
import re
from typing import Any, Dict, List, Tuple
from app.models import ChangeItem, ChangeType, ComparisonResult, DiffSummary


def compute_word_diff_chunks(text_a: str, text_b: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Tokenizes two modified lines into words/whitespace and produces chunks with highlight flags."""
    # Split into words, spaces, and punctuation tokens preserving exact characters
    tokens_a = re.findall(r"\w+|\s+|[^\w\s]", text_a)
    tokens_b = re.findall(r"\w+|\s+|[^\w\s]", text_b)

    matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b)
    chunks_a = []
    chunks_b = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        part_a = "".join(tokens_a[i1:i2])
        part_b = "".join(tokens_b[j1:j2])

        if tag == "equal":
            if part_a:
                chunks_a.append({"text": part_a, "highlight": False})
            if part_b:
                chunks_b.append({"text": part_b, "highlight": False})
        elif tag == "replace":
            if part_a:
                chunks_a.append({"text": part_a, "highlight": True})
            if part_b:
                chunks_b.append({"text": part_b, "highlight": True})
        elif tag == "delete":
            if part_a:
                chunks_a.append({"text": part_a, "highlight": True})
        elif tag == "insert":
            if part_b:
                chunks_b.append({"text": part_b, "highlight": True})

    return chunks_a, chunks_b


def compare_csv_data(
    file_a_name: str,
    file_b_name: str,
    headers_a: List[str],
    rows_a: List[List[str]],
    headers_b: List[str],
    rows_b: List[List[str]],
) -> ComparisonResult:
    changes: List[ChangeItem] = []
    total_unchanged = 0
    total_added = 0
    total_modified = 0
    total_removed = 0

    all_headers = []
    for h in headers_a:
        if h not in all_headers:
            all_headers.append(h)
    for h in headers_b:
        if h not in all_headers:
            all_headers.append(h)

    # Header diffs
    for h in headers_a:
        if h not in headers_b:
            total_removed += 1
            changes.append(ChangeItem(
                type=ChangeType.REMOVED,
                location=f"Header: {h}",
                original_value=h,
                updated_value=None,
                details=f"Column '{h}' removed in File B"
            ))
    for h in headers_b:
        if h not in headers_a:
            total_added += 1
            changes.append(ChangeItem(
                type=ChangeType.ADDED,
                location=f"Header: {h}",
                original_value=None,
                updated_value=h,
                details=f"Column '{h}' added in File B"
            ))

    col_index_a = {h: i for i, h in enumerate(headers_a)}
    col_index_b = {h: i for i, h in enumerate(headers_b)}

    max_rows = max(len(rows_a), len(rows_b))
    baseline_view_rows = []
    comparison_view_rows = []

    for r_idx in range(max_rows):
        has_a = r_idx < len(rows_a)
        has_b = r_idx < len(rows_b)
        row_num = r_idx + 1

        row_a_cells = []
        row_b_cells = []

        if has_a and not has_b:
            total_removed += 1
            changes.append(ChangeItem(
                type=ChangeType.REMOVED,
                location=f"Row {row_num}",
                original_value=", ".join(rows_a[r_idx]),
                updated_value=None,
                details="Entire row removed in File B"
            ))
            for h in all_headers:
                val_a = rows_a[r_idx][col_index_a[h]] if h in col_index_a and col_index_a[h] < len(rows_a[r_idx]) else ""
                row_a_cells.append({"value": val_a, "type": ChangeType.REMOVED.value})
                row_b_cells.append({"value": "", "type": "empty"})

        elif not has_a and has_b:
            total_added += 1
            changes.append(ChangeItem(
                type=ChangeType.ADDED,
                location=f"Row {row_num}",
                original_value=None,
                updated_value=", ".join(rows_b[r_idx]),
                details="Entire row added in File B"
            ))
            for h in all_headers:
                val_b = rows_b[r_idx][col_index_b[h]] if h in col_index_b and col_index_b[h] < len(rows_b[r_idx]) else ""
                row_a_cells.append({"value": "", "type": "empty"})
                row_b_cells.append({"value": val_b, "type": ChangeType.ADDED.value})

        else:
            # Both rows exist: cell-by-cell comparison
            row_data_a = rows_a[r_idx]
            row_data_b = rows_b[r_idx]

            for h in all_headers:
                in_a = h in col_index_a and col_index_a[h] < len(row_data_a)
                in_b = h in col_index_b and col_index_b[h] < len(row_data_b)

                val_a = row_data_a[col_index_a[h]] if in_a else ""
                val_b = row_data_b[col_index_b[h]] if in_b else ""

                if in_a and not in_b:
                    total_removed += 1
                    row_a_cells.append({"value": val_a, "type": ChangeType.REMOVED.value})
                    row_b_cells.append({"value": "", "type": "empty"})
                    changes.append(ChangeItem(
                        type=ChangeType.REMOVED,
                        location=f"Row {row_num}, Column {h}",
                        original_value=val_a,
                        updated_value=None
                    ))
                elif not in_a and in_b:
                    total_added += 1
                    row_a_cells.append({"value": "", "type": "empty"})
                    row_b_cells.append({"value": val_b, "type": ChangeType.ADDED.value})
                    changes.append(ChangeItem(
                        type=ChangeType.ADDED,
                        location=f"Row {row_num}, Column {h}",
                        original_value=None,
                        updated_value=val_b
                    ))
                else:
                    if val_a == val_b:
                        total_unchanged += 1
                        row_a_cells.append({"value": val_a, "type": ChangeType.UNCHANGED.value})
                        row_b_cells.append({"value": val_b, "type": ChangeType.UNCHANGED.value})
                    else:
                        total_modified += 1
                        row_a_cells.append({"value": val_a, "type": ChangeType.MODIFIED.value})
                        row_b_cells.append({"value": val_b, "type": ChangeType.MODIFIED.value})
                        changes.append(ChangeItem(
                            type=ChangeType.MODIFIED,
                            location=f"Row {row_num}, Column {h}",
                            original_value=val_a,
                            updated_value=val_b
                        ))

        baseline_view_rows.append(row_a_cells)
        comparison_view_rows.append(row_b_cells)

    has_diffs = (total_added + total_modified + total_removed) > 0
    status = "Differences detected" if has_diffs else "No differences"

    summary = DiffSummary(
        file_a_name=file_a_name,
        file_b_name=file_b_name,
        format="CSV",
        total_unchanged=total_unchanged,
        total_added=total_added,
        total_modified=total_modified,
        total_removed=total_removed,
        unit="cells/rows",
        status=status,
        positional_notice="Positional comparison used: rows are matched by their 1-based index."
    )

    baseline_view = {"headers": all_headers, "rows": baseline_view_rows}
    comparison_view = {"headers": all_headers, "rows": comparison_view_rows}

    return ComparisonResult(
        summary=summary,
        changes=changes,
        baseline_view=baseline_view,
        comparison_view=comparison_view
    )


def compare_json_data(file_a_name: str, file_b_name: str, json_a: Any, json_b: Any) -> ComparisonResult:
    changes: List[ChangeItem] = []
    counts = {"unchanged": 0, "added": 0, "modified": 0, "removed": 0}

    def walk_diff(path: str, val_a: Any, val_b: Any):
        if val_a == val_b:
            counts["unchanged"] += 1
            return

        # Both are dicts
        if isinstance(val_a, dict) and isinstance(val_b, dict):
            all_keys = sorted(list(set(val_a.keys()) | set(val_b.keys())))
            for k in all_keys:
                subpath = f"{path}.{k}" if path != "$" else f"$.{k}"
                if k in val_a and k not in val_b:
                    counts["removed"] += 1
                    changes.append(ChangeItem(
                        type=ChangeType.REMOVED,
                        location=subpath,
                        original_value=val_a[k],
                        updated_value=None,
                        details=f"Key '{k}' removed in File B"
                    ))
                elif k not in val_a and k in val_b:
                    counts["added"] += 1
                    changes.append(ChangeItem(
                        type=ChangeType.ADDED,
                        location=subpath,
                        original_value=None,
                        updated_value=val_b[k],
                        details=f"Key '{k}' added in File B"
                    ))
                else:
                    walk_diff(subpath, val_a[k], val_b[k])

        # Both are lists
        elif isinstance(val_a, list) and isinstance(val_b, list):
            max_len = max(len(val_a), len(val_b))
            for i in range(max_len):
                subpath = f"{path}[{i}]"
                if i < len(val_a) and i >= len(val_b):
                    counts["removed"] += 1
                    changes.append(ChangeItem(
                        type=ChangeType.REMOVED,
                        location=subpath,
                        original_value=val_a[i],
                        updated_value=None,
                        details="Array element removed"
                    ))
                elif i >= len(val_a) and i < len(val_b):
                    counts["added"] += 1
                    changes.append(ChangeItem(
                        type=ChangeType.ADDED,
                        location=subpath,
                        original_value=None,
                        updated_value=val_b[i],
                        details="Array element added"
                    ))
                else:
                    walk_diff(subpath, val_a[i], val_b[i])

        else:
            # Primitive modification or type change
            counts["modified"] += 1
            changes.append(ChangeItem(
                type=ChangeType.MODIFIED,
                location=path,
                original_value=val_a,
                updated_value=val_b
            ))

    walk_diff("$", json_a, json_b)

    has_diffs = (counts["added"] + counts["modified"] + counts["removed"]) > 0
    status = "Differences detected" if has_diffs else "No differences"

    summary = DiffSummary(
        file_a_name=file_a_name,
        file_b_name=file_b_name,
        format="JSON",
        total_unchanged=counts["unchanged"],
        total_added=counts["added"],
        total_modified=counts["modified"],
        total_removed=counts["removed"],
        unit="nodes/paths",
        status=status,
        positional_notice="JSON keys compared by path; arrays compared by element index."
    )

    baseline_lines = json.dumps(json_a, indent=2).splitlines()
    comparison_lines = json.dumps(json_b, indent=2).splitlines()

    # Map paths to diff types for line-matching in JSON
    # We will pass both formatted string lines and the change list to highlight
    return ComparisonResult(
        summary=summary,
        changes=changes,
        baseline_view=baseline_lines,
        comparison_view=comparison_lines
    )


def compare_txt_data(file_a_name: str, file_b_name: str, lines_a: List[str], lines_b: List[str]) -> ComparisonResult:
    changes: List[ChangeItem] = []
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)

    total_unchanged = 0
    total_added = 0
    total_modified = 0
    total_removed = 0

    aligned_a = []
    aligned_b = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for idx, line in enumerate(lines_a[i1:i2]):
                line_no_a = i1 + idx + 1
                line_no_b = j1 + idx + 1
                total_unchanged += 1
                aligned_a.append({"line_num": line_no_a, "text": line, "type": ChangeType.UNCHANGED.value})
                aligned_b.append({"line_num": line_no_b, "text": line, "type": ChangeType.UNCHANGED.value})

        elif tag == "replace":
            len_a = i2 - i1
            len_b = j2 - j1
            max_len = max(len_a, len_b)
            for k in range(max_len):
                orig_text = lines_a[i1 + k] if k < len_a else None
                upd_text = lines_b[j1 + k] if k < len_b else None
                orig_no = (i1 + k + 1) if k < len_a else None
                upd_no = (j1 + k + 1) if k < len_b else None

                if orig_text is not None and upd_text is not None:
                    total_modified += 1
                    chunks_a, chunks_b = compute_word_diff_chunks(orig_text, upd_text)
                    changes.append(ChangeItem(
                        type=ChangeType.MODIFIED,
                        location=f"Line {orig_no} -> {upd_no}",
                        original_value=orig_text,
                        updated_value=upd_text
                    ))
                    aligned_a.append({
                        "line_num": orig_no,
                        "text": orig_text,
                        "type": ChangeType.MODIFIED.value,
                        "chunks": chunks_a
                    })
                    aligned_b.append({
                        "line_num": upd_no,
                        "text": upd_text,
                        "type": ChangeType.MODIFIED.value,
                        "chunks": chunks_b
                    })
                elif orig_text is not None:
                    total_removed += 1
                    changes.append(ChangeItem(
                        type=ChangeType.REMOVED,
                        location=f"Line {orig_no}",
                        original_value=orig_text,
                        updated_value=None
                    ))
                    aligned_a.append({"line_num": orig_no, "text": orig_text, "type": ChangeType.REMOVED.value})
                    aligned_b.append({"line_num": "", "text": "", "type": "empty"})
                else:
                    total_added += 1
                    changes.append(ChangeItem(
                        type=ChangeType.ADDED,
                        location=f"Line {upd_no}",
                        original_value=None,
                        updated_value=upd_text
                    ))
                    aligned_a.append({"line_num": "", "text": "", "type": "empty"})
                    aligned_b.append({"line_num": upd_no, "text": upd_text, "type": ChangeType.ADDED.value})

        elif tag == "delete":
            for k in range(i2 - i1):
                orig_no = i1 + k + 1
                orig_text = lines_a[i1 + k]
                total_removed += 1
                changes.append(ChangeItem(
                    type=ChangeType.REMOVED,
                    location=f"Line {orig_no}",
                    original_value=orig_text,
                    updated_value=None
                ))
                aligned_a.append({"line_num": orig_no, "text": orig_text, "type": ChangeType.REMOVED.value})
                aligned_b.append({"line_num": "", "text": "", "type": "empty"})

        elif tag == "insert":
            for k in range(j2 - j1):
                upd_no = j1 + k + 1
                upd_text = lines_b[j1 + k]
                total_added += 1
                changes.append(ChangeItem(
                    type=ChangeType.ADDED,
                    location=f"Line {upd_no}",
                    original_value=None,
                    updated_value=upd_text
                ))
                aligned_a.append({"line_num": "", "text": "", "type": "empty"})
                aligned_b.append({"line_num": upd_no, "text": upd_text, "type": ChangeType.ADDED.value})

    has_diffs = (total_added + total_modified + total_removed) > 0
    status = "Differences detected" if has_diffs else "No differences"

    summary = DiffSummary(
        file_a_name=file_a_name,
        file_b_name=file_b_name,
        format="TXT",
        total_unchanged=total_unchanged,
        total_added=total_added,
        total_modified=total_modified,
        total_removed=total_removed,
        unit="lines",
        status=status,
        positional_notice="Aligned sequence diff applied for line-by-line comparison."
    )

    return ComparisonResult(
        summary=summary,
        changes=changes,
        baseline_view=aligned_a,
        comparison_view=aligned_b
    )
