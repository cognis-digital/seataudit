"""Core engine for SEATAUDIT.

Input is a JSON inventory describing sanctioned SaaS apps, their per-seat cost
and contracted seat count, plus a flat list of seat assignments with last-used
timestamps. The engine computes utilization, classifies each seat, detects
shadow-IT (apps with seats but no catalog entry), and produces a dollar-quantified
reclaim plan.

Pure standard-library. No network, no third-party deps.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# A seat is considered "stale" / reclaimable once it has been inactive this long.
DEFAULT_INACTIVE_DAYS = 45


def _parse_date(value: Optional[str]) -> Optional[_dt.date]:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return _dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date format: {value!r}")


@dataclass
class Seat:
    """A single license assignment to a user for an app."""

    app: str
    user: str
    last_active: Optional[_dt.date]
    assigned: Optional[_dt.date] = None

    def days_idle(self, as_of: _dt.date) -> Optional[int]:
        if self.last_active is None:
            return None
        return (as_of - self.last_active).days


@dataclass
class App:
    """A sanctioned SaaS application from the license catalog."""

    name: str
    cost_per_seat: float
    contracted_seats: int
    billing: str = "monthly"  # monthly | annual
    owner: str = ""

    def monthly_cost_per_seat(self) -> float:
        if self.billing == "annual":
            return self.cost_per_seat / 12.0
        return self.cost_per_seat


@dataclass
class AppAudit:
    name: str
    sanctioned: bool
    cost_per_seat_monthly: float
    contracted_seats: int
    assigned_seats: int
    active_seats: int
    inactive_seats: int
    never_used_seats: int
    owner: str
    # dollars
    unused_contract_cost: float  # paid-for seats nobody is assigned
    inactive_seat_cost: float    # assigned but idle past threshold
    reclaimable_monthly: float
    inactive_users: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        for k in ("cost_per_seat_monthly", "unused_contract_cost",
                  "inactive_seat_cost", "reclaimable_monthly"):
            d[k] = round(d[k], 2)
        return d


@dataclass
class AuditResult:
    as_of: str
    inactive_threshold_days: int
    apps: List[AppAudit]
    shadow_it: List[str]
    total_monthly_spend: float
    reclaimable_monthly: float
    reclaimable_annual: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "inactive_threshold_days": self.inactive_threshold_days,
            "apps": [a.to_dict() for a in self.apps],
            "shadow_it": self.shadow_it,
            "total_monthly_spend": round(self.total_monthly_spend, 2),
            "reclaimable_monthly": round(self.reclaimable_monthly, 2),
            "reclaimable_annual": round(self.reclaimable_annual, 2),
        }


def load_inventory(path: str) -> Dict[str, Any]:
    """Load and validate an inventory JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("inventory must be a JSON object")
    if "apps" not in data or "seats" not in data:
        raise ValueError("inventory must contain 'apps' and 'seats' keys")
    return data


def _build_apps(raw_apps: List[Dict[str, Any]]) -> Dict[str, App]:
    apps: Dict[str, App] = {}
    for a in raw_apps:
        name = a["name"]
        apps[name] = App(
            name=name,
            cost_per_seat=float(a["cost_per_seat"]),
            contracted_seats=int(a.get("contracted_seats", 0)),
            billing=a.get("billing", "monthly"),
            owner=a.get("owner", ""),
        )
    return apps


def _build_seats(raw_seats: List[Dict[str, Any]]) -> List[Seat]:
    seats: List[Seat] = []
    for s in raw_seats:
        seats.append(Seat(
            app=s["app"],
            user=s["user"],
            last_active=_parse_date(s.get("last_active")),
            assigned=_parse_date(s.get("assigned")),
        ))
    return seats


