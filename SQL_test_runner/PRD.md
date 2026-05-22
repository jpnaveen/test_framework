# PRD: SQL Test Framework

## Problem Statement

Data engineers and QA teams working with MySQL have no standardised way to test SQL queries. Verifying that a query returns the correct result requires manually running queries, eyeballing output, and keeping mental notes about what changed. This process does not scale, is not repeatable, and leaves no audit trail. When a schema changes or business logic is updated, there is no automated safety net to catch regressions before they reach production.

---

## Solution

A Python-based CLI test framework that executes SQL test files against a MySQL database, captures query results as CSV files, compares them against human-authored expected output files, and reports each test as PASS, FAIL, SKIP, PENDING, or ERROR. The framework supports parallel execution across multiple processes, suite and test-level setup/teardown, tag-based filtering, dry-run validation, and optional HTML/JSON reporting.

---

## User Stories

1. As a data engineer, I want to write SQL tests in plain `.sql` files, so that I can author and review tests without learning a new language or DSL.
2. As a data engineer, I want to define multiple tests in a single SQL file, so that related tests for a feature or table stay together.
3. As a data engineer, I want to use comment-based markers to declare tests, so that my test files remain valid SQL and can be opened in any SQL editor.
4. As a data engineer, I want to define suite-level setup and teardown SQL, so that I can create and destroy shared database objects once per file without repeating myself.
5. As a data engineer, I want to define test-level setup and teardown SQL, so that each test starts with a clean, isolated dataset.
6. As a data engineer, I want query results to be compared against an expected CSV file, so that I have a clear, auditable record of what the correct output looks like.
7. As a data engineer, I want expected and result files stored in separate sibling folders, so that test logic, expected data, and actual output are clearly separated.
8. As a data engineer, I want row comparison to be unordered by default, so that tests do not produce false failures when SQL returns rows in a different order on different runs.
9. As a data engineer, I want column order to be enforced strictly, so that a query that reorders columns is caught as a failure.
10. As a data engineer, I want NULL values to be represented as the string `NULL` in expected and result files, so that NULL and empty string are never ambiguous.
11. As a data engineer, I want float and decimal values compared with a configurable tolerance, so that trivial floating-point representation differences do not cause false failures.
12. As a data engineer, I want the framework to auto-generate an expected file the first time a test runs, so that I do not have to manually write expected output for every test.
13. As a data engineer, I want auto-generated expected files to be marked as PENDING, so that I know to review and approve them before treating them as authoritative.
14. As a data engineer, I want a zero-row result to be a valid expected outcome, so that I can test queries that are supposed to return no data.
15. As a data engineer, I want to skip a test using a marker in the SQL file, so that I can disable a test temporarily without deleting it.
16. As a data engineer, I want to attach tags to tests, so that I can group them by category (e.g. smoke, regression, slow).
17. As a data engineer, I want to filter test runs by tag, so that I can run only a subset of tests relevant to my current work.
18. As a data engineer, I want to run a single test by name, so that I can iterate quickly on one failing test without running the full suite.
19. As a data engineer, I want to run a single SQL test file, so that I can focus a run on one feature area.
20. As a data engineer, I want database connection details stored in a config file, so that I do not hardcode credentials in test files.
21. As a data engineer, I want test results printed to the terminal in real time, so that I can see progress as the suite runs.
22. As a data engineer, I want all test failures summarised at the end of a run, so that I can see every failure in one place without scrolling through the full log.
23. As a data engineer, I want each test to show its execution duration, so that I can identify slow queries.
24. As a data engineer, I want to generate an HTML report, so that I can share results with non-technical stakeholders.
25. As a data engineer, I want to generate a JSON report, so that CI/CD pipelines can consume test results programmatically.
26. As a data engineer, I want test output logged to a timestamped log file, so that I have a permanent record of each run.
27. As a data engineer, I want individual test SQL errors to fail only that test and continue the suite, so that one bad query does not block all other tests from running.
28. As a data engineer, I want the suite to stop immediately if the MySQL server becomes unreachable, so that I do not waste time running tests against a crashed database.
29. As a data engineer, I want server crash events logged prominently with a clear error message, so that I know exactly when and why a run was aborted.
30. As a data engineer, I want to run tests in parallel across multiple processes, so that large test suites complete faster.
31. As a data engineer, I want parallelism to operate at the file level (one process per SQL file), so that suite-level setup and teardown always run in the same process as their tests.
32. As a data engineer, I want to control the number of worker processes from the CLI, so that I can tune parallelism for my environment.
33. As a data engineer, I want a dry-run mode that parses and validates test files without executing SQL, so that I can catch malformed markers and missing config before a full run.
34. As a data engineer, I want to run the test suite without comparing results using a CLI flag, so that I can use the same test files for coverage runs or memory-leak testing without modifying them.
35. As a data engineer, I want the `--no-compare` flag to still write result files, so that I can inspect actual output after a no-compare run if needed.
36. As a QA engineer, I want the framework to exit with a non-zero code when tests fail, so that CI pipelines automatically detect failures.
37. As a QA engineer, I want a distinct exit code when the run is aborted due to a server crash, so that CI pipelines can distinguish a test failure from an infrastructure failure.
38. As a team lead, I want all design decisions documented in a DESIGN.md file, so that new team members can understand the framework's architecture quickly.
39. As a data engineer, I want parallel test runs to produce clean, non-interleaved terminal output, so that I can read results clearly regardless of how many workers are running.
40. As a data engineer, I want a `-- QUERY:` block to support multiple SQL statements, so that I can set variables, seed intermediate data, and run the final SELECT all within one test.
41. As a data engineer, I want every statement's result written to the `.res` file, so that I can understand what each step did when debugging a failure.
42. As a data engineer, I want the `.exp` and `.res` files to use the same format, so that I can diff them side by side in any text editor without mental translation.
43. As a data engineer, I want the terminal to show one line per SQL file (not per test), so that I get a clean high-level view of which files passed or failed without noise.
44. As a data engineer, I want the end-of-run summary to count files rather than individual tests, so that I can immediately see the scope of failure across my test suite.
45. As a data engineer, I want the summary to list every individual failing test name under its file, so that I know exactly which tests to fix without opening each file.
46. As a data engineer, I want to define global setup SQL that runs once before all test files, so that shared schema and reference data are available to every test without duplicating setup in each file.
47. As a data engineer, I want to split global setup across multiple SQL files, so that schema creation, reference data, and seed data are each in their own focused file rather than one large file.
48. As a data engineer, I want global setup files to run in alphabetical order, so that I can control dependencies between files using numeric prefixes.
49. As a data engineer, I want global teardown to run in reverse order, so that child data is deleted before parent tables are dropped, respecting foreign key constraints.
50. As a data engineer, I want global teardown to always run even if tests crash, so that the database is left in a clean state regardless of test outcome.
51. As a data engineer, I want the global setup directory configured in `config.ini`, so that the path is version-controlled and does not need to be specified on every invocation.
52. As a data engineer, I want a `--retry` flag that re-runs all failed files after the first pass, so that transient failures do not require manually re-running the entire suite.
53. As a data engineer, I want the retry to re-run the entire file (not just the failed test), so that `SUITE_SETUP` guarantees a clean database state before the retry executes.
54. As a data engineer, I want retry results to replace first-pass results in the final summary, so that the reported outcome reflects the last known state of each file.
55. As a data engineer, I want only FAIL and ERROR files retried, so that passing, skipped, and pending files are not re-executed unnecessarily.
56. As a data engineer, I want all SQL statements in a test compared against expected output — not just the final SELECT — so that a wrong INSERT count or missing SET variable is caught immediately.
57. As a data engineer, I want `ROWS AFFECTED` counts compared between `.exp` and `.res`, so that a DML statement that updates the wrong number of rows is reported as a failure.
58. As a data engineer, I want all statement mismatches reported together in one failure message, so that I can see the full picture of what went wrong without re-running the test multiple times.
59. As a data engineer, I want one expected file and one result file per SQL test file, so that the relationship between files is a clean 1:1:1 — one `.sql`, one `.exp`, one `.res`.
60. As a data engineer, I want all tests' results written to a single `.res` file per SQL file, so that I can review all test outputs for a feature in one place.
61. As a data engineer, I want the `.exp` file to be appendable — new tests add their block without touching existing approved blocks, so that adding a new test does not invalidate the expected output for existing tests.
62. As a data engineer, I want NULL database values written as the string `NULL` in result files, so that NULL and empty string are never ambiguous during comparison.
63. As a data engineer, I want float and decimal values written to a configurable number of decimal places, so that trivial floating-point representation differences do not cause false failures.
64. As a data engineer, I want a DML statement that affects zero rows written as `-- NO RESULT` rather than `-- ROWS AFFECTED: 0`, so that the output is consistent with SET and other no-result statements.
65. As a data engineer, I want a `-- QUERY:` block to contain multiple SELECT statements, so that a single test can verify several related result sets without creating multiple tests.
66. As a data engineer, I want each SELECT in a multi-SELECT query block written as its own numbered statement block in the result file, so that I can see exactly which SELECT produced which output.
67. As a data engineer, I want all SELECT blocks in a multi-SELECT test compared pairwise against the expected file, so that a failure in any SELECT is caught and reported with its statement number.
68. As a data engineer, I want a statement count mismatch to fail immediately, so that adding or removing a SELECT from the query forces a deliberate update to the expected file.
69. As a data engineer, I want the framework to detect duplicate test names within a file and raise an error immediately, so that I am not silently given wrong comparison results due to overwritten result blocks.
70. As a data engineer, I want duplicate name detection to run before any SQL executes, so that `--dry-run` also catches the problem without requiring a database connection.
71. As a data engineer, I want `TEARDOWN` to always run even when the `QUERY` throws a SQL error, so that data inserted by `SETUP` is cleaned up and does not pollute subsequent tests.
72. As a data engineer, I want `TEARDOWN` errors logged without masking the original query error, so that I see the real failure reason in the test report.
73. As a data engineer, I want MySQL `DECIMAL` column values written with the configured float precision, so that decimal values are formatted consistently regardless of MySQL's internal representation.
74. As a data engineer, I want `--` comments with semicolons inside a `QUERY` block handled correctly, so that comment text is never treated as a SQL statement separator.
75. As a data engineer, I want result files to use consistent `\n` line endings on all platforms, so that `.exp` and `.res` files can be diffed cleanly across operating systems.
76. As a data engineer, I want the framework to work with both the pure Python and C extension MySQL cursor, so that it runs correctly regardless of which `mysql-connector-python` build is installed.
77. As a data engineer, I want leftover result bytes from stored procedure calls automatically discarded before the next SQL executes, so that `Unread result found` errors never occur.
78. As a data engineer, I want a MySQL error in one global teardown file to be logged and skipped, so that remaining teardown files always run and tables are not left in the database.
79. As a data engineer, I want the framework to exit cleanly with a log message when global setup or teardown fails, so that I never see a raw Python traceback in the terminal.
80. As a data engineer, I want marker keywords to require a colon (e.g. `-- TEST: name`), so that regular comments containing words like `test` or `setup` are never mistakenly parsed as markers.

