"""Command-line interface for SEATAUDIT."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import audit, load_inventory, summarize


def _fmt_money(v: float) -> str:
    return f"${v:,.2f}"


def _print_table(result, summary) -> None:
    print(f"SEATAUDIT report  as-of {result.as_of}  "
          f"(idle >= {result.inactive_threshold_days}d)")
    print("=" * 78)
    hdr = f"{'APP':<22}{'SEATS':>8}{'ACTIVE':>8}{'IDLE':>6}{'RECLAIM/mo':>14}  STATUS"
    print(hdr)
    print("-" * 78)
    for a in result.apps:
        status = "OK" if a.sanctioned else "SHADOW-IT"
        idle = a.inactive_seats + a.never_used_seats
        seats = f"{a.assigned_seats}/{a.contracted_seats}" if a.sanctioned else str(a.assigned_seats)
        print(f"{a.name[:22]:<22}{seats:>8}{a.active_seats:>8}{idle:>6}"
              f"{_fmt_money(a.reclaimable_monthly):>14}  {status}")
    print("-" * 78)
    print(f"Total monthly spend : {_fmt_money(summary['total_monthly_spend'])}")
    print(f"Reclaimable / month : {_fmt_money(summary['reclaimable_monthly'])} "
          f"({summary['waste_pct']}% of spend)")
    print(f"Reclaimable / year  : {_fmt_money(summary['reclaimable_annual'])}")
    if result.shadow_it:
        print(f"Shadow-IT apps      : {', '.join(result.shadow_it)}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="SaaS license, seat-usage and shadow-IT auditor.",
    )
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("audit", help="audit a SaaS inventory for seat waste")
    a.add_argument("inventory", help="path to inventory JSON file")
    a.add_argument("--inactive-days", type=int, default=45,
                   help="days idle before a seat is reclaimable (default 45)")
    a.add_argument("--format", choices=("table", "json"), default="table")
    a.add_argument("--summary", action="store_true",
                   help="emit only the CFO rollup summary")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "audit":
        try:
            inventory = load_inventory(args.inventory)
            result = audit(inventory, inactive_days=args.inactive_days)
        except FileNotFoundError:
            print(f"error: inventory file not found: {args.inventory}",
                  file=sys.stderr)
            return 2
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            print(f"error: invalid inventory: {exc}", file=sys.stderr)
            return 1

        summary = summarize(result)
        if args.format == "json":
            payload = summary if args.summary else result.to_dict()
            print(json.dumps(payload, indent=2))
        else:
            if args.summary:
                for k, v in summary.items():
                    print(f"{k}: {v}")
            else:
                _print_table(result, summary)
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
