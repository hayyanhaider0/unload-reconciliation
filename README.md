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
3. Compares weights and timestamps for matched records.
4. Handles records marked as deleted in the cloud.
5. Flags records that exist in only one source.
6. Checks accepted unloads against truck capacities and validates field references.
7. Preserves the original records and reconciliation results in PostgreSQL.

Records that cannot be confidently reconciled are flagged for manual review rather than silently discarded.

## Reconciliation Statuses

| Status | Description |
|---|---|
| `RECONCILED` | Record successfully reconciled and accepted |
| `FLAGGED` | Record requires manual review |
| `DELETED` | Record marked as deleted in the cloud |

Records with different IDs are preserved separately. The application does not automatically classify them as duplicates because the provided data does not establish a reliable way to identify cross-ID duplicates.

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

**Automatic Reconciliation Decisions**
- Records automatically overridden or marked as deleted
- Record ID, status, and decision
- Original controller and accepted cloud weights for weight overrides

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

Three tests cover:

- **Record accounting:** Every unique unload ID from both sources must appear exactly once in the reconciliation output.
- **Cloud weight override:** When the cloud has a later update, the cloud weight is accepted.
- **Controller updated later:** When the controller has a later update and the weights differ, the record is flagged for manual review.

These tests focus on preventing lost records and incorrect weight reconciliation.

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