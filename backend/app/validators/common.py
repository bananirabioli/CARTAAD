from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.i18n import t

Severity = Literal["block", "warn", "info"]


@dataclass
class Finding:
    validator: str  # numeric | claims | style | compat | labels
    code: str
    severity: Severity
    message: str
    rule_id: str | None = None  # HR-xx when the finding enforces a hard rule
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def finding(validator: str, code: str, severity: Severity, rule_id: str | None = None, detail: dict[str, Any] | None = None, **params: Any) -> Finding:
    return Finding(validator, code, severity, t(f"validators.{validator}.{code}", **params), rule_id, detail or {})


def status_of(findings: list[Finding]) -> str:
    if any(f.severity == "block" for f in findings):
        return "block"
    if any(f.severity == "warn" for f in findings):
        return "warn"
    return "ok"
