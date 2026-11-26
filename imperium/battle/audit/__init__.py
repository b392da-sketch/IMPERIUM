"""IMPERIUM battle audit v1: independent structural verification of audit
journals and the isolated draw-record validator (P3 contract rev 0.3
sections 8 and 10).

This package never imports ``imperium.battle.engine`` (guard G-P3-1).
"""

from .drawcheck import check_draw_records
from .errors import AuditError, AuditReport, DrawRecordError
from .refold import preflight, verify

__all__ = ["verify", "AuditReport", "AuditError", "check_draw_records", "DrawRecordError",
           "preflight"]
