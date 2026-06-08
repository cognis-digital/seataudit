"""SEATAUDIT - SaaS license, seat-usage and shadow-IT auditor.

CFO-friendly auditing of SaaS spend: finds wasted seats (paid but inactive),
over-provisioned apps, shadow-IT (apps in use but not in the sanctioned
catalog), and quantifies the dollars you can reclaim.
"""
from .core import (
    App,
    Seat,
    AuditResult,
    load_inventory,
    audit,
    summarize,
)

TOOL_NAME = "seataudit"
TOOL_VERSION = "1.0.0"

__all__ = [
    "App",
    "Seat",
    "AuditResult",
    "load_inventory",
    "audit",
    "summarize",
    "TOOL_NAME",
    "TOOL_VERSION",
]
