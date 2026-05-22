import pytest
from framework.parser import parse_file, TestCase, TestSuite


def write_sql(tmp_path, content: str):
    f = tmp_path / "test.sql"
    f.write_text(content)
    return str(f)


# ---------------------------------------------------------------------------
# Empty / minimal files
# ---------------------------------------------------------------------------

def test_empty_file_returns_empty_suite(tmp_path):
    path = write_sql(tmp_path, "")
    suite = parse_file(path)
    assert suite.tests == []
    assert suite.suite_setup == ""
    assert suite.suite_teardown == ""


def test_file_with_only_comments_returns_empty_suite(tmp_path):
    path = write_sql(tmp_path, "-- just a comment\n-- another comment\n")
    suite = parse_file(path)
    assert suite.tests == []


# ---------------------------------------------------------------------------
# Single test basics
# ---------------------------------------------------------------------------

def test_single_test_name_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert len(suite.tests) == 1
    assert suite.tests[0].name == "my_test"


def test_single_test_query_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert suite.tests[0].query == "SELECT 1;"


def test_test_with_no_query_marker_has_empty_query(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: no_query
    """))
    suite = parse_file(path)
    assert suite.tests[0].query == ""


# ---------------------------------------------------------------------------
# Multiple tests
# ---------------------------------------------------------------------------

def test_multiple_tests_all_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: first
        -- QUERY:
        SELECT 1;

        -- TEST: second
        -- QUERY:
        SELECT 2;

        -- TEST: third
        -- QUERY:
        SELECT 3;
    """))
    suite = parse_file(path)
    assert len(suite.tests) == 3
    assert [t.name for t in suite.tests] == ["first", "second", "third"]


def test_multiple_tests_queries_are_independent(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: alpha
        -- QUERY:
        SELECT 'alpha';

        -- TEST: beta
        -- QUERY:
        SELECT 'beta';
    """))
    suite = parse_file(path)
    assert "alpha" in suite.tests[0].query
    assert "beta" in suite.tests[1].query


# ---------------------------------------------------------------------------
# Suite-level setup / teardown
# ---------------------------------------------------------------------------

def test_suite_setup_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- SUITE_SETUP:
        CREATE TABLE t (id INT);

        -- TEST: my_test
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert "CREATE TABLE t" in suite.suite_setup


def test_suite_teardown_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- QUERY:
        SELECT 1;

        -- SUITE_TEARDOWN:
        DROP TABLE t;
    """))
    suite = parse_file(path)
    assert "DROP TABLE t" in suite.suite_teardown


def test_suite_setup_not_included_in_tests(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- SUITE_SETUP:
        CREATE TABLE t (id INT);

        -- TEST: my_test
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert len(suite.tests) == 1


# ---------------------------------------------------------------------------
# Test-level setup / teardown
# ---------------------------------------------------------------------------

def test_test_setup_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- SETUP:
        INSERT INTO t VALUES (1);
        -- QUERY:
        SELECT * FROM t;
    """))
    suite = parse_file(path)
    assert "INSERT INTO t" in suite.tests[0].setup


def test_test_teardown_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- QUERY:
        SELECT * FROM t;
        -- TEARDOWN:
        DELETE FROM t;
    """))
    suite = parse_file(path)
    assert "DELETE FROM t" in suite.tests[0].teardown


def test_setup_and_teardown_are_test_scoped(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: first
        -- SETUP:
        INSERT INTO t VALUES (1);
        -- QUERY:
        SELECT * FROM t;
        -- TEARDOWN:
        DELETE FROM t;

        -- TEST: second
        -- QUERY:
        SELECT 2;
    """))
    suite = parse_file(path)
    assert suite.tests[0].setup != ""
    assert suite.tests[1].setup == ""
    assert suite.tests[1].teardown == ""


# ---------------------------------------------------------------------------
# Multiline SQL
# ---------------------------------------------------------------------------

def test_multiline_query_preserved(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: multiline
        -- QUERY:
        SELECT
            customer_id,
            COUNT(*) AS cnt
        FROM orders
        GROUP BY customer_id;
    """))
    suite = parse_file(path)
    q = suite.tests[0].query
    assert "customer_id" in q
    assert "COUNT(*)" in q
    assert "GROUP BY" in q


def test_multiline_suite_setup_preserved(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- SUITE_SETUP:
        CREATE TABLE orders (
            id INT PRIMARY KEY,
            customer_id INT
        );

        -- TEST: t
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert "CREATE TABLE orders" in suite.suite_setup
    assert "customer_id INT" in suite.suite_setup


# ---------------------------------------------------------------------------
# TAGS
# ---------------------------------------------------------------------------

def test_single_tag_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- TAGS: smoke
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert suite.tests[0].tags == ["smoke"]


def test_multiple_tags_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- TAGS: smoke, regression, slow
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert suite.tests[0].tags == ["smoke", "regression", "slow"]


def test_tags_with_extra_spaces_stripped(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- TAGS:  smoke ,  regression
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert suite.tests[0].tags == ["smoke", "regression"]


def test_tags_before_any_test_are_ignored(tmp_path):
    # TAGS with no preceding TEST marker should not raise
    path = write_sql(tmp_path, dedent("""
        -- TAGS: orphan
        -- TEST: my_test
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert suite.tests[0].tags == []


def test_tags_are_test_scoped(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: first
        -- TAGS: smoke
        -- QUERY:
        SELECT 1;

        -- TEST: second
        -- QUERY:
        SELECT 2;
    """))
    suite = parse_file(path)
    assert suite.tests[0].tags == ["smoke"]
    assert suite.tests[1].tags == []


# ---------------------------------------------------------------------------
# SKIP
# ---------------------------------------------------------------------------

def test_skip_with_reason(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- SKIP: not yet deployed
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert suite.tests[0].skip == "not yet deployed"


def test_skip_without_reason_defaults_to_skipped(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- SKIP:
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert suite.tests[0].skip == "skipped"


def test_unskipped_test_has_none_skip(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert suite.tests[0].skip is None


# ---------------------------------------------------------------------------
# NO_COMPARE
# ---------------------------------------------------------------------------

def test_no_compare_sets_flag(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- NO_COMPARE:
        -- QUERY:
        INSERT INTO t VALUES (1);
    """))
    suite = parse_file(path)
    assert suite.tests[0].no_compare is True


def test_no_compare_false_by_default(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- TEST: my_test
        -- QUERY:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert suite.tests[0].no_compare is False


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------

def test_lowercase_markers_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- test: lower_test
        -- query:
        SELECT 1;
    """))
    suite = parse_file(path)
    assert len(suite.tests) == 1
    assert suite.tests[0].name == "lower_test"


def test_mixed_case_markers_parsed(tmp_path):
    path = write_sql(tmp_path, dedent("""
        -- Test: mixed_test
        -- Query:
        SELECT 1;
        -- Tags: Smoke
        -- Skip: Not Ready
    """))
    suite = parse_file(path)
    assert suite.tests[0].name == "mixed_test"
    assert suite.tests[0].tags == ["Smoke"]
    assert suite.tests[0].skip == "Not Ready"


# ---------------------------------------------------------------------------
# File path stored on suite
# ---------------------------------------------------------------------------

def test_suite_stores_file_path(tmp_path):
    path = write_sql(tmp_path, "")
    suite = parse_file(path)
    assert suite.file_path == path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def dedent(text: str) -> str:
    """Strip leading newline and common indentation from triple-quoted strings."""
    import textwrap
    return textwrap.dedent(text).lstrip("\n")
