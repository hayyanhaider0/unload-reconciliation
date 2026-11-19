
import unittest

from reconcile import load_json, get_clock_offset, reconcile_weights, normalize_weight, reconcile
from pathlib import Path
import json


class TestReconciliation(unittest.TestCase):

    def test_all_ids_accounted_for(self):
        controller = load_json("controller_unloads.json")
        cloud = load_json("cloud_unloads.json")
        fields = load_json("fields.json")
        trucks = load_json("trucks.json")

        # Run reconciliation directly
        output = reconcile(controller, cloud, fields, trucks)

        # Collect IDs from both original sources
        source_ids = {
            record["id"] for record in controller + cloud
        }

        # Collect IDs from reconciliation output
        output_ids = [record["id"] for record in output]

        # Every unique source ID must appear exactly once
        self.assertEqual(len(output_ids), len(set(output_ids)))
        self.assertEqual(set(output_ids), source_ids)

    def test_cloud_weight_override(self):
        controller = {
            "id": "test-001",
            "weight": 10000,
            "unit": "kg",
            "unloaded_at": "2026-09-14 08:00:00",
            "updated_at": "2026-09-14 08:05:00"
        }

        cloud = {
            "id": "test-001",
            "weight_kg": 10500,
            "unloaded_at": "2026-09-14T09:00:00-05:00",
            "updated_at": "2026-09-14T09:10:00-05:00"
        }

        clock_offset = get_clock_offset(controller, cloud)
        reconciled_records = {}

        reconcile_weights(
            "test-001",
            normalize_weight(controller),
            cloud,
            controller,
            clock_offset,
            reconciled_records
        )

        result = reconciled_records["test-001"]

        self.assertEqual(clock_offset, -3600)
        self.assertEqual(result["status"], "RECONCILED")
        self.assertEqual(result["reason"], "CLOUD_WEIGHT_OVERRIDE")
        self.assertEqual(result["weight_kg"], 10500)


    def test_controller_updated_later(self):
        controller = {
            "id": "test-002",
            "weight": 10000,
            "unit": "kg",
            "unloaded_at": "2026-09-14 08:00:00",
            "updated_at": "2026-09-14 08:15:00"
        }

        cloud = {
            "id": "test-002",
            "weight_kg": 10500,
            "unloaded_at": "2026-09-14T09:00:00-05:00",
            "updated_at": "2026-09-14T09:10:00-05:00"
        }

        clock_offset = get_clock_offset(controller, cloud)
        reconciled_records = {}

        reconcile_weights(
            "test-002",
            normalize_weight(controller),
            cloud,
            controller,
            clock_offset,
            reconciled_records
        )

        result = reconciled_records["test-002"]

        self.assertEqual(clock_offset, -3600)
        self.assertEqual(result["status"], "RECONCILED")
        self.assertEqual(result["reason"], "CONTROLLER_WEIGHT_OVERRIDE")
        self.assertEqual(result["original_cloud_weight_kg"], 10500)
        self.assertEqual(result["weight_kg"], 10000)

if __name__ == "__main__":
    unittest.main()