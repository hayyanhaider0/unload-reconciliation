"""
Two starter tests built from real unloads in the data. Save this as tests/test_starter.py and run:

    docker compose run --rm app python -m unittest discover -s tests -v

Both run your whole reconcile() on the real files and then look at what happened to specific ids.
"""
import unittest

from reconcile import load_data, reconcile


def run_reconciliation():
    controller, cloud, fields, trucks = load_data()
    return {record["id"]: record for record in reconcile(controller, cloud, fields, trucks)}


class TestStarter(unittest.TestCase):

    def test_controller_edit_after_cloud_wins(self):
        # Unload 2f5e7232: the cloud says 7925.3 kg and was last edited at 13:07 (-05:00).
        # The controller says 8395.3 kg and was last edited at 12:37 on a clock that runs
        # an hour behind, so 13:37 in cloud time. The controller edit is the newer one.
        results = run_reconciliation()
        record = results["2f5e7232-7a60-4323-b436-78590a7303a8"]

        self.assertEqual(record["status"], "RECONCILED")
        self.assertAlmostEqual(float(record["weight_kg"]), 8395.3, places=1)

    def test_unload_recorded_twice_is_counted_once_and_named(self):
        # 1cc33abb (on both sides) and 3ac2ff60 (controller only): same cart, truck, field,
        # crop and weight, and the same unloaded_at on the same controller clock.
        results = run_reconciliation()
        original = results["1cc33abb-4461-474b-8090-14fed5baef95"]
        copy = results["3ac2ff60-5686-4564-a28c-dd2d1d59d793"]

        self.assertEqual(original["status"], "RECONCILED")
        self.assertNotEqual(copy["status"], "RECONCILED")
        # Whatever you call it, the reason should tell a farmer this is a second copy
        self.assertIn("DUPLICATE", f"{copy['status']} {copy.get('reason')}".upper())


if __name__ == "__main__":
    unittest.main()
