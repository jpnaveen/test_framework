# SQL Test Framework — Design Document

## Overview

A Python-based test framework that executes SQL test files against a MySQL database, compares results against expected output, and reports pass/fail status.

---

## Technology Stack

| Component | Choice |
|-----------|--------|
| Language | Python |
| Database | MySQL (`mysql-connector-python`) |
| CLI | `argparse` |
| Parallelism | `multiprocessing.Pool` |

---

## Directory Structure

```
sql_test_framework/
  sqltest.py          # CLI entry point
  config.ini          # database connection + settings
  requirements.txt
  framework/
    config.py         # loads config.ini
    logger.py         # dual terminal + file logging
    parser.py         # parses SQL files into suite/test objects
    executor.py       # runs SQL against MySQL, detects server crashes
    comparator.py     # compares .res vs .exp files
    runner.py         # orchestrates suite execution + global setup/teardown
    reporter.py       # terminal summary + HTML/JSON reports
  test/
    conftest/         # global setup/teardown SQL files (run before/after all test files)
      01_schema.sql
      02_reference_data.sql
    orders_test.sql   # SQL test files
    customers_test.sql
  expected/           # expected result files (.exp)
  result/             # actual result files written after each run (.res)
  logs/               # timestamped log files
```

---

## Test File Format

Each `.sql` file contains one or more tests delimited by comment-based markers.

### Markers

| Marker | Scope | Description |
|--------|-------|-------------|
| `-- SUITE_SETUP:` | File | SQL that runs once before all tests in the file |
| `-- SUITE_TEARDOWN:` | File | SQL that runs once after all tests in the file |
| `-- TEST: <name>` | Test | Declares a new test with the given name |
| `-- TAGS: <t1>, <t2>` | Test | Comma-separated tags for filtering |
| `-- SKIP: <reason>` | Test | Skips the test; reason is optional |
| `-- NO_COMPARE:` | Test | Runs the query and writes `.res` but skips comparison (always PASS) |
| `-- SETUP:` | Test | SQL that runs before this specific test |
| `-- QUERY:` | Test | The SQL query to execute and compare |
| `-- TEARDOWN:` | Test | SQL that runs after this specific test |

### Example

```sql
-- SUITE_SETUP:
CREATE TABLE IF NOT EXISTS orders (
    id INT PRIMARY KEY,
    customer_id INT,
    amount DECIMAL(10,2),
    order_date DATE
);

-- SUITE_TEARDOWN:
DROP TABLE IF EXISTS orders;

-- Single SELECT — simplest case
-- TAGS: smoke, orders
-- TEST: total_order_count
-- SETUP:
INSERT INTO orders VALUES (1, 1, 100.00, '2024-01-01');
-- QUERY:
SELECT COUNT(*) AS total FROM orders;
-- TEARDOWN:
DELETE FROM orders;

-- Multiple SELECTs in one QUERY block — each becomes its own STATEMENT block
-- TAGS: orders
-- TEST: orders_summary
-- SETUP:
INSERT INTO orders VALUES (1, 1, 100.00, '2024-01-01'),
                          (2, 1, 200.00, '2024-01-02'),
                          (3, 2, 150.00, '2024-01-03');
-- QUERY:
SELECT COUNT(*) AS total_orders FROM orders;

SELECT customer_id, COUNT(*) AS order_count
FROM orders
GROUP BY customer_id
ORDER BY customer_id;

SELECT MIN(amount) AS min_amt, MAX(amount) AS max_amt, SUM(amount) AS total_amt
FROM orders;
-- TEARDOWN:
DELETE FROM orders;

-- Mixed: SET variable + multiple SELECTs
-- TAGS: orders
-- TEST: orders_with_variables
-- SETUP:
INSERT INTO orders VALUES (1, 1, 100.00, '2024-01-01'),
                          (2, 1, 200.00, '2024-01-02'),
                          (3, 2, 150.00, '2024-01-03');
-- QUERY:
SET @threshold = 150.00;

SELECT COUNT(*) AS orders_above_threshold
FROM orders WHERE amount >= @threshold;

SELECT customer_id, SUM(amount) AS total
FROM orders WHERE amount >= @threshold
GROUP BY customer_id;
-- TEARDOWN:
DELETE FROM orders;

-- SKIP: feature not yet deployed
-- TEST: future_feature
-- QUERY:
SELECT 1;

-- NO_COMPARE:
-- TEST: load_staging_data
-- QUERY:
INSERT INTO staging SELECT * FROM source;
```

