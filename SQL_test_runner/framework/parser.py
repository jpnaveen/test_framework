import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TestCase:
    name: str
    tags: List[str] = field(default_factory=list)
    skip: Optional[str] = None
    no_compare: bool = False
    setup: str = ""
    query: str = ""
    teardown: str = ""


@dataclass
class TestSuite:
    file_path: str
    suite_setup: str = ""
    suite_teardown: str = ""
    tests: List[TestCase] = field(default_factory=list)


MARKER = re.compile(
    r"^--\s*(SUITE_SETUP|SUITE_TEARDOWN|TAGS|SKIP|NO_COMPARE|TEST|SETUP|QUERY|TEARDOWN)\s*:\s*(.*)?$",
    re.IGNORECASE,
)


def parse_file(file_path: str) -> TestSuite:
    suite = TestSuite(file_path=file_path)
    current_test: Optional[TestCase] = None
    current_section: Optional[str] = None
    buffer: List[str] = []

    def flush(section, buf, test, s):
        text = "\n".join(buf).strip()
        if not section or not text:
            return
        sec = section.upper()
        if sec == "SUITE_SETUP":
            s.suite_setup = text
        elif sec == "SUITE_TEARDOWN":
            s.suite_teardown = text
        elif test:
            if sec == "SETUP":
                test.setup = text
            elif sec == "QUERY":
                test.query = text
            elif sec == "TEARDOWN":
                test.teardown = text

    with open(file_path, "r") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            m = MARKER.match(line.strip())
            if m:
                keyword = m.group(1).upper()
                value = m.group(2).strip() if m.group(2) else ""

                flush(current_section, buffer, current_test, suite)
                buffer = []

                if keyword in ("SUITE_SETUP", "SUITE_TEARDOWN"):
                    current_section = keyword
                elif keyword == "TAGS":
                    if current_test:
                        current_test.tags = [t.strip() for t in value.split(",") if t.strip()]
                    current_section = None
                elif keyword == "SKIP":
                    if current_test:
                        current_test.skip = value or "skipped"
                    current_section = None
                elif keyword == "NO_COMPARE":
                    if current_test:
                        current_test.no_compare = True
                    current_section = None
                elif keyword == "TEST":
                    if current_test:
                        suite.tests.append(current_test)
                    current_test = TestCase(name=value)
                    current_section = None
                elif keyword in ("SETUP", "QUERY", "TEARDOWN"):
                    current_section = keyword
            else:
                if current_section:
                    buffer.append(line)

        flush(current_section, buffer, current_test, suite)
        if current_test:
            suite.tests.append(current_test)

    return suite