---

## Implementation Decisions

### Module Breakdown

The framework is decomposed into six deep modules, each with a single responsibility:

- **Parser** — reads a `.sql` file and produces a `TestSuite` object containing a list of `TestCase` objects. Has no knowledge of the database or file system beyond reading the input file. Pure, deterministic, and fully testable in isolation. The MARKER regex requires a literal colon after every keyword (`-- TEST: name` matches; `-- Tests that...` does not) — preventing regular comments from being parsed as markers.

- **Executor** — exposes four functions: `connect(config)` returns a MySQL connection (with `use_pure=True` and `consume_results=True` — the latter auto-discards leftover socket bytes from stored procedure calls before each new execute, preventing `Unread result found` errors) or raises `ServerCrashError`; `initialize_result_file(path)` clears the suite-level `.res` file once before any test runs; `run_sql(conn, sql)` splits SQL via `_split_statements()` (respects single/double quotes, `--` line comments, and `BEGIN...END` block depth), executes each statement with a fresh cursor per statement (closed in `finally`), drains all result sets via `cursor.nextset()`, and returns a list of result dicts; `write_result(path, test_name, results, precision)` formats `float` and `decimal.Decimal` values with `float_precision` decimal places, uses `csv.writer(lineterminator="\n")` for consistent line endings, appends one `-- TEST:` block to the `.res` file, and returns the text written for PENDING auto-generation. Distinguishes recoverable query errors (`MySQLError`) from unrecoverable connection loss (`ServerCrashError`).