### Multiple SELECTs — How the Files Look

When `orders_summary` runs, its `.res` block contains three statement blocks:

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

```

The `.exp` file must have the identical structure. Each SELECT is compared pairwise by position. If STATEMENT 2 fails, STATEMENT 1 and 3 are still checked — all mismatches are collected and reported together.

**Statement count rule:** If the query is changed to add or remove a SELECT, the statement count no longer matches the `.exp` and the test fails immediately with `Statement count mismatch`. This forces the engineer to update the `.exp` file deliberately — wrong output cannot silently pass.

---

## Expected / Result File Format

| Folder | Extension | Description |
|--------|-----------|-------------|
| `expected/` | `.exp` | Hand-authored or auto-generated expected output |
| `result/` | `.res` | Actual output written after each test run |

- File naming: `<sql_filename>.exp` / `<sql_filename>.res` — **one file per SQL test file**
- Both files use the **same unified format** — test blocks separated by `-- TEST:` markers, each containing statement blocks separated by `-- STATEMENT N:` markers
- Clean 1:1:1 relationship: one `.sql` → one `.exp` → one `.res`

### Unified Format

Each test in the suite gets a `-- TEST: name` block. Within each test block, every SQL statement is written as a numbered `-- STATEMENT N:` block:

| Line | Meaning |
|------|---------|
| `-- TEST: <name>` | Opens a test block |
| `-- STATEMENT N: <sql>` | Opens a statement block; `<sql>` is the first line (capped at 80 chars) |
| CSV header + rows | The result set for a SELECT statement |
| `-- ROWS AFFECTED: N` | Row count for INSERT / UPDATE / DELETE |
| `-- NO RESULT` | Statement produced no result set and affected no rows (e.g. SET) |

### Example `orders_test.exp` / `orders_test.res`

```
-- TEST: total_orders_by_customer
-- STATEMENT 1: SET @cutoff = '2024-01-01';
-- NO RESULT

-- STATEMENT 2: INSERT INTO audit_log VALUES (NOW(), 'test_run');
-- ROWS AFFECTED: 1

-- STATEMENT 3: SELECT customer_id, COUNT(*) AS order_count FROM orders WHERE
customer_id,order_count
1,3
2,1

-- TEST: orders_by_date
-- STATEMENT 1: SELECT order_date, SUM(amount) FROM orders GROUP BY order_date
order_date,total
2024-01-01,100.000000
2024-01-02,200.000000

```

### Why One File Per Suite

- **1:1:1 relationship** — `orders_test.sql` → `orders_test.exp` → `orders_test.res`; no double-underscore naming convention needed
- **Side-by-side diff** — all expected output for a file in one place; open both `.exp` and `.res` and diff the entire suite at once
- **Mirrors SQL file structure** — one SQL file has many tests; one result file has many test blocks
- **Simpler PENDING** — on first run, each new test's block is appended to the `.exp` file; existing approved blocks are untouched

### NULL Representation

`NULL` database values are written as the string `NULL` in result rows. Empty string and `NULL` are treated as distinct values.

---

## Comparison Rules

| Rule | Behaviour |
|------|-----------|
| File format | Both `.exp` and `.res` use identical format — `-- TEST:` blocks containing `-- STATEMENT N:` blocks |
| File granularity | One `.exp` and one `.res` per SQL file (suite), not per individual test |
| Parser | Both files parsed by `_parse_test_blocks` returning `{test_name: [statement_blocks]}` |
| Comparison scope | **All statements compared per test** — `NO RESULT`, `ROWS AFFECTED`, and SELECT result sets |
| Statement count | Number of statement blocks must match exactly per test |
| `NO RESULT` | Both sides must be `no_result` — type mismatch is a failure |
| `ROWS AFFECTED` | Counts must match exactly — a wrong INSERT/UPDATE/DELETE count is a failure |
| SELECT rows | Unordered — rows from both files are sorted before comparison |
| Column order | Must match exactly (position-based, not name-based) |
| NULL values | Represented as the string `NULL` — never Python `None` |
| Floats / decimals | Compared with configurable tolerance (`float_precision` in `config.ini`) |
| Zero rows | Valid expected outcome — SELECT block has header only, no data rows |
| All mismatches reported | All statement failures collected and reported together — engineer sees the full picture in one run |
| Missing test block in `.exp` | That test's block appended to `.exp` from `.res`; test marked `PENDING`; existing blocks untouched |

---

## Test Status Values

| Status | Meaning |
|--------|---------|
| `PASS` | Query executed and result matches expected |
| `FAIL` | Query executed but result does not match expected |
| `ERROR` | Query threw a SQL error |
| `SKIP` | Test has a `-- SKIP:` marker |
| `PENDING` | No `.exp` file existed; auto-generated from actual result |

---

## Configuration (`config.ini`)

```ini
[database]
host = localhost
port = 3306
user = root
password = password
database = testdb

