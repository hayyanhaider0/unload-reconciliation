
from datetime import datetime as dt, timedelta
from pathlib import Path
from enum import StrEnum
import json


# Enumerations
class ReconciliationStatus(StrEnum):
    RECONCILED = "RECONCILED"
    FLAGGED = "FLAGGED"
    DELETED = "DELETED"

class ReconciliationIssue(StrEnum):
    MISSING_UNIT = "MISSING_UNIT"
    WEIGHT_MISMATCH = "WEIGHT_MISMATCH"
    # Used when the cloud weight is updated after the controller weight
    CLOUD_WEIGHT_OVERRIDE = "CLOUD_WEIGHT_OVERRIDE"
    CONTROLLER_ONLY_IMPORT = "CONTROLLER_ONLY_IMPORT"
    CLOUD_ONLY_IMPORT = "CLOUD_ONLY_IMPORT"
    # Used when the unload weight is higher than the truck's capacity
    TRUCK_CAPACITY_EXCEEDED = "TRUCK_CAPACITY_EXCEEDED"
    # Field reference doesn't exist in fields.json
    UNKNOWN_FIELD = "UNKNOWN_FIELD"


# Constants
LB_TO_KG = 0.45359237
DATA_DIR = Path(__file__).parent / "data"


# Functions
def load_json(file_name):
    with open(DATA_DIR / file_name, "r") as f:
        return json.load(f)


# Loads data into variables and returns them
def load_data():
    controller_unloads = load_json("controller_unloads.json")
    cloud_unloads = load_json("cloud_unloads.json")
    fields = load_json("fields.json")
    trucks = load_json("trucks.json")

    return controller_unloads, cloud_unloads, fields, trucks


# Normalizes the weight from controller records to kgs. If a unit is missing, returns None
def normalize_weight(record):
    weight = record.get("weight")
    unit = record.get("unit")

    match unit:
        case "kg":
            return weight
        case "lb":
            return weight * LB_TO_KG
        case _:
            return None


# Calculates the clock offset in seconds between the controller and cloud records based on their unloaded_at timestamps
# The assumption is that the unload would have happened at the same time, but the controller may have an incorrectly set clock
def get_clock_offset(controller_record, cloud_record):
    controller_time = dt.fromisoformat(controller_record["unloaded_at"])
    cloud_time = dt.fromisoformat(cloud_record["unloaded_at"])

    # Assume the controller uses the same UTC offset as the cloud
    controller_time = controller_time.replace(tzinfo=cloud_time.tzinfo)

    return (controller_time - cloud_time).total_seconds()

# Determines if the cloud record was updated later than the controller record, taking into account the clock offset
def is_cloud_updated_later(controller_record, cloud_record, clock_offset):
    controller_updated_at = dt.fromisoformat(controller_record["updated_at"])
    cloud_updated_at = dt.fromisoformat(cloud_record["updated_at"])

    # Assume the controller uses the same UTC offset as the cloud
    controller_updated_at = controller_updated_at.replace(tzinfo=cloud_updated_at.tzinfo)

    # Correct the controller timestamp using the calculated clock offset
    corrected_controller_time = controller_updated_at - timedelta(seconds=clock_offset)

    # Check if the cloud was updated after the controller
    return cloud_updated_at > corrected_controller_time

# Validates if the weight of a record does not exceed the truck's capacity
def validate_truck_capacity(record, trucks_by_id):
    truck = trucks_by_id.get(record["truck_id"])

    if truck is None:
        return False

    return record["weight_kg"] <= truck["capacity_kg"]


# Updates a record's status while preserving its previous reason
def mark_flagged(record, reason):
    if record.get("reason") is not None:
        record["previous_reason"] = record["reason"]

    record["status"] = ReconciliationStatus.FLAGGED.value
    record["reason"] = reason


# Creates a flagged record using the available controller or cloud data
def flag_record(record_id, reason, controller_record, cloud_record, reconciled_records, controller_weight_kg=None):
    source_record = cloud_record if cloud_record is not None else controller_record

    reconciled_records[record_id] = {
        **source_record,
        "weight_kg": cloud_record["weight_kg"] if cloud_record is not None else controller_weight_kg,
        "status": ReconciliationStatus.FLAGGED.value,
        "reason": reason
    }


# If records are trashed, they are marked as deleted
def reconcile_deletions(record_id, cloud_record, reconciled_records):
    if cloud_record.get("trashed_at") is not None:
        reconciled_records[record_id] = {
            **cloud_record,
            "status": ReconciliationStatus.DELETED.value,
            "reason": "CLOUD_DELETION"
        }
        return True

    return False


# Reconciles the weights between controller and cloud records, taking into account the clock offset and storing the results in reconciled_records
def reconcile_weights(record_id, controller_weight_kg, cloud_record, controller_record, clock_offset, reconciled_records):
    if round(controller_weight_kg, 1) != round(cloud_record["weight_kg"], 1):
        if is_cloud_updated_later(controller_record, cloud_record, clock_offset):
            # Store successfully reconciled records using cloud data
            reconciled_records[record_id] = {
                **cloud_record,
                "status": ReconciliationStatus.RECONCILED.value,
                "reason": ReconciliationIssue.CLOUD_WEIGHT_OVERRIDE.value,
                "original_controller_weight_kg": controller_weight_kg,
                "clock_offset_seconds": clock_offset
            }
        else:
            # Store flagged records with weight mismatch
            flag_record(
                record_id,
                ReconciliationIssue.WEIGHT_MISMATCH.value,
                controller_record,
                cloud_record,
                reconciled_records
            )

            reconciled_records[record_id]["original_controller_weight_kg"] = controller_weight_kg
            reconciled_records[record_id]["clock_offset_seconds"] = clock_offset
    else:
        # Store successfully reconciled records using cloud data
        reconciled_records[record_id] = {
            **cloud_record,
            "status": ReconciliationStatus.RECONCILED.value,
            "original_controller_weight_kg": controller_weight_kg,
            "clock_offset_seconds": clock_offset
        }


