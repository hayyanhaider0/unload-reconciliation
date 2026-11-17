
import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb


# Constants
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_URL = os.environ["DATABASE_URL"]


# Functions

# Loads a JSON file and returns its contents
def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


# Imports fields, trucks, and reconciled unloads into PostgreSQL
def import_data(unloads):
    fields = load_json(DATA_DIR / "fields.json")
    trucks = load_json(DATA_DIR / "trucks.json")

    # Used to check if unloads reference an existing field
    valid_field_ids = {field["id"] for field in fields}

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:

            # Create database tables
            schema = (BASE_DIR / "database" / "schema.sql").read_text()
            cursor.execute(schema)

            # Import fields
            for field in fields:
                cursor.execute("""
                    INSERT INTO fields (id, name, area_ha, crop)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        area_ha = EXCLUDED.area_ha,
                        crop = EXCLUDED.crop
                """, (
                    field["id"],
                    field["name"],
                    field["area_ha"],
                    field["crop"]
                ))

            # Import trucks
            for truck in trucks:
                cursor.execute("""
                    INSERT INTO trucks (id, name, capacity_kg)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        capacity_kg = EXCLUDED.capacity_kg
                """, (
                    truck["id"],
                    truck["name"],
                    truck["capacity_kg"]
                ))

            # Import reconciled unloads
            for unload in unloads:
                field_id = unload["field_id"]

                # Preserve unknown field IDs without violating the foreign key
                valid_field_id = field_id if field_id in valid_field_ids else None
                unresolved_field_id = field_id if field_id not in valid_field_ids else None

                # Store the reconciliation result and both original records
                cursor.execute("""
                    INSERT INTO unloads (
                        id, field_id, unresolved_field_id, truck_id, crop,
                        weight_kg, unloaded_at, status, reason, previous_reason,
                        controller_record, cloud_record
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        field_id = EXCLUDED.field_id,
                        unresolved_field_id = EXCLUDED.unresolved_field_id,
                        truck_id = EXCLUDED.truck_id,
                        crop = EXCLUDED.crop,
                        weight_kg = EXCLUDED.weight_kg,
                        unloaded_at = EXCLUDED.unloaded_at,
                        status = EXCLUDED.status,
                        reason = EXCLUDED.reason,
                        previous_reason = EXCLUDED.previous_reason,
                        controller_record = EXCLUDED.controller_record,
                        cloud_record = EXCLUDED.cloud_record
                """, (
                    unload["id"],
                    valid_field_id,
                    unresolved_field_id,
                    unload["truck_id"],
                    unload["crop"],
                    unload.get("weight_kg"),
                    unload["unloaded_at"],
                    unload["status"],
                    unload.get("reason"),
                    unload.get("previous_reason"),
                    Jsonb(unload["controller_record"]) if unload.get("controller_record") is not None else None,
                    Jsonb(unload["cloud_record"]) if unload.get("cloud_record") is not None else None
                ))
