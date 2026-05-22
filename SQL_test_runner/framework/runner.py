import csv
import glob
import os
import time
from typing import List, Optional

from .comparator import compare, _parse_test_blocks
from .executor import ServerCrashError, connect, initialize_result_file, run_sql, write_result
from .logger import logger
from .parser import TestCase, TestSuite, parse_file


def _exp_path(base_dir: str, suite: TestSuite) -> str:
    sql_name = os.path.splitext(os.path.basename(suite.file_path))[0]
    return os.path.join(base_dir, "expected", f"{sql_name}.exp")


def _res_path(base_dir: str, suite: TestSuite) -> str:
    sql_name = os.path.splitext(os.path.basename(suite.file_path))[0]
    return os.path.join(base_dir, "result", f"{sql_name}.res")


def _test_block_exists(exp_path: str, test_name: str) -> bool:
    """Return True if the test's block is already present in the .exp file."""
    blocks = _parse_test_blocks(exp_path)
    return blocks is not None and test_name in blocks


def _append_to_exp(exp_path: str, content: str):
    """Append a test block to the .exp file (auto-generation on first run)."""
    os.makedirs(os.path.dirname(exp_path), exist_ok=True)
    with open(exp_path, "a") as f:
        f.write(content)


def _check_duplicate_names(suite: TestSuite) -> None:
    """Raise ValueError if any test name appears more than once in the suite."""
    seen = set()
    duplicates = []
    for test in suite.tests:
        if test.name in seen and test.name not in duplicates:
            duplicates.append(test.name)
        seen.add(test.name)
    if duplicates:
        raise ValueError(
            f"Duplicate test name(s) in {suite.file_path}: {duplicates}. "
            f"Each test name must be unique within a file."
        )


def run_suite(suite: TestSuite, config: dict, base_dir: str,
              filter_test: Optional[str] = None,
              filter_tag: Optional[str] = None,
              dry_run: bool = False,
              no_compare: bool = False) -> List[dict]:
    results = []
    suite_name = os.path.splitext(os.path.basename(suite.file_path))[0]

    _check_duplicate_names(suite)

    if dry_run:
        for test in suite.tests:
            if filter_test and test.name != filter_test:
                continue
            if filter_tag and filter_tag not in test.tags:
                continue
            status = "SKIP" if test.skip else "PASS"
            msg = f"[dry-run] skip reason: {test.skip}" if test.skip else "[dry-run] ok"
            results.append({"suite": suite_name, "test": test.name, "status": status, "message": msg, "duration": 0})
        return results

    exp_p = _exp_path(base_dir, suite)
    res_p = _res_path(base_dir, suite)

    try:
        conn = connect(config)
    except ServerCrashError as e:
        logger.error(f"[SERVER CRASH] {e}")
        raise

    initialize_result_file(res_p)

    try:
        if suite.suite_setup:
            logger.info(f"[SUITE_SETUP] {suite_name}")
            run_sql(conn, suite.suite_setup)

        for test in suite.tests:
            if filter_test and test.name != filter_test:
                continue
            if filter_tag and filter_tag not in test.tags:
                continue

            if test.skip:
                msg = f"Skipped: {test.skip}"
                results.append({"suite": suite_name, "test": test.name, "status": "SKIP", "message": msg, "duration": 0})
                continue

            if not test.query:
                msg = "No QUERY marker found"
                results.append({"suite": suite_name, "test": test.name, "status": "ERROR", "message": msg, "duration": 0})
                continue

            start = time.time()
            content = None
            exec_error = None

            try:
                if test.setup:
                    run_sql(conn, test.setup)
                try:
                    statement_results = run_sql(conn, test.query)
                    content = write_result(res_p, test.name, statement_results, config["float_precision"])
                except ServerCrashError:
                    raise
                except Exception as e:
                    exec_error = e
                finally:
                    if test.teardown:
                        try:
                            run_sql(conn, test.teardown)
                        except ServerCrashError:
                            raise
                        except Exception as td_err:
                            logger.error(f"[TEARDOWN ERROR] {suite_name}::{test.name}: {td_err}")
            except ServerCrashError:
                raise
            except Exception as e:
                exec_error = e

            if exec_error is not None:
                duration = time.time() - start
                msg = str(exec_error)
                results.append({"suite": suite_name, "test": test.name, "status": "ERROR", "message": msg, "duration": duration})
                continue

            duration = time.time() - start

            if no_compare or test.no_compare:
                results.append({"suite": suite_name, "test": test.name, "status": "PASS", "message": "Comparison skipped", "duration": duration})
                continue

            if not _test_block_exists(exp_p, test.name):
                _append_to_exp(exp_p, content)
                msg = f"Expected block auto-generated in: {exp_p}"
                results.append({"suite": suite_name, "test": test.name, "status": "PENDING", "message": msg, "duration": duration})
                continue

            passed, msg = compare(exp_p, res_p, test.name, config["float_precision"])
            status = "PASS" if passed else "FAIL"
            results.append({"suite": suite_name, "test": test.name, "status": status, "message": msg, "duration": duration})

        if suite.suite_teardown:
            logger.info(f"[SUITE_TEARDOWN] {suite_name}")
            run_sql(conn, suite.suite_teardown)

    except ServerCrashError:
        logger.error("[SERVER CRASH] MySQL server is unreachable. Stopping test run.")
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return results