[settings]
float_precision = 6

[global]
; Directory containing global setup/teardown SQL files.
; Files run in alphabetical order before any test file.
; Teardown runs in reverse order after all test files finish.
; Leave blank or omit section to disable global setup.
setup_dir = test/conftest
```

---

## Global Setup / Teardown

A three-level setup hierarchy is supported:

```
GLOBAL_SETUP    → runs once before all test files (main process, sequential)
  SUITE_SETUP   → runs once per SQL file (worker process)
    TEST_SETUP  → runs once per test (worker process)
    TEST_TEARDOWN
  SUITE_TEARDOWN
GLOBAL_TEARDOWN → runs once after all test files (main process, sequential)
```

### conftest/ Directory

Global setup SQL files live in a directory configured via `config.ini` `[global] setup_dir`. Files use the same `-- SUITE_SETUP:` / `-- SUITE_TEARDOWN:` markers as regular test files. Splitting across multiple files keeps each file focused on one concern (schema, reference data, seed data):

```
test/conftest/
  01_schema.sql         ← CREATE TABLE statements
  02_reference_data.sql ← lookup tables, status codes
  03_seed_customers.sql ← customer test data
```

### Execution Order

- **Setup**: files run in **alphabetical order** — numeric prefixes (`01_`, `02_`) make dependency order visible
- **Teardown**: files run in **reverse order** — child data deleted before parent tables dropped, respecting foreign key constraints

### Guarantees

| Behaviour | Detail |
|-----------|--------|
| Setup runs before workers | Global setup completes on the main process before the worker pool starts |
| Teardown always runs | Wrapped in `finally` — executes even if tests crash or server goes down mid-run |
| Dry-run skips global setup | `--dry-run` skips all SQL execution including global setup/teardown |
| Missing directory | Silently skipped — no error if `setup_dir` is not set or directory does not exist |
| Server crash in global setup | Aborts immediately with exit code 2 — no test files run |
| Server crash in global teardown | Logs a warning — manual cleanup may be required |

---

## CLI Reference

```bash
python sqltest.py [options]
```

| Flag | Description |
|------|-------------|
| `--config <path>` | Path to `config.ini` (required) |
| `--file <path>` | Run a specific SQL test file only |
| `--test <name>` | Run a specific test by name within a file |
| `--tag <tag>` | Run only tests that have this tag |
| `--workers <N>` | Number of parallel worker processes (default: 1) |
| `--no-compare` | Execute all SQL and write `.res` files but skip comparison (always PASS) |
| `--dry-run` | Parse and validate test files without executing any SQL |
| `--retry` | Re-run all files that had at least one FAIL or ERROR after the first pass |
| `--report html\|json` | Generate an HTML or JSON report after the run |
| `--report-output <path>` | Output path for report file, without extension (default: `report`) |

### Usage Examples

```bash
# Run all tests, single process
python sqltest.py --config config.ini

# Run all tests, 4 parallel workers
python sqltest.py --config config.ini --workers 4

# Run a specific file
python sqltest.py --config config.ini --file test/orders_test.sql

# Run a specific test by name
python sqltest.py --config config.ini --test total_order_count

# Run only smoke-tagged tests
python sqltest.py --config config.ini --tag smoke

# Retry failed files after the first pass
python sqltest.py --config config.ini --retry

