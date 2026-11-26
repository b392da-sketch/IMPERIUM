"""Audit result and error types (P3 contract rev 0.3 sections 8 and 10)."""

from dataclasses import dataclass


class AuditError(Exception):
    """The first fault of an audit journal: an AU code, 1-based line and an
    RFC 6901 path within that line (``""`` for the whole line)."""

    def __init__(self, code, line, path, detail):
        super().__init__(f"{code} line {line} {path!r}: {detail}")
        self.code = code
        self.line = line
        self.path = path
        self.detail = detail


class DrawRecordError(Exception):
    """A fault found by the isolated draw-record validator (ER03)."""

    def __init__(self, code, path, detail=""):
        super().__init__(f"{code} {path!r}: {detail}")
        self.code = code
        self.path = path
        self.detail = detail


@dataclass(frozen=True, slots=True)
class AuditReport:
    fixture: str
    pair: str
    run: tuple | None
    sealed: bool
    roots: int
    cursor: int
    final: str
    terminal: bool
    stages: tuple
    draws: int
    final_chain: str
