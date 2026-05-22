#!/usr/bin/env python3
import argparse
import glob
import os
import sys
from multiprocessing import Pool

from framework.config import load_config
from framework.executor import ServerCrashError
from framework.logger import setup_logger, logger
from framework.reporter import generate_html, generate_json, print_file_result, print_summary
from framework.runner import run_file, run_global_setup, run_global_teardown


def collect_sql_files(base_dir: str, specific_file: str = None) -> list:
    if specific_file:
        return [specific_file]
    pattern = os.path.join(base_dir, "test", "*.sql")
    return sorted(glob.glob(pattern))


def _failed_suites(results: list) -> set:
    """Return suite names that have at least one FAIL or ERROR result."""
    return {
        r["suite"] for r in results
        if r["status"] in ("FAIL", "ERROR")
    }


def _remove_suite_results(results: list, suites: set) -> list:
    """Return results with all entries for the given suites removed."""
    return [r for r in results if r["suite"] not in suites]


def main():
    parser = argparse.ArgumentParser(
        prog="sqltest",
        description="SQL Test Framework — execute SQL tests and compare against expected results.",
    )
    parser.add_argument("--config", required=True, help="Path to config.ini")
    parser.add_argument("--file", help="Run a specific SQL test file")
    parser.add_argument("--test", help="Run a specific test by name within a file")
    parser.add_argument("--tag", help="Run only tests with this tag")
    parser.add_argument("--report", choices=["html", "json"], help="Generate an output report")
    parser.add_argument("--report-output", default="report", help="Output path for the report (without extension)")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel worker processes (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate test files without executing SQL")
    parser.add_argument("--no-compare", action="store_true", help="Run all tests and write result files but skip comparison (always PASS if no SQL error)")
    parser.add_argument("--retry", action="store_true", help="Re-run all files with at least one FAIL or ERROR after the first pass")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(args.config))
    setup_logger(os.path.join(base_dir, "logs"))

    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    sql_files = collect_sql_files(base_dir, args.file)
    if not sql_files:
        logger.error("No SQL test files found.")
        sys.exit(1)

    logger.info(f"Discovered {len(sql_files)} test file(s). Workers: {args.workers}")

    task_args = [
        (f, config, base_dir, args.test, args.tag, args.dry_run, args.no_compare)
        for f in sql_files
    ]

    all_results = []

    def _print_and_collect(file_results):
        print_file_result(file_results)
        all_results.extend(file_results)

    # global setup runs sequentially on the main process before any worker starts
    if not args.dry_run:
        try:
            run_global_setup(config)
        except ServerCrashError as e:
            logger.error(f"[SERVER CRASH] {e}. Aborting — global setup failed.")
            sys.exit(2)
        except Exception as e:
            logger.error(f"[GLOBAL_SETUP ERROR] {e}. Aborting — global setup failed.")
            sys.exit(1)

    try:
        try:
            # ── first pass ────────────────────────────────────────────────
            if args.workers > 1:
                with Pool(processes=args.workers) as pool:
                    for file_results in pool.imap_unordered(run_file, task_args):
                        _print_and_collect(file_results)
            else:
                for task in task_args:
                    _print_and_collect(run_file(task))

            # ── retry pass ────────────────────────────────────────────────
            if args.retry and not args.dry_run:
                failed = _failed_suites(all_results)
                if failed:
                    logger.info(f"\n[RETRY] Re-running {len(failed)} failed file(s): {sorted(failed)}")
                    # remove first-pass results for failed files
                    all_results[:] = _remove_suite_results(all_results, failed)
                    # rebuild task args for failed files only
                    retry_tasks = [
                        t for t in task_args
                        if os.path.splitext(os.path.basename(t[0]))[0] in failed
                    ]
                    if args.workers > 1:
                        with Pool(processes=args.workers) as pool:
                            for file_results in pool.imap_unordered(run_file, retry_tasks):
                                _print_and_collect(file_results)
                    else:
                        for task in retry_tasks:
                            _print_and_collect(run_file(task))
                else:
                    logger.info("[RETRY] No failed files to retry.")

        except ServerCrashError as e:
            logger.error(f"[SERVER CRASH] {e}. Aborting test run.")
            print_summary(all_results)
            sys.exit(2)
    finally:
        # global teardown always runs — even if tests crash or server goes down
        if not args.dry_run:
            try:
                run_global_teardown(config)
            except ServerCrashError:
                logger.error("[SERVER CRASH] Global teardown failed — manual cleanup may be required.")
            except Exception as e:
                logger.error(f"[GLOBAL_TEARDOWN ERROR] {e} — manual cleanup may be required.")

    print_summary(all_results)

    if args.report == "json":
        generate_json(all_results, f"{args.report_output}.json")
    elif args.report == "html":
        generate_html(all_results, f"{args.report_output}.html")

    failures = sum(1 for r in all_results if r["status"] in ("FAIL", "ERROR"))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