# Coverage / memory leak run — no comparison
python sqltest.py --config config.ini --no-compare

# Dry run — validate test files without hitting the database
python sqltest.py --config config.ini --dry-run

# Generate HTML report
python sqltest.py --config config.ini --report html --report-output reports/run1
```

---

## Parallelism

- Granularity: **one process per SQL file**
- Suite-level `SETUP/TEARDOWN` always runs in the same process as its tests, preventing race conditions on shared database state
- Controlled via `--workers N`; defaults to 1 (single process)

### Parallel Reporting

Worker processes are **silent** — they never write to the terminal or log file. Each worker only builds and returns a list of result dicts when its entire file completes. The main process is the **sole writer** to the terminal, printing each file's results as a clean block the moment that file's worker finishes.

```
Worker 1 (orders_test.sql)     ──► returns results ──►┐
Worker 2 (customers_test.sql)  ──► returns results ──►├──► main process prints
Worker 3 (invoices_test.sql)   ──► returns results ──►┘
```

This eliminates interleaved output without requiring locks or queues. The output arrives in file-completion order (whichever worker finishes first), not file-declaration order. Within each file, tests always appear together in sequence.

**Trade-off:** per-test real-time feedback is only visible after the slowest test in a file completes, not as each individual test finishes. This is acceptable for most suites. If per-test real-time feedback becomes a requirement, the solution is a `multiprocessing.Queue` where workers push result dicts and a dedicated printer thread in the main process drains and prints them in order.

---

## Retry Failed Files

### Why Re-run the File, Not Just the Failed Test

Each SQL file owns its schema lifecycle via `SUITE_SETUP` and `SUITE_TEARDOWN`. Running a failed test in isolation — without its `SUITE_SETUP` — risks executing against stale or dirty database state left by a previous failed run. Re-running the entire file guarantees a clean slate every time.

### Behaviour

When `--retry` is passed:

1. **First pass** — all files run normally, results collected
2. **Failed files identified** — any file with at least one `FAIL` or `ERROR` test
3. **Retry pass** — failed files re-run from scratch (`SUITE_SETUP` → tests → `SUITE_TEARDOWN`)
4. **First-pass results replaced** — the retry results overwrite the first-pass results for those files
5. **Summary reflects final state** — counts based on retry results, not first-pass results

```
First pass:
  orders_test.sql     → FAIL   ← will be retried
  customers_test.sql  → PASS
  invoices_test.sql   → FAIL   ← will be retried

Retry pass:
  orders_test.sql     → PASS   ← recovered
  invoices_test.sql   → FAIL   ← still failing

Final result:
  orders_test.sql     → PASS
  customers_test.sql  → PASS
  invoices_test.sql   → FAIL
```

### What Gets Retried

| Status | Retried? | Reason |
|--------|----------|--------|
| `FAIL` | Yes | Result mismatch — may be transient data issue |
| `ERROR` | Yes | SQL error — may be transient connection or lock issue |
| `PASS` | No | Already passing |
| `SKIP` | No | Explicitly skipped |
| `PENDING` | No | No expected file — not a failure |

### Why Not Retry Individual Tests

Retrying individual tests without `SUITE_SETUP` breaks the file's isolation contract. If a previous test's `TEARDOWN` failed, the database may be in a dirty state. The full file re-run is the only way to guarantee a clean starting point.

### Implementation

Two helper functions in `sqltest.py`:

```python
def _failed_suites(results: list) -> set:
    return {r["suite"] for r in results if r["status"] in ("FAIL", "ERROR")}

def _remove_suite_results(results: list, suites: set) -> list:
    return [r for r in results if r["suite"] not in suites]
```

After the first pass, if `--retry` is set:

```python
failed = _failed_suites(all_results)
if failed:
    all_results[:] = _remove_suite_results(all_results, failed)  # replace in-place
    retry_tasks = [t for t in task_args
                   if os.path.splitext(os.path.basename(t[0]))[0] in failed]
    # re-run with same worker count
