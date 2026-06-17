"""Secret-pattern guardrail for memory writes.

Runs before every write so credentials never land in a markdown file that git
will happily share. Detection is regex-based and intentionally conservative —
it catches well-known credential shapes (cloud keys, provider tokens, private
keys, obvious ``secret=value`` assignments) without flagging ordinary prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["GuardrailResult", "scan_for_secrets"]


# (label, pattern) pairs. Labels name the kind of secret for the rejection
# report; patterns match the credential shape, not the surrounding text.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b")),
    (
        "credential-assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|"
            r"auth[_-]?token|client[_-]?secret)\b\s*[:=]\s*['\"]?[^\s'\"]{6,}"
        ),
    ),
]


@dataclass
class GuardrailResult:
    """Result of scanning content for secrets.

    ``ok`` is ``True`` when nothing matched. ``findings`` lists the labels of the
    patterns that fired (no secret values, so the report itself is safe to log).
    """

    ok: bool
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "findings": list(self.findings)}


def scan_for_secrets(content: str) -> GuardrailResult:
    """Scan *content* for credential patterns.

    Returns a passing result for clean content, or a failing one naming each
    pattern that matched.
    """
    findings: list[str] = []
    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(content):
            findings.append(label)
    return GuardrailResult(ok=not findings, findings=findings)
