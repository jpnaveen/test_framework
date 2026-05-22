import pytest
from framework.comparator import compare, _parse_result_file

TEST = "default_test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_result_file(path, blocks, test_name=TEST):
    """Write a suite-level result file with a -- TEST: header.

    blocks is a list of dicts:
      {"stmt": "SELECT ...", "cols": ["a","b"], "rows": [["1","2"]]}   # SELECT
      {"stmt": "INSERT ...", "affected": 3}                             # DML
      {"stmt": "SET ...", "no_result": True}                           # no result
    """
    lines = [f"-- TEST: {test_name}"]
    for i, b in enumerate(blocks, start=1):
        stmt_label = b.get("stmt", "")
        lines.append(f"-- STATEMENT {i}: {stmt_label}")
        if b.get("no_result"):
            lines.append("-- NO RESULT")
        elif "affected" in b:
            lines.append(f"-- ROWS AFFECTED: {b['affected']}")
        else:
            lines.append(",".join(b["cols"]))
            for row in b.get("rows", []):
                lines.append(",".join(row))
        lines.append("")
    path.write_text("\n".join(lines))


def simple_exp(tmp_path, cols, rows):
    p = tmp_path / "test.exp"
    write_result_file(p, [{"stmt": "SELECT ...", "cols": cols, "rows": rows}])
    return str(p)


def simple_res(tmp_path, cols, rows):
    p = tmp_path / "test.res"
    write_result_file(p, [{"stmt": "SELECT ...", "cols": cols, "rows": rows}])
    return str(p)


# ---------------------------------------------------------------------------
# Missing files
# ---------------------------------------------------------------------------

def test_missing_exp_file_returns_false(tmp_path):
    res = simple_res(tmp_path, ["id"], [["1"]])
    passed, msg = compare("/nonexistent/file.exp", res, TEST, 6)
    assert passed is False
    assert "Expected file not found" in msg


def test_missing_res_file_returns_false(tmp_path):
    exp = simple_exp(tmp_path, ["id"], [["1"]])
    passed, msg = compare(exp, "/nonexistent/file.res", TEST, 6)
    assert passed is False
    assert "Result file not found" in msg


# ---------------------------------------------------------------------------
# Exact match
# ---------------------------------------------------------------------------

def test_identical_files_pass(tmp_path):
    cols = ["customer_id", "order_count"]
    rows = [["1", "3"], ["2", "1"]]
    exp = simple_exp(tmp_path, cols, rows)
    res = simple_res(tmp_path, cols, rows)
    passed, msg = compare(exp, res, TEST, 6)
    assert passed is True
    assert msg == ""


