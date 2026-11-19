CREATE TABLE IF NOT EXISTS fields (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    area_ha NUMERIC NOT NULL,
    crop TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trucks (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    capacity_kg NUMERIC NOT NULL CHECK (capacity_kg > 0)
);

CREATE TABLE IF NOT EXISTS unloads (
    id UUID PRIMARY KEY,
    field_id UUID REFERENCES fields(id),
    unresolved_field_id UUID,
    truck_id UUID REFERENCES trucks(id) NOT NULL,
    crop TEXT NOT NULL,
    weight_kg NUMERIC CHECK (weight_kg >= 0),
    unloaded_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('RECONCILED', 'FLAGGED', 'DELETED', 'DUPLICATE', 'WARNING')
    ),
    reason TEXT,
    previous_reason TEXT,
    duplicate_of UUID REFERENCES unloads(id)
        DEFERRABLE INITIALLY DEFERRED,
    controller_record JSONB,
    cloud_record JSONB
);