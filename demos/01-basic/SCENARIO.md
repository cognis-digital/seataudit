# Demo 01 - Basic SaaS seat audit

A 40-person startup hands you an export of their SaaS license inventory and
seat-usage data. The CFO wants to know how much they're wasting before the
upcoming renewals.

## Input

`inventory.json` describes:

- **apps**: the sanctioned license catalog (cost per seat, billing cadence,
  contracted seat count, owning team).
- **seats**: who has a license for which app, and when they last logged in.

Note that some seat rows reference apps **not** in the catalog
(`Notion`, `Grammarly`) - that is shadow-IT picked up from SSO/expense logs.

## Run it

```
python -m seataudit audit demos/01-basic/inventory.json
python -m seataudit audit demos/01-basic/inventory.json --format json
python -m seataudit audit demos/01-basic/inventory.json --summary
```

## What to look for

- **Salesforce** is contracted for 25 seats but only 12 are assigned and
  several of those are idle past 45 days - the single biggest reclaim line.
- **Figma** has fully unused contracted seats.
- **Notion** and **Grammarly** surface as **SHADOW-IT** (in use, not sanctioned).
- The footer quantifies total monthly spend and reclaimable dollars per
  month / per year, with waste as a percentage of spend.

The `as_of` date is pinned in the file so results are deterministic.