def test_single_row_match(tmp_path):
    exp = simple_exp(tmp_path, ["total"], [["42"]])
    res = simple_res(tmp_path, ["total"], [["42"]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is True


# ---------------------------------------------------------------------------
# Row order independence
# ---------------------------------------------------------------------------

def test_different_row_order_passes(tmp_path):
    cols = ["id", "name"]
    exp = simple_exp(tmp_path, cols, [["1", "Alice"], ["2", "Bob"], ["3", "Carol"]])
    res = simple_res(tmp_path, cols, [["3", "Carol"], ["1", "Alice"], ["2", "Bob"]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is True


# ---------------------------------------------------------------------------
# Column mismatches
# ---------------------------------------------------------------------------

def test_column_order_mismatch_fails(tmp_path):
    exp = simple_exp(tmp_path, ["id", "name"], [["1", "Alice"]])
    res = simple_res(tmp_path, ["name", "id"], [["Alice", "1"]])
    passed, msg = compare(exp, res, TEST, 6)
    assert passed is False
    assert "Column mismatch" in msg


def test_extra_column_in_result_fails(tmp_path):
    exp = simple_exp(tmp_path, ["id"], [["1"]])
    res = simple_res(tmp_path, ["id", "extra"], [["1", "x"]])
    passed, msg = compare(exp, res, TEST, 6)
    assert passed is False
    assert "Column mismatch" in msg


def test_missing_column_in_result_fails(tmp_path):
    exp = simple_exp(tmp_path, ["id", "name"], [["1", "Alice"]])
    res = simple_res(tmp_path, ["id"], [["1"]])
    passed, msg = compare(exp, res, TEST, 6)
    assert passed is False
    assert "Column mismatch" in msg


# ---------------------------------------------------------------------------
# Row mismatches
# ---------------------------------------------------------------------------

def test_missing_row_in_result_fails(tmp_path):
    exp = simple_exp(tmp_path, ["id"], [["1"], ["2"]])
    res = simple_res(tmp_path, ["id"], [["1"]])
    passed, msg = compare(exp, res, TEST, 6)
    assert passed is False
    assert "Missing rows" in msg


def test_extra_row_in_result_fails(tmp_path):
    exp = simple_exp(tmp_path, ["id"], [["1"]])
    res = simple_res(tmp_path, ["id"], [["1"], ["2"]])
    passed, msg = compare(exp, res, TEST, 6)
    assert passed is False
    assert "Extra rows" in msg


def test_completely_different_rows_fail(tmp_path):
    exp = simple_exp(tmp_path, ["id"], [["1"], ["2"]])
    res = simple_res(tmp_path, ["id"], [["3"], ["4"]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is False


# ---------------------------------------------------------------------------
# NULL handling
# ---------------------------------------------------------------------------

def test_null_matches_null(tmp_path):
    exp = simple_exp(tmp_path, ["id", "name"], [["1", "NULL"]])
    res = simple_res(tmp_path, ["id", "name"], [["1", "NULL"]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is True


def test_null_does_not_match_empty_string(tmp_path):
    exp = simple_exp(tmp_path, ["name"], [["NULL"]])
    res = simple_res(tmp_path, ["name"], [[""]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is False


def test_empty_string_matches_empty_string(tmp_path):
    exp = simple_exp(tmp_path, ["name"], [[""]])
    res = simple_res(tmp_path, ["name"], [[""]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is True


# ---------------------------------------------------------------------------
# Float / decimal tolerance
# ---------------------------------------------------------------------------

def test_floats_within_tolerance_pass(tmp_path):
    exp = simple_exp(tmp_path, ["amount"], [["100.123456"]])
    res = simple_res(tmp_path, ["amount"], [["100.1234560"]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is True


def test_floats_outside_tolerance_fail(tmp_path):
    exp = simple_exp(tmp_path, ["amount"], [["100.123456"]])
    res = simple_res(tmp_path, ["amount"], [["100.123999"]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is False


def test_float_precision_respected(tmp_path):
    exp = simple_exp(tmp_path, ["v"], [["1.111"]])
    res = simple_res(tmp_path, ["v"], [["1.114"]])
    passed, _ = compare(exp, res, TEST, 2)
    assert passed is True


def test_integer_values_not_affected_by_float_precision(tmp_path):
    exp = simple_exp(tmp_path, ["count"], [["42"]])
    res = simple_res(tmp_path, ["count"], [["42"]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is True


# ---------------------------------------------------------------------------
# Zero rows
# ---------------------------------------------------------------------------

def test_both_zero_rows_pass(tmp_path):
    exp = simple_exp(tmp_path, ["id"], [])
    res = simple_res(tmp_path, ["id"], [])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is True


def test_exp_zero_rows_res_has_rows_fails(tmp_path):
    exp = simple_exp(tmp_path, ["id"], [])
    res = simple_res(tmp_path, ["id"], [["1"]])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is False


def test_res_zero_rows_exp_has_rows_fails(tmp_path):
    exp = simple_exp(tmp_path, ["id"], [["1"]])
    res = simple_res(tmp_path, ["id"], [])
    passed, _ = compare(exp, res, TEST, 6)
    assert passed is False


# ---------------------------------------------------------------------------
# Multi-statement comparison
# ---------------------------------------------------------------------------

def test_all_statements_match_passes(tmp_path):
    exp_p = tmp_path / "test.exp"
    res_p = tmp_path / "test.res"
    blocks = [
        {"stmt": "SET @x = 1;", "no_result": True},
        {"stmt": "INSERT INTO t VALUES (1);", "affected": 1},
        {"stmt": "SELECT id FROM t;", "cols": ["id"], "rows": [["1"]]},
    ]
    write_result_file(exp_p, blocks)
    write_result_file(res_p, blocks)
    passed, _ = compare(str(exp_p), str(res_p), TEST, 6)
    assert passed is True


def test_intermediate_dml_mismatch_fails(tmp_path):
    exp_p = tmp_path / "test.exp"
    res_p = tmp_path / "test.res"
    write_result_file(exp_p, [
        {"stmt": "INSERT INTO t VALUES (1);", "affected": 1},
        {"stmt": "SELECT id FROM t;", "cols": ["id"], "rows": [["1"]]},
    ])
    write_result_file(res_p, [
        {"stmt": "INSERT INTO t VALUES (1);", "affected": 5},
        {"stmt": "SELECT id FROM t;", "cols": ["id"], "rows": [["1"]]},
    ])
    passed, msg = compare(str(exp_p), str(res_p), TEST, 6)
    assert passed is False
    assert "Rows affected mismatch" in msg


def test_select_mismatch_fails(tmp_path):
    exp_p = tmp_path / "test.exp"
    res_p = tmp_path / "test.res"
    write_result_file(exp_p, [
        {"stmt": "SET @x = 1;", "no_result": True},
        {"stmt": "SELECT id FROM t;", "cols": ["id"], "rows": [["1"]]},
    ])
    write_result_file(res_p, [
        {"stmt": "SET @x = 1;", "no_result": True},
        {"stmt": "SELECT id FROM t;", "cols": ["id"], "rows": [["99"]]},
    ])
    passed, _ = compare(str(exp_p), str(res_p), TEST, 6)
    assert passed is False


def test_single_dml_matching_passes(tmp_path):
    exp_p = tmp_path / "test.exp"
    res_p = tmp_path / "test.res"
    write_result_file(exp_p, [{"stmt": "INSERT INTO t VALUES (1);", "affected": 1}])
    write_result_file(res_p, [{"stmt": "INSERT INTO t VALUES (1);", "affected": 1}])
    passed, _ = compare(str(exp_p), str(res_p), TEST, 6)
    assert passed is True


def test_statement_count_mismatch_fails(tmp_path):
    exp_p = tmp_path / "test.exp"
    res_p = tmp_path / "test.res"
    write_result_file(exp_p, [
        {"stmt": "SET @x = 1;", "no_result": True},
        {"stmt": "SELECT id FROM t;", "cols": ["id"], "rows": [["1"]]},
    ])
    write_result_file(res_p, [
        {"stmt": "SELECT id FROM t;", "cols": ["id"], "rows": [["1"]]},
    ])
    passed, msg = compare(str(exp_p), str(res_p), TEST, 6)
    assert passed is False
    assert "Statement count mismatch" in msg


def test_no_result_both_sides_passes(tmp_path):
    exp_p = tmp_path / "test.exp"
    res_p = tmp_path / "test.res"
    write_result_file(exp_p, [
        {"stmt": "SET @cutoff = 1;", "no_result": True},
        {"stmt": "SELECT id FROM t;", "cols": ["id"], "rows": [["1"]]},
    ])
    write_result_file(res_p, [
        {"stmt": "SET @cutoff = 1;", "no_result": True},
        {"stmt": "SELECT id FROM t;", "cols": ["id"], "rows": [["1"]]},
    ])
    passed, _ = compare(str(exp_p), str(res_p), TEST, 6)
    assert passed is True


def test_multiple_tests_in_file_compares_correct_test(tmp_path):
    exp_p = tmp_path / "test.exp"
    res_p = tmp_path / "test.res"

    # Write two test blocks — second one has different data
    write_result_file(exp_p, [{"stmt": "SELECT id;", "cols": ["id"], "rows": [["1"]]}],
                      test_name="test_one")
    write_result_file(exp_p, [{"stmt": "SELECT id;", "cols": ["id"], "rows": [["99"]]}],
                      test_name="test_two")
    exp_p.write_text(
        "-- TEST: test_one\n-- STATEMENT 1: SELECT id;\nid\n1\n\n"
        "-- TEST: test_two\n-- STATEMENT 1: SELECT id;\nid\n99\n\n"
    )
    res_p.write_text(
        "-- TEST: test_one\n-- STATEMENT 1: SELECT id;\nid\n1\n\n"
        "-- TEST: test_two\n-- STATEMENT 1: SELECT id;\nid\n99\n\n"
    )

    assert compare(str(exp_p), str(res_p), "test_one", 6)[0] is True
    assert compare(str(exp_p), str(res_p), "test_two", 6)[0] is True


# ---------------------------------------------------------------------------
# _parse_result_file backward compat (no -- TEST: header needed)
# ---------------------------------------------------------------------------

def test_parse_result_file_missing_returns_none(tmp_path):
    cols, rows = _parse_result_file("/nonexistent/path.exp")
    assert cols is None
    assert rows == []


def test_parse_result_file_extracts_last_select(tmp_path):
    p = tmp_path / "f.res"
    # write without TEST wrapper — backward compat
    p.write_text(
        "-- STATEMENT 1: SELECT 1;\na\nfirst\n\n"
        "-- STATEMENT 2: SELECT 2;\nb\nsecond\n\n"
    )
    cols, rows = _parse_result_file(str(p))
    assert cols == ["b"]
    assert rows == [["second"]]


def test_parse_result_file_header_only_returns_empty_rows(tmp_path):
    p = tmp_path / "f.res"
    p.write_text("-- STATEMENT 1: SELECT id FROM t;\nid\n\n")
    cols, rows = _parse_result_file(str(p))
    assert cols == ["id"]
    assert rows == []
