
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

    def test_deleted_stays_deleted_after_update(self):
        controller = load_json("controller_unloads.json")
        cloud = load_json("cloud_unloads.json")
        fields = load_json("fields.json")
        trucks = load_json("trucks.json")

        record_id = "d35e13a3-f646-4910-b30a-bf370fb959c4"

        for record in controller:
            if record["id"] == record_id:
                record["updated_at"] = "2026-10-01 12:00:00"

        for record in cloud:
            if record["id"] == record_id:
                record["trashed_at"] = "2026-09-20T12:00:00-05:00"

        output = reconcile(controller, cloud, fields, trucks)
        result = next(record for record in output if record["id"] == record_id)

        self.assertEqual(result["status"], "DELETED")
        self.assertEqual(result["reason"], "CLOUD_DELETION")

    def test_deleted_duplicate_not_counted(self):
        controller = load_json("controller_unloads.json")
        cloud = load_json("cloud_unloads.json")
        fields = load_json("fields.json")
        trucks = load_json("trucks.json")

        # These two IDs represent the same unload
        cloud_id = "1cc33abb-4461-474b-8090-14fed5baef95"
        controller_id = "3ac2ff60-5686-4564-a28c-dd2d1d59d793"

        # Simulate the cloud unload being deleted
        cloud_record = next(r for r in cloud if r["id"] == cloud_id)
        cloud_record["trashed_at"] = "2026-09-20T12:00:00-05:00"

        output = reconcile(controller, cloud, fields, trucks)

        records = {r["id"]: r for r in output}

        self.assertEqual(records[cloud_id]["status"], "DELETED")
        self.assertEqual(records[controller_id]["status"], "DUPLICATE")
        self.assertEqual(records[controller_id]["duplicate_of"], cloud_id)

        # Neither record should contribute to harvest totals
        accepted = [
            r for r in output
            if r["id"] in (cloud_id, controller_id)
            and r["status"] in ("RECONCILED", "WARNING")
        ]

        self.assertEqual(len(accepted), 0)

if __name__ == "__main__":
    unittest.main()