"""Layer 0: the P1 domain error contract (contract 12.6).

Every error raised for supported input is a ``DomainError``. It subclasses
``Exception`` and deliberately not ``ValueError``, so a caller's
``except ValueError`` never swallows a domain diagnostic by accident.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Violation:
    """One failed clause: its id, a path and a fixed detail string."""

    clause: str
    path: str
    detail: str


def violation_key(violation):
    """Sort key of a violation: ``(clause, path)`` (contract 10.0)."""
    return (violation.clause, violation.path)


class DomainError(Exception):
    """Base class of every P1 diagnostic."""


class InvalidValue(DomainError):
    """A local (T) clause or an argument check failed."""

    def __init__(self, clause, path, detail):
        super().__init__(clause, path, detail)
        self.clause = clause
        self.path = path
        self.detail = detail

    def __str__(self):
        return f"{self.clause} at {self.path!r}: {self.detail}"


class InvalidState(DomainError):
    """One or more cross-record clauses failed; violations are sorted."""

    def __init__(self, violations):
        super().__init__(violations)
        self.violations = violations

    def __str__(self):
        return "; ".join(f"{v.clause} at {v.path!r}: {v.detail}" for v in self.violations)


class UnknownId(DomainError):
    """A well-typed identifier outside the function's domain."""

    def __init__(self, id):
        super().__init__(id)
        self.id = id


class DecodeError(DomainError):
    """A decoding rejection with a deterministic code (contract 13.1)."""

    def __init__(self, code, path, detail, offset, violations):
        super().__init__(code, path, detail, offset, violations)
        self.code = code
        self.path = path
        self.detail = detail
        self.offset = offset
        self.violations = violations

    def __str__(self):
        return f"{self.code} at {self.path!r} (offset {self.offset}): {self.detail}"
