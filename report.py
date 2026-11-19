
import os
import psycopg

# Constants
DATABASE_URL = os.environ["DATABASE_URL"]


# Functions

# Retrieves and prints the total weight and number of accepted unloads for each field
def print_field_summary(cursor):
    cursor.execute("""
        SELECT
            f.name,
            COUNT(u.id) AS unload_count,
            COALESCE(SUM(u.weight_kg), 0) AS total_weight
        FROM fields f
        LEFT JOIN unloads u
            ON f.id = u.field_id
            AND u.status IN ('RECONCILED', 'WARNING')
        GROUP BY f.id, f.name
        ORDER BY f.name
    """)

    fields = cursor.fetchall()

    print("\nFIELD SUMMARY")
    print("=" * 65)

    print(f"{'Field':<25}{'Unloads':>12}{'Weight (kg)':>20}")
    print("-" * 65)

    for name, unload_count, weight_kg in fields:
        print(
            f"{name:<25}"
            f"{unload_count:>12}"
            f"{weight_kg:>20,.1f}"
        )

    print("-" * 65)
    print(
        f"{'TOTAL':<25}"
        f"{sum(field[1] for field in fields):>12}"
        f"{sum(field[2] for field in fields):>20,.1f}"
    )


# Retrieves and prints all flagged records and their reasons
def print_unresolved_records(cursor):
    cursor.execute("""
        SELECT
            u.id,
            u.reason,
            u.weight_kg,
            u.unresolved_field_id,
            u.controller_record,
            u.cloud_record
        FROM unloads u
        WHERE u.status = 'FLAGGED'
        ORDER BY u.reason, u.id
    """)

    records = cursor.fetchall()

    print("\nUNRESOLVED RECORDS")
    print("=" * 80)

    if not records:
        print("No unresolved records.")
        return

    for record_id, reason, weight_kg, unresolved_field_id, controller, cloud in records:
        print(f"ID:      {record_id}")
        print(f"Reason:  {reason}")

        # Display details depending on why the record was flagged
        if reason == "WEIGHT_MISMATCH":
            controller_weight = controller.get("weight") if controller else None
            controller_unit = controller.get("unit", "") if controller else ""
            cloud_weight = cloud.get("weight_kg") if cloud else None

            print(
                f"Details: Controller: {controller_weight} {controller_unit}"
                f" | Cloud: {cloud_weight} kg"
            )

        elif reason == "TRUCK_CAPACITY_EXCEEDED":
            print(f"Details: Weight: {weight_kg} kg | Truck capacity exceeded")

        elif reason == "UNKNOWN_FIELD":
            print(f"Details: Unknown field ID: {unresolved_field_id}")

        elif reason == "MISSING_UNIT":
            print("Details: Controller weight unit is missing")

        else:
            print("Details: Manual review required")

        print("-" * 80)


# Retrieves and prints records that were automatically overridden or deleted
def print_automatic_decisions(cursor):
    cursor.execute("""
        SELECT
            id, status, reason, controller_record, cloud_record, duplicate_of
        FROM unloads
        WHERE (status = 'RECONCILED' AND reason IS NOT NULL)
           OR status in ('DELETED', 'DUPLICATE') 
        ORDER BY status, reason, id
    """)

    records = cursor.fetchall()

    print("\nAUTOMATIC RECONCILIATION DECISIONS")
    print("=" * 80)

    if not records:
        print("No automatic decisions.")
        return

    for record_id, status, reason, controller, cloud, duplicate_of in records:
        print(f"ID:       {record_id}")
        print(f"Status:   {status}")
        print(f"Decision: {reason}")

        if reason == "CLOUD_WEIGHT_OVERRIDE":
            controller_weight = controller.get("weight") if controller else None
            controller_unit = controller.get("unit", "") if controller else ""
            cloud_weight = cloud.get("weight_kg") if cloud else None

            print(
                f"Details:  Controller: {controller_weight} {controller_unit}"
                f" | Cloud: {cloud_weight} kg"
            )

        elif status == "DELETED":
            print("Details:  Record marked as deleted in the cloud")

        elif status == "DUPLICATE":
            print(f"Duplicate of: {duplicate_of}")

        print("-" * 80)

def print_warnings(cursor):
    cursor.execute("""
        SELECT u.id, u.weight_kg, u.reason, t.name, t.capacity_kg
        FROM unloads AS u
        JOIN trucks AS t ON u.truck_id = t.id
        WHERE u.status = 'WARNING'
        ORDER BY u.id
    """)

    records = cursor.fetchall()

    print("\nWARNINGS")
    print("=" * 80)

    if not records:
        print("No warnings.")
        return

    for record in records:
        record_id, weight_kg, reason, truck_name, capacity_kg = record

        print(f"ID:      {record_id}")
        print(f"Warning: {reason}")
        print(f"Truck:   {truck_name}")
        print(
            f"Details: Weight: {weight_kg:.1f} kg | "
            f"Truck capacity: {capacity_kg:.1f} kg"
        )
        print("-" * 80)

# Retrieves and prints the number of records for each reconciliation status
def print_reconciliation_audit(cursor):
    cursor.execute("""
        SELECT status, COUNT(*)
        FROM unloads
        GROUP BY status
    """)

    audit = dict(cursor.fetchall())

    print("\nRECONCILIATION AUDIT")
    print("=" * 60)

    print(f"{'Accepted':<15}{'Flagged':<15}{'Deleted':<15}{'Duplicates':<15}")
    print("-" * 60)

    print(
        f"{audit.get('RECONCILED', 0) + audit.get('WARNING', 0):<15}"
        f"{audit.get('FLAGGED', 0):<15}"
        f"{audit.get('DELETED', 0):<15}"
        f"{audit.get('DUPLICATE', 0):<15}"
    )

    print("-" * 60)
    print(f"Total records: {sum(audit.values())}")

    # Count current and previous reconciliation reasons
    cursor.execute("""
        SELECT reason, COUNT(*)
        FROM (
            SELECT reason
            FROM unloads
            WHERE reason IS NOT NULL

            UNION ALL

            SELECT previous_reason AS reason
            FROM unloads
            WHERE previous_reason IS NOT NULL
        ) AS decisions
        GROUP BY reason
        ORDER BY reason
    """)

    decisions = cursor.fetchall()

    # Print reconciliation decisions and their counts
    if decisions:
        print("\nRECONCILIATION DECISIONS")
        print("-" * 60)

        for reason, count in decisions:
            print(f"{reason:<35}{count:>5}")

# Connects to PostgreSQL and prints the reconciliation report
def main():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            print("=" * 80)
            print("UNLOAD RECONCILIATION REPORT")
            print("=" * 80)

            print_field_summary(cursor)
            print_unresolved_records(cursor)
            print_automatic_decisions(cursor)
            print_warnings(cursor)
            print_reconciliation_audit(cursor)


if __name__ == "__main__":
    main()