- **Comparator** — reads `.exp` and `.res` files using `_parse_test_blocks` (returns `{test_name: [statement_blocks]}`), extracts the specific test's blocks by name, compares every statement block pairwise (`no_result` type check, `dml` row count, `select` rows and columns), collects all mismatches, and returns a combined pass/fail verdict with per-statement error messages. Applies unordered row matching, position-based column matching, NULL normalisation, and float tolerance. Has no knowledge of the database or test structure.

- **Runner** — exposes four functions: `run_suite` orchestrates a single file (`_check_duplicate_names` → connect → initialize `.res` → SUITE_SETUP → per-test SETUP/QUERY/TEARDOWN/compare → SUITE_TEARDOWN → close connection) and returns `List[dict]` results; `run_file` is the picklable multiprocessing entry point; `run_global_setup` and `run_global_teardown` handle conftest files — teardown wraps each file in its own `try/except` so a MySQL error in one file logs a warning and continues to the next, ensuring all teardown files execute and tables are not left in the database. `_check_duplicate_names` raises `ValueError` before any SQL runs. `TEARDOWN` is placed in a `finally` block so it always executes — even when QUERY throws an error — preventing dirty data from leaking to subsequent tests; teardown errors are logged without masking the original query error. Two-level error handling distinguishes `ServerCrashError` (re-raise, stop everything) from SQL errors (record `ERROR`, continue). PENDING auto-generation appends only the missing test's block to `.exp` via the content returned by `write_result`.