```

`all_results[:] =` mutates the list in-place so the `_print_and_collect` closure used by the retry pass appends to the same list as the first pass. `--retry` is silently ignored when `--dry-run` is set — no SQL executes in dry-run mode so there is nothing to retry.

---

## Executor — Functions, Inputs and Outputs

### `connect(config)`

| | Detail |
|-|--------|
| Input | `config` dict — `host`, `port`, `user`, `password`, `database`, `float_precision` |
| Output (success) | Live MySQL connection object |
| Output (failure) | Raises `ServerCrashError` |

#### `use_pure=True` — Why It Is Set and Why It Is Not the Primary Fix

`mysql-connector-python` ships two cursor implementations:

| Implementation | Class | `multi=True` support |
|----------------|-------|---------------------|
| Pure Python | `MySQLCursor` | ✅ Supported |
| C extension | `CMySQLCursor` | ❌ Not supported |

When the C extension is installed (the default on most systems), `CMySQLCursor` is used automatically. Calling `cursor.execute(sql, multi=True)` raises:

```
TypeError: CMySQLCursor.execute() got an unexpected keyword argument 'multi'
```

`use_pure=True` forces the pure Python `MySQLCursor`. However it is **not a reliable cross-version fix**:

- Some connector versions do not recognise `use_pure` and raise `TypeError: unexpected keyword argument`
- Some versions accept it but silently ignore it — still returning `CMySQLCursor`
- If the C extension was already imported by another library before `connect()`, `use_pure=True` may have no effect

**The real fix is `_split_statements()`** — splitting SQL manually and calling plain `cursor.execute(single_statement)` with no `multi=True`. This works identically on both `MySQLCursor` and `CMySQLCursor` regardless of connector version.

`use_pure=True` is kept as a **safety net only** — on versions where it works, it removes C extension incompatibilities beyond `multi=True`. But the framework no longer depends on it.

#### `consume_results=True` — Fixing `Unread result found`

After `CALL procedure()` executes, MySQL sends result sets followed by a final status/OK packet. The pure Python cursor's `cursor.nextset()` returns `None` immediately — it is not fully implemented — so the status packet remained unread in the connection's socket buffer. The next `cursor.execute()` found the leftover bytes and raised:

```
InternalError: Unread result found
```

`consume_results=True` on the connection tells the connector to automatically read and discard any buffered result bytes from the previous statement before executing a new one. It operates at the **protocol level** — not the cursor level — so it correctly handles packets that `cursor.nextset()` cannot reach.

Both parameters are set together:

```python
conn = mysql.connector.connect(
    ...,
    use_pure=True,        # safety net against CMySQLCursor API differences
    consume_results=True, # auto-discard leftover socket bytes before each execute
)
```

### `initialize_result_file(result_path)`

| | Detail |
|-|--------|
| Input | Path to the suite-level `.res` file (e.g. `result/orders_test.res`) |
| Output | Creates or clears the file on disk; returns nothing |
| When called | Once per suite at the start of `run_suite` — before any test executes |
| Why | Ensures each run starts with a clean `.res` before tests append their blocks |

### `run_sql(conn, sql)`

| | Detail |
|-|--------|
| Input | Live MySQL connection + SQL string (may contain multiple statements) |
| Output | `List[dict]` — one dict per statement in execution order |

Each dict has:

| Key | Type | Meaning |
|-----|------|---------|
| `sql` | `str` | First 80 chars of the statement text |
| `columns` | `List[str] \| None` | Column names for SELECT; `None` otherwise |
| `rows` | `List[tuple] \| None` | Result rows for SELECT; `None` otherwise |
| `affected` | `int \| None` | Row count for DML; `None` for SELECT |

Statement splitting rules in `_split_statements()`:

| Context | Behaviour |
|---------|-----------|
| Semicolon outside quotes | Split point — starts a new statement |
| Semicolon inside `'...'` | Ignored |
| Semicolon inside `"..."` | Ignored |
| Semicolon inside `-- comment` | Ignored — `in_line_comment` state tracks until `\n` |

Error behaviour:

| Scenario | Raises |
|----------|--------|
| SQL syntax / runtime error | `MySQLError` — runner catches, marks test `ERROR` |
| Connection lost mid-query | `ServerCrashError` — stops the entire run |

Cursor handling: cursor is created before `try` and closed in `finally` — always closed regardless of success or error.

### `write_result(result_path, test_name, statement_results, float_precision)`

| | Detail |
|-|--------|
| Input | `.res` path, test name, list of statement result dicts, float precision |
| Output | Appends one `-- TEST:` block to the `.res` file; **returns the text written** |
| Append mode | Opens file in append mode — never overwrites existing test blocks |
| Return value used by | Runner — passed to `_append_to_exp()` to auto-generate PENDING blocks |
| Line endings | `csv.writer(lineterminator="\n")` — consistent `\n` on all platforms |

Value formatting applied before writing:

| Type | Format |
|------|--------|
| `None` (NULL) | Written as string `"NULL"` |
| `float` or `decimal.Decimal` | Converted via `float()` then rounded to `float_precision` decimal places |
| `ROWS AFFECTED = 0` | Written as `-- NO RESULT`, not `-- ROWS AFFECTED: 0` |
| All other values | `str()` conversion |

---

## Runner — Functions, Inputs and Outputs

### `run_suite(suite, config, base_dir, filter_test, filter_tag, dry_run, no_compare)`

**Input:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `suite` | `TestSuite` | Parsed object from `parser.py` |
| `config` | `dict` | DB credentials + `float_precision` |
| `base_dir` | `str` | Framework root — where `expected/` and `result/` live |
| `filter_test` | `str \| None` | Run only this test name (`--test` flag) |
| `filter_tag` | `str \| None` | Run only tests with this tag (`--tag` flag) |
| `dry_run` | `bool` | Skip all SQL execution (`--dry-run` flag) |
| `no_compare` | `bool` | Skip comparison for entire run (`--no-compare` flag) |

**Output:** `List[dict]` — one dict per processed test:

```python
{
    "suite":    "orders_test",   # SQL filename without extension
    "test":     "total_orders",  # test name from -- TEST: marker
    "status":   "PASS",          # PASS | FAIL | ERROR | SKIP | PENDING
    "message":  "",              # error detail, skip reason, or empty
    "duration": 0.042            # seconds taken to execute the test
}
```

### `run_file(args)`

Entry point for `multiprocessing.Pool` workers. Unpacks a tuple `(file_path, config, base_dir, filter_test, filter_tag, dry_run, no_compare)`, calls `parse_file()` then `run_suite()`, and returns the same `List[dict]`. Must be a free (picklable) function — not a method — for multiprocessing compatibility.

### `run_global_setup(config)` / `run_global_teardown(config)`

**Input:** `config` dict containing `global_setup_dir`

**Output:** Nothing — side effects only

- Setup: discovers all `.sql` files in `conftest/` alphabetically, opens a single connection, runs each file's `SUITE_SETUP` block in order
- Teardown: same files in **reverse order**, runs each `SUITE_TEARDOWN` block
- Both: raise `ServerCrashError` on connection loss; close connection in `finally`

---

## Runner — Execution Flow and Complex Logic

### Full Execution Flow

```
check for duplicate test names → raise ValueError immediately if found

