# Unload Reconciliation

A Python application that reconciles unload records from controllers and the cloud.

The application compares records from both sources, normalizes weights, identifies discrepancies, and stores the results in a PostgreSQL database. It also generates a CLI report showing field-level totals, unresolved records, and reconciliation decisions.

## Requirements

- Docker with Docker Compose
- Git (for cloning the repository)

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/hayyanhaider0/unload-reconciliation.git
cd unload-reconciliation
```

### 2. Configure environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

The `.env` file contains the PostgreSQL credentials used by Docker Compose.

The default credentials in `.env.example` are intended for local development. You can change the password before starting the containers.

### 3. Run the application

```bash
docker compose up --build
```

Docker Compose will build the Python application, start PostgreSQL, wait until the database is healthy, and run the reconciliation.

The report will be displayed in the terminal.

To stop the containers, press `Ctrl+C`, then run:

```bash
docker compose down
```

## How It Works

The application processes four JSON files:

- `controller_unloads.json` — unload records collected from cart controllers
- `cloud_unloads.json` — unload records stored in the cloud
- `fields.json` — field information
- `trucks.json` — truck information and capacities

The reconciliation process:

1. Matches controller and cloud records using their unload IDs.
2. Converts controller weights to kilograms.
3. Infers the clock offset using the most common offset among matched records.
4. Compares weights and corrected update timestamps, accepting whichever source was updated later.
5. Handles records marked as deleted in the cloud.
6. Accepts valid controller-only and cloud-only records while preserving their source.
7. Identifies duplicate unloads with different IDs and counts them only once.
8. Recovers missing controller weight units using matching cloud weights when possible.
9. Checks truck capacities, adds warnings for overweight unloads, and validates field references.
10. Preserves the original records and reconciliation results in PostgreSQL.

Records that cannot be confidently reconciled are flagged for manual review rather than silently discarded.

## Reconciliation Statuses

| Status | Description |
|---|---|
| `RECONCILED` | Record successfully reconciled and accepted |
| `WARNING`	| Accepted unload with a potential issue, such as exceeding truck capacity |
| `FLAGGED` | Record requires manual review |
| `DELETED` | Record marked as deleted in the cloud |
| `DUPLICATE` | Duplicate of another unload, excluded from totals |

The application identifies likely duplicates using matching field, truck, crop, weight, and corrected timestamps. Both records are preserved for auditing, but the unload is counted only once.

## Output

Running the application generates a terminal report containing:

**Field Summary**
- Number of accepted unloads per field
- Total accepted weight in kilograms per field
- Overall unload count and weight

**Unresolved Records**
- Record ID
- Reason the record was flagged
- Additional details about the discrepancy

**Warnings**
- Records that exceed truck capacity
- Truck name, unload weight, and rated capacity
- Warning records are still included in accepted harvest totals

**Automatic Reconciliation Decisions**
- Records automatically overridden, deleted, or marked as duplicates
- Record ID, status, and reconciliation reason
- Controller and cloud weights for weight overrides
- Original unload IDs for duplicate records

**Reconciliation Audit**
- Accepted records
- Flagged records
- Deleted records
- Duplicate records
- Total records processed

**Reconciliation Decisions**
- Summary of reconciliation reasons and their counts, including previous reasons

Only accepted records contribute to the confirmed field totals. Records that were automatically overridden or deleted are listed separately to make these decisions visible.

## Testing

The project uses Python's built-in `unittest` framework.

Run the tests inside Docker:

```bash
docker compose run --rm app python -m unittest discover -s tests -v
```

### My Tests

The five tests cover:

- **Record accounting:** Every unique unload ID from both sources appears exactly once in the reconciliation output.
- **Cloud weight override:** A later cloud update overrides the controller weight.
- **Controller weight override:** A later controller update overrides the cloud weight after clock correction.
- **Deletion priority:** A cloud record remains deleted even when the controller has a later update.
- **Deleted duplicates:** A deleted cloud unload cannot be brought back into accepted totals by a controller duplicate with a different ID.

### Review Tests

- **Test 1 — Later controller edit:** Checks that a controller weight is accepted when its corrected update timestamp is newer than the cloud's. This originally failed because I was flagging later controller edits instead of accepting them.
- **Test 2 — Duplicate unload:** Checks that two records with different IDs representing the same unload are not counted twice. This originally failed because I had removed cross-ID duplicate detection.

Both tests helped identify issues in my original reconciliation logic, which I fixed during the review.

These tests focus on preventing lost records, incorrect weight reconciliation, and deleted records accidentally being counted towards harvest totals.

## Project Structure

```text
unload-reconciliation/
├── data/
│   ├── controller_unloads.json
│   ├── cloud_unloads.json
│   ├── fields.json
│   └── trucks.json
├── database/
│   ├── importer.py
│   └── schema.sql
├── tests/
│   └── test_reconciliation.py
├── .env.example
├── .gitignore
├── Dockerfile
├── main.py
├── reconcile.py
├── report.py
├── requirements.txt
├── compose.yaml
├── README.md
└── DECISIONS.md
```

- `main.py` — entry point for the application
- `reconcile.py` — reconciliation and validation logic
- `database/importer.py` — imports data into PostgreSQL
- `database/schema.sql` — relational database schema
- `report.py` — queries PostgreSQL and generates the CLI report
- `tests/` — automated tests
- `Dockerfile` — builds the Python application container
- `compose.yaml` — configures the Python and PostgreSQL containers
- `.env.example` — example database credentials and environment configuration

## Design Decisions

See [DECISIONS.md](DECISIONS.md) for the assumptions made during reconciliation, known limitations, design choices, and how AI tools were used during development.