import csv
import os
import re
from typing import List, Optional, Tuple


def _parse_all_statements(path: str) -> Optional[List[dict]]:
    """Parse all statement blocks from a result file (.exp or .res).

    Returns None if the file does not exist.
    Returns a list of dicts, one per statement block:
      {"num": 1, "sql": "SET @x=1;", "type": "no_result"}
      {"num": 2, "sql": "INSERT ...", "type": "dml", "affected": 3}
      {"num": 3, "sql": "SELECT ...", "type": "select",
       "cols": ["id", "name"], "rows": [["1", "Alice"]]}
    """
    if not os.path.exists(path):
        return None

    blocks = []
    current: Optional[dict] = None

    def flush():
        if current:
            blocks.append(current)

    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue

            raw = row[0].strip() if row else ""

            if raw.startswith("-- STATEMENT"):
                flush()
                m = re.match(r"-- STATEMENT\s+(\d+):\s*(.*)", raw)
                num = int(m.group(1)) if m else len(blocks) + 1
                sql = m.group(2).strip() if m else ""
                current = {"num": num, "sql": sql, "type": None}

            elif raw.startswith("-- NO RESULT"):
                if current:
                    current["type"] = "no_result"

            elif raw.startswith("-- ROWS AFFECTED:"):
                if current:
                    try:
                        affected = int(raw.split(":")[1].strip())
                    except (IndexError, ValueError):
                        affected = 0
                    current["type"] = "dml"
                    current["affected"] = affected

            elif not raw.startswith("--"):
                if current:
                    if current.get("type") is None:
                        current["type"] = "select"
                        current["cols"] = row
                        current["rows"] = []
                    elif current["type"] == "select":
                        current["rows"].append(row)

    flush()
    return blocks


def _parse_result_file(path: str) -> Tuple[Optional[List[str]], List[List[str]]]:
    """Extract the last SELECT result set. Kept for unit test backward compat."""
    if not os.path.exists(path):
        return None, []
    blocks = _parse_all_statements(path)
    if blocks is None:
        return None, []
    select_blocks = [b for b in blocks if b.get("type") == "select"]
    if not select_blocks:
        return None, []
    last = select_blocks[-1]
    return last.get("cols", []), last.get("rows", [])


def _parse_test_blocks(path: str) -> Optional[dict]:
    """Parse a suite-level result file into {test_name: [statement_blocks]}.
    Returns None if the file does not exist.
    """
    if not os.path.exists(path):
        return None

    result = {}
    current_test_name: Optional[str] = None
    current_blocks: List[dict] = []
    current_stmt: Optional[dict] = None

    def commit_stmt():
        nonlocal current_stmt
        if current_stmt is not None:
            current_blocks.append(current_stmt)
            current_stmt = None

    def commit_test():
        commit_stmt()
        if current_test_name is not None:
            result[current_test_name] = list(current_blocks)

    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            raw = row[0].strip()

            if raw.startswith("-- TEST:"):
                commit_test()
                current_test_name = raw[len("-- TEST:"):].strip()
                current_blocks = []
                current_stmt = None

            elif raw.startswith("-- STATEMENT"):
                commit_stmt()
                m = re.match(r"-- STATEMENT\s+(\d+):\s*(.*)", raw)
                num = int(m.group(1)) if m else len(current_blocks) + 1
                sql_text = m.group(2).strip() if m else ""
                current_stmt = {"num": num, "sql": sql_text, "type": None}

            elif raw.startswith("-- NO RESULT"):
                if current_stmt:
                    current_stmt["type"] = "no_result"

            elif raw.startswith("-- ROWS AFFECTED:"):
                if current_stmt:
                    try:
                        affected = int(raw.split(":")[1].strip())
                    except (IndexError, ValueError):
                        affected = 0
                    current_stmt["type"] = "dml"
                    current_stmt["affected"] = affected

            elif not raw.startswith("--"):
                if current_stmt:
                    if current_stmt.get("type") is None:
                        current_stmt["type"] = "select"
                        current_stmt["cols"] = row
                        current_stmt["rows"] = []
                    elif current_stmt["type"] == "select":
                        current_stmt["rows"].append(row)

    commit_test()
    return result


def _normalize_float(val: str, precision: int) -> str:
    try:
        return f"{float(val):.{precision}f}"
    except ValueError:
        return val


def _normalize_row(row: List[str], precision: int) -> List[str]:
    return [_normalize_float(v, precision) for v in row]


def _compare_select(exp_block: dict, res_block: dict,
                    float_precision: int, label: str) -> Optional[str]:
    """Compare two SELECT blocks. Returns an error message or None."""
    exp_cols = exp_block.get("cols", [])
    res_cols = res_block.get("cols", [])

    if exp_cols != res_cols:
        return (f"{label}: Column mismatch.\n"
                f"  Expected: {exp_cols}\n"
                f"  Got:      {res_cols}")

    exp_norm = sorted(_normalize_row(r, float_precision)
                      for r in exp_block.get("rows", []))
    res_norm = sorted(_normalize_row(r, float_precision)
                      for r in res_block.get("rows", []))

    if exp_norm != res_norm:
        missing = [r for r in exp_norm if r not in res_norm]
        extra   = [r for r in res_norm  if r not in exp_norm]
        msg = f"{label}: Row mismatch (unordered)."
        if missing:
            msg += f"\n  Missing rows: {missing}"
        if extra:
            msg += f"\n  Extra rows:   {extra}"
        return msg

    return None


def compare(exp_path: str, res_path: str, test_name: str,
            float_precision: int) -> Tuple[bool, str]:
    """Compare one test's statement blocks between .exp and .res files."""
    exp_all = _parse_test_blocks(exp_path)
    res_all = _parse_test_blocks(res_path)

    if exp_all is None:
        return False, f"Expected file not found: {exp_path}"
    if res_all is None:
        return False, f"Result file not found: {res_path}"

    exp_blocks = exp_all.get(test_name)
    res_blocks = res_all.get(test_name)

    if exp_blocks is None:
        return False, f"Test '{test_name}' block not found in expected file"
    if res_blocks is None:
        return False, f"Test '{test_name}' block not found in result file"

    if len(exp_blocks) != len(res_blocks):
        return False, (
            f"Statement count mismatch.\n"
            f"  Expected: {len(exp_blocks)} statement(s)\n"
            f"  Got:      {len(res_blocks)} statement(s)"
        )

    errors = []

    for exp_b, res_b in zip(exp_blocks, res_blocks):
        label = f"STATEMENT {exp_b['num']} ({exp_b['sql'][:60]})"
        exp_type = exp_b.get("type")
        res_type = res_b.get("type")

        if exp_type != res_type:
            errors.append(
                f"{label}: Type mismatch.\n"
                f"  Expected: {exp_type}\n"
                f"  Got:      {res_type}"
            )
            continue

        if exp_type == "dml":
            exp_affected = exp_b.get("affected", 0)
            res_affected = res_b.get("affected", 0)
            if exp_affected != res_affected:
                errors.append(
                    f"{label}: Rows affected mismatch.\n"
                    f"  Expected: {exp_affected}\n"
                    f"  Got:      {res_affected}"
                )

        elif exp_type == "select":
            err = _compare_select(exp_b, res_b, float_precision, label)
            if err:
                errors.append(err)

    if errors:
        return False, "\n".join(errors)

    return True, ""