dry_run? → return synthetic results, skip all SQL

connect to MySQL
initialize .res file (clear)
run SUITE_SETUP

for each TestCase:
  ├── filtered out?          → skip silently (not in results)
  ├── test.skip?             → record SKIP, continue
  ├── no test.query?         → record ERROR, continue
  ├── run SETUP
  │   try:
  │     run QUERY → write .res block
  │     ├── ServerCrashError → re-raise (stops everything)
  │     └── any other error  → record exec_error
  │   finally:
  │     run TEARDOWN (always — even on query error)
  │     teardown errors logged, do not mask query error
  │   if exec_error → record ERROR, continue
  ├── no_compare?            → record PASS, continue
  ├── test block missing in .exp? → append block, record PENDING, continue
  └── compare .exp vs .res   → record PASS or FAIL

run SUITE_TEARDOWN
close connection (always — in finally)

return List[dict]
```

### Complex Logic 0 — Duplicate Test Name Detection

`_check_duplicate_names(suite)` is called as the very first step of `run_suite` — before `dry_run`, before connecting to MySQL, before anything executes:

```python
seen = set()
duplicates = []
for test in suite.tests:
    if test.name in seen and test.name not in duplicates:
        duplicates.append(test.name)
    seen.add(test.name)
if duplicates:
    raise ValueError(f"Duplicate test name(s) in {suite.file_path}: {duplicates}")
