"""Smoke tests for SEATAUDIT. Standard library only, no network."""
import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from seataudit import TOOL_NAME, TOOL_VERSION, audit, load_inventory, summarize
from seataudit.cli import main

DEMO = os.path.join(os.path.dirname(__file__), "..", "demos", "01-basic", "inventory.json")
AS_OF = dt.date(2026, 6, 8)


class TestCore(unittest.TestCase):
    def setUp(self):
        self.inv = load_inventory(DEMO)

    def test_metadata(self):
        self.assertEqual(TOOL_NAME, "seataudit")
        self.assertTrue(TOOL_VERSION)

    def test_audit_runs(self):
        res = audit(self.inv, inactive_days=45, as_of=AS_OF)
        self.assertEqual(res.as_of, "2026-06-08")
        self.assertTrue(res.apps)

    def test_shadow_it_detected(self):
        res = audit(self.inv, inactive_days=45, as_of=AS_OF)
        self.assertIn("Notion", res.shadow_it)
        self.assertIn("Grammarly", res.shadow_it)
        self.assertNotIn("Salesforce", res.shadow_it)

    def test_salesforce_classification(self):
        res = audit(self.inv, inactive_days=45, as_of=AS_OF)
        sf = next(a for a in res.apps if a.name == "Salesforce")
        # 12 assigned of 25 contracted
        self.assertEqual(sf.assigned_seats, 12)
        self.assertEqual(sf.contracted_seats, 25)
        # idle past 45d: dan, eve, finn, leo (4) + never-used gail (1)
        self.assertEqual(sf.inactive_seats, 4)
        self.assertEqual(sf.never_used_seats, 1)
        self.assertEqual(sf.active_seats, 7)
        self.assertTrue(sf.reclaimable_monthly > 0)

    def test_annual_billing_normalized(self):
        res = audit(self.inv, inactive_days=45, as_of=AS_OF)
        figma = next(a for a in res.apps if a.name == "Figma")
        # 540/yr annual -> 45/mo per seat
        self.assertAlmostEqual(figma.cost_per_seat_monthly, 45.0, places=2)

    def test_reclaim_totals_consistent(self):
        res = audit(self.inv, inactive_days=45, as_of=AS_OF)
        total = sum(a.reclaimable_monthly for a in res.apps)
        self.assertAlmostEqual(total, res.reclaimable_monthly, places=2)
        self.assertAlmostEqual(res.reclaimable_annual,
                               res.reclaimable_monthly * 12, places=2)

    def test_summary_shape(self):
        res = audit(self.inv, inactive_days=45, as_of=AS_OF)
        s = summarize(res)
        for key in ("sanctioned_apps", "shadow_it_apps", "total_monthly_spend",
                    "reclaimable_monthly", "reclaimable_annual", "waste_pct"):
            self.assertIn(key, s)
        self.assertEqual(s["shadow_it_apps"], 2)

    def test_inactive_threshold_changes_result(self):
        loose = audit(self.inv, inactive_days=365, as_of=AS_OF)
        strict = audit(self.inv, inactive_days=10, as_of=AS_OF)
        self.assertGreaterEqual(strict.reclaimable_monthly,
                                loose.reclaimable_monthly)

    def test_bad_inventory_raises(self):
        with self.assertRaises(ValueError):
            audit({"apps": []}, as_of=AS_OF)


class TestCli(unittest.TestCase):
    def test_json_output(self):
        rc = main(["audit", DEMO, "--format", "json"])
        self.assertEqual(rc, 0)

    def test_table_output(self):
        rc = main(["audit", DEMO])
        self.assertEqual(rc, 0)

    def test_summary_json(self):
        rc = main(["audit", DEMO, "--format", "json", "--summary"])
        self.assertEqual(rc, 0)

    def test_missing_file_nonzero(self):
        rc = main(["audit", "/no/such/file.json"])
        self.assertEqual(rc, 2)

    def test_invalid_json_nonzero(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{ not valid json ")
            path = fh.name
        try:
            rc = main(["audit", path])
            self.assertEqual(rc, 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