- **Reporter** — prints one line per file to the terminal (file-level status derived from all its test results), prints a file-level count summary at the end, and generates test-level HTML/JSON report files. Always called from the main process — never from a worker — so it is the sole writer to the terminal regardless of worker count.

- **Logger** — configures a shared `logging.Logger` instance that writes to both terminal (INFO level) and a timestamped log file (DEBUG level). Initialised once at startup.

### File Naming Convention

Expected and result files are named `<sql_filename>.exp` and `<sql_filename>.res` — one file per SQL test file. The 1:1:1 relationship (`orders_test.sql` → `orders_test.exp` → `orders_test.res`) removes the need for a double-underscore naming convention and makes the connection between files self-evident.

### Marker Syntax

All markers follow the pattern `-- KEYWORD: value` and are parsed case-insensitively. Supported markers:

| Marker | Scope |
|--------|-------|
| `SUITE_SETUP` / `SUITE_TEARDOWN` | File |
| `TEST`, `TAGS`, `SKIP`, `NO_COMPARE` | Test (metadata) |
| `SETUP`, `QUERY`, `TEARDOWN` | Test (SQL blocks) |

### Unified File Format

Both `.exp` and `.res` files use the same format. Each test gets a `-- TEST: name` block; within each test block, every SQL statement produces a `-- STATEMENT N:` block. A `-- QUERY:` block may contain any mix of statement types — SET variables, DML, and multiple SELECTs — all written in execution order:

```
-- TEST: orders_summary
-- STATEMENT 1: SELECT COUNT(*) AS total_orders FROM orders;
total_orders
3

-- STATEMENT 2: SELECT customer_id, COUNT(*) AS order_count FROM orders GROUP B
customer_id,order_count
1,2
2,1

-- STATEMENT 3: SELECT MIN(amount) AS min_amt, MAX(amount) AS max_amt, SUM(amou
min_amt,max_amt,total_amt
100.00,200.00,450.000000

-- TEST: orders_with_variables
-- STATEMENT 1: SET @threshold = 150.00;
-- NO RESULT

-- STATEMENT 2: SELECT COUNT(*) AS orders_above_threshold FROM orders WHERE amo
orders_above_threshold
2

-- STATEMENT 3: SELECT customer_id, SUM(amount) AS total FROM orders WHERE amou
customer_id,total
1,200.00
2,150.00

```

The `.res` file is initialised (cleared) at the start of each suite run. Each test's block is appended as it executes. For PENDING, only the missing test's block is appended to the `.exp` — existing approved blocks are never overwritten.

**Multiple SELECTs:** Each SELECT becomes its own numbered statement block. All are compared pairwise by position. A statement count mismatch between `.exp` and `.res` fails immediately — adding or removing a SELECT from the query forces a deliberate `.exp` update.

### MySQL Cursor Compatibility — `_split_statements()` vs `multi=True`

`mysql-connector-python` provides two cursor implementations — pure Python (`MySQLCursor`) and C extension (`CMySQLCursor`). The C extension is the default when installed and does not support `cursor.execute(sql, multi=True)`, raising `TypeError` at runtime.

`use_pure=True` on the connection forces the pure Python cursor but is unreliable — some connector versions do not recognise the flag, some silently ignore it, and if the C extension was already imported it may have no effect.

The definitive fix is `_split_statements()` — a quote-aware and `--` comment-aware semicolon splitter that produces individual statements, each executed with plain `cursor.execute(stmt)`. This requires no `multi=True` and works identically with both cursor types. `use_pure=True` is retained as a safety net but the framework no longer depends on it.

### Comparison Algorithm

1. Parse both `.exp` and `.res` using `_parse_test_blocks` — returns `{test_name: [statement_blocks]}` for each file.
2. Extract the target test's block list from each file by `test_name`.
3. Assert statement counts match for that test — different number of blocks is an immediate failure.
4. Compare each statement block pairwise by position:
   - **`no_result`** — both sides must be `no_result`; type mismatch fails
   - **`dml`** — `ROWS AFFECTED` counts must match exactly; wrong row count fails
   - **`select`** — assert column headers match (position-based); normalise floats to `float_precision` decimal places; sort both row lists; compare element-wise (unordered match)
5. Collect **all** mismatches across all statements — do not stop at the first failure.
6. Return a combined failure message listing every statement that mismatched, identified by statement number and SQL text.

### Parallelism Model

`multiprocessing.Pool.imap_unordered` dispatches one task per SQL file. Each worker process calls `run_file(args)` which is a free function (picklable) that parses the file and runs its suite. `ServerCrashError` propagates out of the pool and aborts the main process.

### Parallel Reporting

Worker processes are silent — they never write to the terminal or log file. Each worker only builds and returns a list of result dicts when its file completes. The main process receives completed file results via `imap_unordered` and is the sole writer to the terminal. This eliminates interleaved output from concurrent workers.

Consequence: output appears in file-completion order (whichever file finishes first), not in file-declaration order. The terminal shows one line per file — consistent with the file-level reporting model — so there is no concept of per-test real-time output to lose. HTML and JSON reports retain full test-level detail for post-run analysis.

### No-Compare Mode

`--no-compare` is a run-level CLI flag. It bypasses the comparator for every test in the run, always recording PASS (provided no SQL error occurred). The `-- NO_COMPARE:` marker in a SQL file does the same for an individual test. Both paths still write `.res` files.

### Configuration

`config.ini` uses Python's `configparser`. The `[database]` section holds connection details; the `[settings]` section holds `float_precision`; the optional `[global]` section holds `setup_dir` pointing to the conftest directory. All settings have sensible defaults so only credentials are mandatory.

### Global Setup / Teardown