def audit(
    inventory: Dict[str, Any],
    inactive_days: int = DEFAULT_INACTIVE_DAYS,
    as_of: Optional[_dt.date] = None,
) -> AuditResult:
    """Run the full seat/license audit."""
    if inactive_days < 0:
        raise ValueError("inactive_days must be >= 0")
    if as_of is None:
        as_of = _parse_date(inventory.get("as_of")) or _dt.date.today()

    if "seats" not in inventory:
        raise ValueError("inventory must contain a 'seats' key")
    apps = _build_apps(inventory["apps"])
    seats = _build_seats(inventory["seats"])

    # Group seats by app
    by_app: Dict[str, List[Seat]] = {}
    for seat in seats:
        by_app.setdefault(seat.app, []).append(seat)

    app_audits: List[AppAudit] = []
    shadow_it: List[str] = []
    total_monthly = 0.0
    total_reclaim = 0.0

    # Sanctioned apps (have a catalog entry)
    for name, app in apps.items():
        seat_list = by_app.get(name, [])
        assigned = len(seat_list)
        active = inactive = never = 0
        inactive_users: List[str] = []
        for seat in seat_list:
            idle = seat.days_idle(as_of)
            if idle is None:
                never += 1
                inactive_users.append(seat.user)
            elif idle >= inactive_days:
                inactive += 1
                inactive_users.append(seat.user)
            else:
                active += 1

        cps = app.monthly_cost_per_seat()
        billed_seats = max(app.contracted_seats, assigned)
        monthly_spend = billed_seats * cps
        total_monthly += monthly_spend

        # Empty contracted seats = paid for, nobody assigned.
        unused_contract = max(app.contracted_seats - assigned, 0)
        unused_contract_cost = unused_contract * cps
        # Assigned-but-idle seats are reclaimable on renewal.
        inactive_seat_cost = (inactive + never) * cps
        reclaimable = unused_contract_cost + inactive_seat_cost
        total_reclaim += reclaimable

        app_audits.append(AppAudit(
            name=name,
            sanctioned=True,
            cost_per_seat_monthly=cps,
            contracted_seats=app.contracted_seats,
            assigned_seats=assigned,
            active_seats=active,
            inactive_seats=inactive,
            never_used_seats=never,
            owner=app.owner,
            unused_contract_cost=unused_contract_cost,
            inactive_seat_cost=inactive_seat_cost,
            reclaimable_monthly=reclaimable,
            inactive_users=sorted(inactive_users),
        ))

    # Shadow IT: apps with seat assignments but no catalog entry.
    for name, seat_list in by_app.items():
        if name in apps:
            continue
        shadow_it.append(name)
        active = inactive = never = 0
        inactive_users = []
        for seat in seat_list:
            idle = seat.days_idle(as_of)
            if idle is None:
                never += 1
                inactive_users.append(seat.user)
            elif idle >= inactive_days:
                inactive += 1
                inactive_users.append(seat.user)
            else:
                active += 1
        app_audits.append(AppAudit(
            name=name,
            sanctioned=False,
            cost_per_seat_monthly=0.0,
            contracted_seats=0,
            assigned_seats=len(seat_list),
            active_seats=active,
            inactive_seats=inactive,
            never_used_seats=never,
            owner="",
            unused_contract_cost=0.0,
            inactive_seat_cost=0.0,
            reclaimable_monthly=0.0,
            inactive_users=sorted(inactive_users),
        ))

    app_audits.sort(key=lambda a: a.reclaimable_monthly, reverse=True)
    shadow_it.sort()

    return AuditResult(
        as_of=as_of.isoformat(),
        inactive_threshold_days=inactive_days,
        apps=app_audits,
        shadow_it=shadow_it,
        total_monthly_spend=total_monthly,
        reclaimable_monthly=total_reclaim,
        reclaimable_annual=total_reclaim * 12.0,
    )


def summarize(result: AuditResult) -> Dict[str, Any]:
    """Compact CFO-facing rollup."""
    sanctioned = [a for a in result.apps if a.sanctioned]
    pct = 0.0
    if result.total_monthly_spend > 0:
        pct = result.reclaimable_monthly / result.total_monthly_spend * 100.0
    return {
        "sanctioned_apps": len(sanctioned),
        "shadow_it_apps": len(result.shadow_it),
        "total_monthly_spend": round(result.total_monthly_spend, 2),
        "reclaimable_monthly": round(result.reclaimable_monthly, 2),
        "reclaimable_annual": round(result.reclaimable_annual, 2),
        "waste_pct": round(pct, 1),
    }