# Reconciles records that exist in both sources
def reconcile_matched_ids(matched_ids, controller_by_id, cloud_by_id, reconciled_records):
    for record_id in matched_ids:
        controller_record = controller_by_id[record_id]
        cloud_record = cloud_by_id[record_id]

        if reconcile_deletions(record_id, cloud_record, reconciled_records):
            continue

        # Normalize controller weight
        controller_weight_kg = normalize_weight(controller_record)

        # Calculate timestamp offset
        clock_offset = get_clock_offset(controller_record, cloud_record)

        # Compare weights
        if controller_weight_kg is None:
            flag_record(
                record_id,
                ReconciliationIssue.MISSING_UNIT.value,
                controller_record,
                cloud_record,
                reconciled_records
            )
            continue

        reconcile_weights(
            record_id,
            controller_weight_kg,
            cloud_record,
            controller_record,
            clock_offset,
            reconciled_records
        )


# Reconciles records that exist only on the controller
def reconcile_controller_only_records(controller_only, controller_by_id, cloud_by_id, reconciled_records):
    for record_id in controller_only:
        controller_record = controller_by_id[record_id]
        controller_weight_kg = normalize_weight(controller_record)

        if controller_weight_kg is None:
            flag_record(
                record_id,
                ReconciliationIssue.MISSING_UNIT.value,
                controller_record,
                None,
                reconciled_records
            )
            continue

        reconciled_records[record_id] = {
            **controller_record,
            "weight_kg": controller_weight_kg,
            "status": ReconciliationStatus.FLAGGED.value,
            "reason": ReconciliationIssue.CONTROLLER_ONLY_IMPORT.value,
            "clock_offset_seconds": None
        }


# Reconciles records that exist only in the cloud
def reconcile_cloud_only_records(cloud_only, cloud_by_id, reconciled_records):
    for record_id in cloud_only:
        cloud_record = cloud_by_id[record_id]

        if reconcile_deletions(record_id, cloud_record, reconciled_records):
            continue

        reconciled_records[record_id] = {
            **cloud_record,
            "status": ReconciliationStatus.FLAGGED.value,
            "reason": ReconciliationIssue.CLOUD_ONLY_IMPORT.value,
            "clock_offset_seconds": None
        }


# Validates reconciled records against their truck capacities
def validate_truck_capacities(reconciled_records, trucks_by_id):
    for record in reconciled_records.values():
        if record["status"] != ReconciliationStatus.RECONCILED.value:
            continue

        if not validate_truck_capacity(record, trucks_by_id):
            mark_flagged(record, ReconciliationIssue.TRUCK_CAPACITY_EXCEEDED.value)


# Validates that every unload references an existing field
def validate_field_references(reconciled_records, fields_by_id):
    for record in reconciled_records.values():
        if record["field_id"] not in fields_by_id:
            mark_flagged(record, ReconciliationIssue.UNKNOWN_FIELD.value)


# Reconciles input records and returns the results without accessing the database
def reconcile(controller_unloads, cloud_unloads, fields, trucks):
    # Quick lookups for fields, trucks, and unloads by their IDs
    fields_by_id = {field["id"]: field for field in fields}
    trucks_by_id = {truck["id"]: truck for truck in trucks}
    controller_by_id = {
        record["id"]: record for record in controller_unloads
    }
    cloud_by_id = {
        record["id"]: record for record in cloud_unloads
    }

    # Identify matched, controller-only, and cloud-only records
    matched_ids = controller_by_id.keys() & cloud_by_id.keys()
    controller_only = controller_by_id.keys() - cloud_by_id.keys()
    cloud_only = cloud_by_id.keys() - controller_by_id.keys()

    reconciled_records = {}

    # Reconcile records
    reconcile_matched_ids(
        matched_ids,
        controller_by_id,
        cloud_by_id,
        reconciled_records
    )

    reconcile_controller_only_records(
        controller_only,
        controller_by_id,
        cloud_by_id,
        reconciled_records,
    )

    reconcile_cloud_only_records(
        cloud_only,
        cloud_by_id,
        reconciled_records
    )

    # Validate reconciled records
    validate_truck_capacities(reconciled_records, trucks_by_id)
    validate_field_references(reconciled_records, fields_by_id)

    # Verify that every unique source ID is accounted for
    source_ids = controller_by_id.keys() | cloud_by_id.keys()
    assert set(reconciled_records) == source_ids

    # Return reconciliation results
    return [
        {
            **record,
            "controller_record": controller_by_id.get(record["id"]),
            "cloud_record": cloud_by_id.get(record["id"])
        }
        for record in reconciled_records.values()
    ]


# Loads the input files and starts reconciliation
def main():
    controller_unloads, cloud_unloads, fields, trucks = load_data()

    results = reconcile(controller_unloads, cloud_unloads, fields, trucks)

    print("Reconciliation complete.")
    return results


if __name__ == "__main__":
    main()
