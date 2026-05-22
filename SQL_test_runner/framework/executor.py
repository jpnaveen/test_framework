import csv
import os
from decimal import Decimal
from typing import List, Optional, Tuple

import mysql.connector
from mysql.connector import Error as MySQLError

from .logger import logger


class ServerCrashError(Exception):
    pass


def connect(config: dict):
    try:
        conn = mysql.connector.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            use_pure=True,        # C extension does not support plain execute style
            consume_results=True, # auto-consume leftover result sets before each new execute
        )
        return conn
    except MySQLError as e:
        raise ServerCrashError(f"Cannot connect to MySQL server: {e}")


def _is_connection_error(e: MySQLError) -> bool:
    lost_codes = {2003, 2006, 2013, 2055}
    return e.errno in lost_codes


def _split_statements(sql: str) -> List[str]:
    """Split a SQL string into individual statements on semicolons,
    respecting:
      - single-quoted and double-quoted string literals
      - -- single-line comments
      - BEGIN...END compound statement blocks (CREATE PROCEDURE/FUNCTION/TRIGGER/EVENT)
      - nested block constructs inside BEGIN...END (IF, CASE, LOOP, WHILE, REPEAT)

    Semicolons inside BEGIN...END blocks are not treated as statement separators.
    A standalone BEGIN; (transaction start) is correctly handled — depth is only
    incremented when BEGIN follows non-empty content in the current statement.
    """
    # Keywords that open a nested block inside a compound statement
    _BLOCK_OPENERS = {"IF", "CASE", "LOOP", "WHILE", "REPEAT"}

    statements = []
    current: List[str] = []
    in_single = False
    in_double = False
    in_line_comment = False
    begin_depth = 0
    prev_ch = ""
    word_buf: List[str] = []

    def _flush_word() -> None:
        nonlocal begin_depth
        if not word_buf:
            return
        word = "".join(word_buf)
        word_len = len(word_buf)
        word_buf.clear()
        if word == "BEGIN":
            # Only a compound-statement opener when the current buffer
            # already has meaningful content before this BEGIN keyword.
            # A bare "BEGIN;" at the start of a statement is a transaction
            # control command and must not increment depth.
            content_before = "".join(current[:-word_len]).strip()
            if content_before:
                begin_depth += 1
        elif word == "END":
            if begin_depth > 0:
                begin_depth -= 1
        elif word in _BLOCK_OPENERS:
            # Track nested control-flow blocks only inside a compound statement
            if begin_depth > 0:
                begin_depth += 1

    def _is_word_char(c: str) -> bool:
        return c.isalnum() or c == "_"

    for ch in sql:
        # ── inside a line comment ────────────────────────────────────────
        if in_line_comment:
            current.append(ch)
            if ch == "\n":
                in_line_comment = False
            prev_ch = ch
            continue

        # ── start of -- comment (outside strings) ───────────────────────
        if ch == "-" and prev_ch == "-" and not in_single and not in_double:
            in_line_comment = True
            current.append(ch)
            prev_ch = ch
            continue

        # ── inside string literals — pass through ───────────────────────
        if in_single:
            if ch == "'":
                in_single = False
            current.append(ch)
            prev_ch = ch
            continue

        if in_double:
            if ch == '"':
                in_double = False
            current.append(ch)
            prev_ch = ch
            continue

        # ── outside strings and comments ────────────────────────────────
        if _is_word_char(ch):
            word_buf.append(ch.upper())
            current.append(ch)
        else:
            _flush_word()
            if ch == "'":
                in_single = True
                current.append(ch)
            elif ch == '"':
                in_double = True
                current.append(ch)
            elif ch == ";" and begin_depth == 0:
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                prev_ch = ch
                continue
            else:
                current.append(ch)

        prev_ch = ch

    _flush_word()
    last = "".join(current).strip()
    if last:
        statements.append(last)

    return statements


def run_sql(conn, sql: str) -> List[dict]:
    """Split SQL into individual statements and execute each one.
    Returns a list of result dicts, one per statement, in execution order.

    Each dict has:
      sql      - the original statement text
      columns  - list of column names (None if no result set)
      rows     - list of tuples (None if no result set)
      affected - row count for DML statements (None for SELECT)

    A fresh cursor is used per statement so that any unread result sets
    from stored procedures (CALL ...) are discarded when the cursor closes,
    preventing 'Unread result found' errors on the next execute.
    """
    try:
        statement_results = []

        for stmt in _split_statements(sql):
            cursor = conn.cursor()
            try:
                cursor.execute(stmt)

                # Drain all result sets. Regular statements produce one.
                # Stored procedures may return multiple — cursor.nextset()
                # advances to the next one; closing the cursor discards any
                # remaining unread results so the next statement is unaffected.
                has_more = True
                while has_more:
                    if cursor.description:
                        columns = [d[0] for d in cursor.description]
                        rows = cursor.fetchall()
                        statement_results.append({
                            "sql": stmt,
                            "columns": columns,
                            "rows": rows,
                            "affected": None,
                        })
                    else:
                        conn.commit()
                        statement_results.append({
                            "sql": stmt,
                            "columns": None,
                            "rows": None,
                            "affected": cursor.rowcount,
                        })
                    try:
                        has_more = bool(cursor.nextset())
                    except Exception:
                        has_more = False
            except MySQLError:
                raise
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass

        return statement_results
    except MySQLError as e:
        if _is_connection_error(e):
            raise ServerCrashError(f"MySQL server connection lost: {e}")
        raise


def _format_row(row: tuple, float_precision: int) -> List[str]:
    formatted = []
    for val in row:
        if val is None:
            formatted.append("NULL")
        elif isinstance(val, (float, Decimal)):
            formatted.append(f"{float(val):.{float_precision}f}")
        else:
            formatted.append(str(val))
    return formatted


def initialize_result_file(result_path: str):
    """Clear or create the .res file at the start of a suite run."""
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    open(result_path, "w").close()


def write_result(result_path: str, test_name: str,
                 statement_results: List[dict], float_precision: int) -> str:
    """Append one test's results to the .res file under a -- TEST: header.
    Returns the text written so the caller can reuse it for .exp generation."""
    import io
    buf = io.StringIO()
    buf.write(f"-- TEST: {test_name}\n")

    cw = csv.writer(buf, lineterminator="\n")
    for i, r in enumerate(statement_results, start=1):
        stmt_label = r["sql"].splitlines()[0][:80]
        buf.write(f"-- STATEMENT {i}: {stmt_label}\n")
        if r["columns"]:
            cw.writerow(r["columns"])
            for row in r["rows"]:
                cw.writerow(_format_row(row, float_precision))
        elif r["affected"] is not None and r["affected"] > 0:
            buf.write(f"-- ROWS AFFECTED: {r['affected']}\n")
        else:
            buf.write("-- NO RESULT\n")
        buf.write("\n")

    content = buf.getvalue()
    with open(result_path, "a") as f:
        f.write(content)
    return content