```

**Why this matters:** Both tests with the same name pass the `filter_test` check and execute. Both call `write_result()` which appends two `-- TEST: name` blocks to the same `.res` file. When `_parse_test_blocks` reads the file, the second block silently overwrites the first in the dict — the first test's results are lost and comparison is unreliable.

**Why raise before `dry_run`:** Duplicate names are a structural error in the test file, not a runtime error. Detecting them before any SQL runs means `--dry-run` also catches the problem, giving engineers early feedback without database access.

**Same name across different files is safe:** Each file has its own `.res` and `.exp`. The `filter_test` check runs independently within each file's worker — `total_orders` in `orders_test.sql` and `total_orders` in `customers_test.sql` write to completely separate files with no conflict.

---

### Complex Logic 1 — Two-Level Error Handling

Two exceptions are handled differently inside the test execution block:

```python
except ServerCrashError:
    raise                    # infrastructure failure — stop everything
except Exception as e:
    results.append(ERROR)    # test failure — record and continue
    continue
```

`ServerCrashError` propagates immediately — there is no point running more tests against a dead server. Any other exception (SQL error, constraint violation, timeout) is recorded as `ERROR` for that test only and the suite continues.

### Complex Logic 2 — PENDING via Append, Not File Copy

When a test's block is missing from `.exp`:

```python
if not _test_block_exists(exp_p, test.name):
    _append_to_exp(exp_p, content)   # content returned by write_result
    record PENDING
```

`_test_block_exists` parses the `.exp` into `{test_name: blocks}` and checks if the key exists. `_append_to_exp` opens the file in **append mode** — existing approved blocks for other tests in the same `.exp` are never touched. Only the new test's block is added.

### Complex Logic 3 — `write_result` Return Value Reuse

```python
content = write_result(res_p, test.name, statement_results, precision)
```

`write_result` returns the text it just wrote to `.res`. The runner stores it in `content` and reuses it directly for `_append_to_exp`. This avoids re-reading the `.res` file to extract the new block — the data is already in memory.

### Complex Logic 5 — Resilient Global Teardown

Each conftest file's teardown is wrapped in its own `try/except` so a MySQL error in one file logs a warning and continues to the next — the tool never crashes mid-teardown leaving remaining tables in the database:

```python
for file_path in reversed(files):
    try:
        run_sql(conn, suite.suite_teardown)
    except ServerCrashError:
        raise                           # server gone — stop everything
    except Exception as e:
        logger.error(f"[GLOBAL_TEARDOWN ERROR] {label}: {e} — continuing")
        # next file still runs
```

`sqltest.py` also catches all exceptions from `run_global_teardown` to prevent raw Python tracebacks reaching the terminal:

```python
except ServerCrashError:
    logger.error("[SERVER CRASH] Global teardown failed...")
except Exception as e:
    logger.error(f"[GLOBAL_TEARDOWN ERROR] {e} — manual cleanup may be required.")
```

### Complex Logic 6 — Mandatory Colon in Marker Regex

The parser MARKER regex requires a literal `:` after every keyword:

```python
MARKER = re.compile(
    r"^--\s*(SUITE_SETUP|...|TEST|...)\s*:\s*(.*)?$",
    re.IGNORECASE,
)
```

The original regex had `:?` (colon optional). A comment like `-- Tests that BEGIN...END body...` matched as keyword `TEST` with value `s that BEGIN...END body...` — creating phantom tests with garbled names. Making the colon mandatory means only `-- TEST: name` format lines are recognised. Regular comments containing marker keywords are correctly ignored.

---

### Complex Logic 7 — Teardown Always Runs

TEARDOWN is placed in a `finally` block nested inside the test execution so it runs regardless of whether QUERY succeeds or fails:

```python
try:
    statement_results = run_sql(conn, test.query)
    content = write_result(...)
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
```

**Why this matters:** Without this, a QUERY that throws a SQL error skips TEARDOWN entirely. Data inserted by SETUP remains in the database and pollutes subsequent tests in the same suite — causing false failures that are difficult to diagnose.

**Teardown error handling:** Teardown errors are logged but do not replace the original query error. The test is still recorded as `ERROR` for the query failure, not for the teardown failure.

---

### Complex Logic 4 — Connection Always Closed

```python
finally:
    try:
        conn.close()
    except Exception:
        pass