A three-level setup hierarchy is supported — global (once per run), suite (once per file), test (once per test). Global setup files live in a `conftest/` directory configured via `[global] setup_dir` in `config.ini`. Multiple files are supported and split by concern. Files run in alphabetical order for setup and reverse order for teardown. Global teardown is wrapped in a `finally` block so it always executes regardless of test outcome. `--dry-run` skips global setup/teardown entirely.

### Retry Failed Files

`--retry` triggers a second pass after the first completes. Two helper functions in `sqltest.py` implement this: `_failed_suites(results)` returns the set of suite names with at least one `FAIL` or `ERROR`; `_remove_suite_results(results, suites)` strips their first-pass entries from `all_results`. The retry pass rebuilds `task_args` for failed files only and re-runs them with the same worker count. `all_results` is mutated in-place so the retry results are appended alongside the retained first-pass results for passing files. Re-running the entire file (not just the failing test) is deliberate — `SUITE_SETUP` guarantees a clean database state, which cannot be assumed if only the failing test is re-run. `PASS`, `SKIP`, and `PENDING` files are never retried. `--retry` is silently ignored when combined with `--dry-run`.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All tests passed, skipped, or pending |
| 1 | One or more tests failed or errored |
| 2 | Run aborted due to MySQL server crash |

---

## Testing Decisions

### What Makes a Good Test

A good test for this framework exercises the external behaviour of a module through its public interface and asserts on observable outputs. It does not assert on internal state, private methods, or implementation details that could change without affecting behaviour.

### Modules to Test

**Parser** — highest priority. It is pure (no I/O beyond file reading), deterministic, and its output is the contract everything else depends on. Tests should cover: single test per file, multiple tests per file, suite setup/teardown, all marker types, SKIP with and without reason, TAGS parsing, NO_COMPARE flag, missing QUERY marker, mixed case markers, empty file.

**Comparator** — second priority. Also pure (reads two files, returns a verdict). Tests should cover: exact match, row order independence, column order mismatch, missing columns, extra columns, NULL handling, float tolerance (within and outside threshold), zero-row match, missing expected file, missing result file.

**Config loader** — low complexity but worth a smoke test covering: valid config, missing database section, missing optional settings section (defaults applied).

**Executor and Runner** — require a real MySQL connection. These are better covered by integration tests run against a local MySQL instance in CI. They should not be mocked, as mock-based tests of database interaction have historically masked real failures.

**Reporter** — terminal output and file generation can be tested by asserting on file contents and log output for a known set of result dicts.

---

## Out of Scope

- Support for databases other than MySQL (PostgreSQL, SQLite, etc.)
- Test dependency graphs (DAG-based ordering) — identified as a future enhancement
- Column masking (`-- IGNORE_COLUMNS:`) — identified as a future enhancement
- Snapshot update mode (`--update-snapshots`) — identified as a future enhancement
- Query plan / EXPLAIN capture and regression detection — future enhancement
- Performance regression detection across runs — future enhancement
- Flaky test detection (multi-run) — future enhancement
- Mutation testing — future enhancement
- Watch mode (`--watch`) — future enhancement
- Checkpoint and resume after server crash — future enhancement
- Plugin architecture for custom comparators/reporters — future enhancement
- Slack / email notifications — future enhancement
- Test history trending — future enhancement
- `--changed-only` git-aware execution — future enhancement
- Web UI for browsing results
- Windows support (multiprocessing behaviour differs)

---

## Further Notes

- The framework was designed with extensibility explicitly in mind. The CLI uses `argparse` so new flags can be added without breaking existing invocations. New SQL markers can be added to the parser regex without changing existing test files. The comparator, reporter, and runner are decoupled enough that each can be replaced independently.
- The `PENDING` state is intentional and important: it lowers the barrier to writing new tests (no need to manually author expected files) while still requiring a human to review and approve auto-generated output before it becomes authoritative.
- Float precision is global (set in `config.ini`) rather than per-test. If per-test precision control is needed in future, a `-- FLOAT_PRECISION: N` marker would be the natural extension point.
- The double-underscore naming convention (`file__test.exp`) was chosen specifically to avoid collisions between test names that contain underscores and the file prefix.