def _conftest_files(setup_dir: str) -> List[str]:
    """Return all .sql files in setup_dir sorted alphabetically."""
    pattern = os.path.join(setup_dir, "*.sql")
    return sorted(glob.glob(pattern))


def run_global_setup(config: dict) -> None:
    """Run SUITE_SETUP blocks from all conftest files in alphabetical order."""
    setup_dir = config.get("global_setup_dir")
    if not setup_dir or not os.path.isdir(setup_dir):
        return

    files = _conftest_files(setup_dir)
    if not files:
        return

    logger.info(f"[GLOBAL_SETUP] Running {len(files)} conftest file(s) from {setup_dir}")
    conn = connect(config)
    try:
        for file_path in files:
            suite = parse_file(file_path)
            if suite.suite_setup:
                label = os.path.basename(file_path)
                logger.info(f"  [GLOBAL_SETUP] {label}")
                run_sql(conn, suite.suite_setup)
    except ServerCrashError:
        logger.error("[SERVER CRASH] Global setup failed — MySQL server unreachable.")
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_global_teardown(config: dict) -> None:
    """Run SUITE_TEARDOWN blocks from all conftest files in reverse order."""
    setup_dir = config.get("global_setup_dir")
    if not setup_dir or not os.path.isdir(setup_dir):
        return

    files = _conftest_files(setup_dir)
    if not files:
        return

    logger.info(f"[GLOBAL_TEARDOWN] Running {len(files)} conftest file(s) in reverse order")
    conn = connect(config)
    try:
        for file_path in reversed(files):
            suite = parse_file(file_path)
            if suite.suite_teardown:
                label = os.path.basename(file_path)
                logger.info(f"  [GLOBAL_TEARDOWN] {label}")
                try:
                    run_sql(conn, suite.suite_teardown)
                except ServerCrashError:
                    logger.error("[SERVER CRASH] Global teardown failed — MySQL server unreachable.")
                    raise
                except Exception as e:
                    logger.error(f"  [GLOBAL_TEARDOWN ERROR] {label}: {e} — continuing")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_file(args) -> List[dict]:
    """Entry point for multiprocessing — unpacks args tuple."""
    file_path, config, base_dir, filter_test, filter_tag, dry_run, no_compare = args
    try:
        suite = parse_file(file_path)
        return run_suite(suite, config, base_dir, filter_test, filter_tag, dry_run, no_compare)
    except ServerCrashError:
        raise
    except Exception as e:
        suite_name = os.path.splitext(os.path.basename(file_path))[0]
        logger.error(f"[ERROR] Failed to process {file_path}: {e}")
        return [{"suite": suite_name, "test": "__file__", "status": "ERROR", "message": str(e), "duration": 0}]