```

The connection is closed in `finally` so it always executes — whether tests completed normally, a SQL error occurred mid-suite, or a `ServerCrashError` was raised. The inner `try/except` prevents a secondary exception if the connection is already dead when `close()` is called.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| SQL syntax / runtime error | Fail that individual test with error message; `TEARDOWN` still runs via `finally`; continue remaining tests |
| MySQL server crash / lost connection | Stop the entire run immediately, log the incident, exit with code 2 |
| Missing test block in `.exp` | Append that test's block from `.res` to `.exp`; mark test `PENDING` |
| Missing `-- QUERY:` marker | Mark test `ERROR`, continue |
| Duplicate test name within a file | Raise `ValueError` immediately — before `dry_run`, before MySQL connection |
| Same test name in different files | Safe — each file has its own `.res` / `.exp`; no conflict |
| `TEARDOWN` SQL error | Logged as warning — does not mask original query error |
| `DECIMAL` column values | Formatted with `float_precision` decimal places via `float()` conversion |
| `--` comments with semicolons in QUERY | Handled by `in_line_comment` state in `_split_statements` — not split |
| `Unread result found` after stored procedure | `consume_results=True` on connection auto-discards leftover socket bytes; fresh cursor per statement |
| Comment line matching marker keyword | Colon is mandatory in MARKER regex — `-- Tests that...` is ignored, `-- TEST: name` matches |
| Server crash during global setup | Abort immediately with exit code 2 — no test files run |
| Non-server MySQL error during global setup | Logged and exits with code 1 — no test files run |
| Server crash during global teardown | Log warning — manual cleanup may be required |
| Non-server MySQL error in one teardown file | Log warning, continue to next conftest teardown file |
| `setup_dir` not set or directory missing | Global setup silently skipped — no error |

---

## Logging

- **Terminal**: INFO-level messages printed to stdout in real time
- **Log file**: DEBUG-level messages written to `logs/sqltest_<YYYY-MM-DD_HH-MM-SS>.log`
- Server crash events are logged at ERROR level in both destinations

---

## Reporting

| Format | How to enable | Output |
|--------|--------------|--------|
| Terminal | Always on | One line per file, file-level counts, failed test detail |
| JSON | `--report json` | `report.json` (or `--report-output` path) — test-level detail |
| HTML | `--report html` | `report.html` (or `--report-output` path) — test-level detail |

### Terminal Output Format

One line per file printed as each file completes. The file status is derived from its tests:

| File status | Condition |
|-------------|-----------|
| `FAIL` | Any test in the file is FAIL or ERROR |
| `PENDING` | Any test is PENDING and no failures |
| `SKIP` | All tests in the file are SKIP |
| `PASS` | All other cases |

```
orders_test.sql: FAIL
customers_test.sql: PASS
invoices_test.sql: PASS
payments_test.sql: SKIP
```

Final summary at the end of the run — counts are at **file level**, not test level:

```
============================================================
  4 FILES RUN  |  2 PASS  |  1 FAILED  |  1 SKIPPED  |  0 PENDING
============================================================

FAILED TESTS:
  orders_test.sql  →  orders_by_date
  orders_test.sql  →  total_orders_by_customer
```

The `FAILED TESTS` section lists individual test names within failed files so the engineer knows exactly which tests to fix. HTML and JSON reports retain full test-level detail for post-run analysis.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All tests passed (or skipped/pending) |
| `1` | One or more tests failed or errored |
| `2` | Run aborted due to MySQL server crash |

---

## Future Enhancements (Identified, Not Yet Built)

- `--update-snapshots` — regenerate all `.exp` files from current results in one shot
- Column masking — `-- IGNORE_COLUMNS: created_at` to exclude dynamic columns from comparison
- `--failed-only` — rerun only tests that failed in the previous run
- Query timing threshold — flag tests that exceed a configurable duration
- Variable substitution — `{{var}}` placeholders in SQL replaced at runtime
- Row count assertions — `-- ASSERT: row_count > 5`
- Environment profiles — `--env dev|staging|prod` switching config blocks
- Watch mode — `--watch` auto-reruns tests on file change
- Slack / email notifications on suite failure
- Test history trending via a local SQLite store
- `--changed-only` — run only tests for SQL files modified since last git commit
