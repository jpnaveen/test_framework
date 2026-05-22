import json
import os
from datetime import datetime
from typing import List

from .logger import logger


STATUS_COLORS = {
    "PASS": "\033[92m",
    "FAIL": "\033[91m",
    "SKIP": "\033[93m",
    "PENDING": "\033[94m",
    "ERROR": "\033[91m",
}
RESET = "\033[0m"


def _color(status: str, text: str) -> str:
    return f"{STATUS_COLORS.get(status, '')}{text}{RESET}"


def _file_status(file_results: List[dict]) -> str:
    """Derive a single file-level status from all its test results."""
    statuses = {r["status"] for r in file_results}
    if statuses & {"FAIL", "ERROR"}:
        return "FAIL"
    if "PENDING" in statuses:
        return "PENDING"
    if statuses == {"SKIP"}:
        return "SKIP"
    return "PASS"


def print_file_result(file_results: List[dict]):
    """Print one line per file showing the overall file status."""
    if not file_results:
        return
    suite_name = file_results[0]["suite"]
    sql_file = f"{suite_name}.sql"
    status = _file_status(file_results)
    logger.info(f"{sql_file}: {_color(status, status)}")


def print_summary(results: List[dict]):
    """Print file-level counts and list every individual failing test."""
    # group results by file
    files: dict = {}
    for r in results:
        files.setdefault(r["suite"], []).append(r)

    total   = len(files)
    passed  = sum(1 for f in files.values() if _file_status(f) == "PASS")
    failed  = sum(1 for f in files.values() if _file_status(f) == "FAIL")
    skipped = sum(1 for f in files.values() if _file_status(f) == "SKIP")
    pending = sum(1 for f in files.values() if _file_status(f) == "PENDING")

    logger.info("")
    logger.info("=" * 60)
    logger.info(
        f"  {total} FILES RUN  |  "
        f"{_color('PASS', str(passed))} PASS  |  "
        f"{_color('FAIL', str(failed))} FAILED  |  "
        f"{_color('SKIP', str(skipped))} SKIPPED  |  "
        f"{_color('PENDING', str(pending))} PENDING"
    )
    logger.info("=" * 60)

    failures = [r for r in results if r["status"] in ("FAIL", "ERROR")]
    if failures:
        logger.info("")
        logger.info("FAILED TESTS:")
        for r in failures:
            logger.info(f"  {r['suite']}.sql  →  {r['test']}")


def generate_json(results: List[dict], output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "summary": {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "SKIP", "PENDING", "ERROR")},
        "tests": results,
    }
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)
    logger.info(f"JSON report written to {output_path}")


def generate_html(results: List[dict], output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "SKIP", "PENDING", "ERROR")}

    status_style = {
        "PASS": "color:#2e7d32;font-weight:bold",
        "FAIL": "color:#c62828;font-weight:bold",
        "SKIP": "color:#f57f17;font-weight:bold",
        "PENDING": "color:#1565c0;font-weight:bold",
        "ERROR": "color:#b71c1c;font-weight:bold",
    }

    rows_html = ""
    for r in results:
        style = status_style.get(r["status"], "")
        msg = r["message"].replace("\n", "<br>") if r["message"] else ""
        rows_html += (
            f"<tr>"
            f"<td>{r['suite']}</td>"
            f"<td>{r['test']}</td>"
            f"<td style='{style}'>{r['status']}</td>"
            f"<td>{r.get('duration', 0):.3f}s</td>"
            f"<td>{msg}</td>"
            f"</tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>SQL Test Report</title>
  <style>
    body {{ font-family: monospace; padding: 20px; }}
    h1 {{ color: #333; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    tr:nth-child(even) {{ background: #fafafa; }}
    .summary {{ margin-bottom: 20px; font-size: 1.1em; }}
  </style>
</head>
<body>
  <h1>SQL Test Report</h1>
  <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
  <div class="summary">
    Total: {len(results)} &nbsp;|&nbsp;
    <span style="{status_style['PASS']}">PASS: {counts['PASS']}</span> &nbsp;|&nbsp;
    <span style="{status_style['FAIL']}">FAIL: {counts['FAIL']}</span> &nbsp;|&nbsp;
    <span style="{status_style['SKIP']}">SKIP: {counts['SKIP']}</span> &nbsp;|&nbsp;
    <span style="{status_style['PENDING']}">PENDING: {counts['PENDING']}</span> &nbsp;|&nbsp;
    <span style="{status_style['ERROR']}">ERROR: {counts['ERROR']}</span>
  </div>
  <table>
    <thead><tr><th>Suite</th><th>Test</th><th>Status</th><th>Duration</th><th>Message</th></tr></thead>
    <tbody>
{rows_html}    </tbody>
  </table>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    logger.info(f"HTML report written to {output_path}")
