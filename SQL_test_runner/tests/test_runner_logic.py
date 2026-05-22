import pytest
from framework.parser import TestCase, TestSuite
from framework.runner import _check_duplicate_names


def make_suite(names):
    """Build a TestSuite with tests named by the given list."""
    tests = [TestCase(name=n, query="SELECT 1;") for n in names]
    return TestSuite(file_path="fake_test.sql", tests=tests)


def test_unique_names_passes():
    suite = make_suite(["total_orders", "orders_by_date", "orders_by_customer"])
    _check_duplicate_names(suite)  # should not raise


def test_single_test_passes():
    suite = make_suite(["total_orders"])
    _check_duplicate_names(suite)


def test_empty_suite_passes():
    suite = make_suite([])
    _check_duplicate_names(suite)


def test_duplicate_name_raises():
    suite = make_suite(["total_orders", "orders_by_date", "total_orders"])
    with pytest.raises(ValueError) as exc:
        _check_duplicate_names(suite)
    assert "total_orders" in str(exc.value)
    assert "Duplicate" in str(exc.value)


def test_multiple_duplicates_all_reported():
    suite = make_suite(["a", "b", "a", "c", "b"])
    with pytest.raises(ValueError) as exc:
        _check_duplicate_names(suite)
    msg = str(exc.value)
    assert "a" in msg
    assert "b" in msg


def test_duplicate_reported_once_not_twice():
    # "a" appears 3 times — should appear once in the duplicates list
    suite = make_suite(["a", "a", "a"])
    with pytest.raises(ValueError) as exc:
        _check_duplicate_names(suite)
    assert str(exc.value).count("a") == str(exc.value).count("a")
    # duplicates list should contain "a" exactly once
    import ast
    msg = str(exc.value)
    assert msg.count("'a'") == 1
