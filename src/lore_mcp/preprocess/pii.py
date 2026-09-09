"""PII detection for preprocessing pipeline. See E12.05.

Report-only — flags patterns, does not remove them.
Vectors are not anonymization.
"""

import re

_SAFE_DOMAINS = {"example.com", "example.org", "example.net",
                 "test.com", "test.org", "localhost"}

_PATTERNS = [
    ("email", re.compile(
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
    )),
    ("ip", re.compile(
        r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b"
    )),
    ("api_key", re.compile(
        r"\b(?:sk-|api[_-]?key[=: ]+)[a-zA-Z0-9]{20,}\b", re.IGNORECASE
    )),
    ("internal_domain", re.compile(
        r"\b[a-zA-Z0-9.-]+\.(?:internal|corp|local|intranet)\b"
    )),
]


def detect_pii(text: str) -> list[dict]:
    """Scan text for PII patterns. Returns list of findings."""
    findings = []
    lines = text.split("\n")

    for line_num, line in enumerate(lines, 1):
        for pii_type, pattern in _PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(0)
                if pii_type == "email":
                    domain = value.split("@")[1].lower()
                    if domain in _SAFE_DOMAINS:
                        continue
                findings.append({
                    "type": pii_type,
                    "match": value,
                    "line": line_num,
                })

    return findings
