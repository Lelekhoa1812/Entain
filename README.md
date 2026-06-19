# Entain Betting ML Batch Pipeline

This repository contains a local, reproducible Python batch pipeline for validating raw betting records and producing customer-level machine-learning features from each customer's first 20 bets. The solution is intentionally small, but it is structured like a production data product: raw input is treated as untrusted, invalid rows are quarantined with rule-level explanations, feature semantics are deterministic, and downstream users get a documented contract.

The project does not train a model, expose an API, or depend on cloud services. It focuses on the data engineering and ML feature foundations that would sit upstream of training, scoring, analytics, CRM activation, or operational decisioning.

## Architecture Preview

The main architecture diagram shows how the local batch workflow fits into a broader ML feature system.

![Betting ML architecture](architecture_diagram/batch_ml_architecture.png)

The rerun and correction flow is kept separately so the operational path is easy to inspect.

![Pipeline rerun and correction flow](architecture_diagram/backfill_data_quality_flow.png)

Diagram sources and exports:

- [Architecture explanation](architecture_diagram/architecture.md)
- [Batch ML architecture PNG](architecture_diagram/batch_ml_architecture.png)
- [Backfill/data-quality flow PNG](architecture_diagram/backfill_data_quality_flow.png)

## System Architecture

At a high level, the pipeline has four boundaries.

The raw boundary is `data/bets.csv`. The file is read as strings first so validation, not pandas type inference, owns parsing and defect reporting.

The validation boundary is `bet-pipeline validate`. It checks schema, parseability, domains, numeric constraints, duplicate keys, monetary formulas, and customer ordering. Valid rows are written to `validation_outputs/valid_bets.csv`; bad rows are written to `validation_outputs/invalid_bets.csv`; summary metrics are written to `validation_outputs/validation_report.json`.

The feature boundary is `bet-pipeline build-features`. It validates internally, filters to valid records where `1 <= bet_num <= 20`, and aggregates customer-level features. Invalid early bets are not replaced by later bets. Partial windows are retained with quality metadata.

The consumption boundary is the generated feature table. Locally this is CSV plus Parquet when `pyarrow` is available. In a production deployment, this would normally become a versioned feature table or feature-store dataset consumed by model training, batch scoring, BI, CRM activation, and operational decisioning.

## Repository Contents

```text
.
├── architecture_diagram/
│   ├── architecture.md                   # Architecture explanation and operating model
│   ├── batch_ml_architecture.png         # Main ML system architecture diagram
│   └── backfill_data_quality_flow.png    # Rerun, correction, and backfill path
├── customer_feature_output/
│   ├── customer_features.csv             # Customer-level first-20 feature table
│   ├── customer_features.parquet         # Typed feature output when pyarrow is installed
│   └── feature_build_report.json         # Feature run summary and validation summary
├── data/
│   └── bets.csv                          # Raw betting extract used for the submitted run
├── design_note/
│   ├── ai_assistance_note.md             # Transparent note on selective AI-assisted review
│   ├── architecture_design_note.md       # Architecture reasoning and production fit
│   ├── feature_design_note.md            # Feature-window and aggregation decisions
│   ├── system_design_note.md             # Full system design narrative
│   └── validation_design_note.md         # Validation and quarantine decisions
├── docs/
│   ├── data_contract.md                  # Input, quarantine, and feature contracts
│   ├── jr-mle-task.docx                  # Original task brief
│   ├── operations_runbook.md             # Operating, review, rerun, and alert guidance
│   ├── task_breakdown.md                 # Requirement-to-deliverable mapping
│   └── testing_strategy.md               # Test coverage and validation approach
├── source_code/src/bet_pipeline/
│   ├── __init__.py
│   ├── build_features.py                 # Customer feature generation workflow
│   ├── cli.py                            # `bet-pipeline` command-line interface
│   ├── config/
│   │   ├── feature_definitions.json      # Machine-readable feature definitions
│   │   └── schema_contract.json          # Machine-readable schema/business contract
│   ├── constants.py                      # Shared rule constants
│   ├── io.py                             # Repeatable local I/O helpers
│   └── validate.py                       # Validation, quarantine, and report workflow
├── tests/
│   ├── test_cli.py                       # CLI output tests
│   ├── test_features.py                  # Feature logic tests
│   └── test_validation.py                # Validation rule tests
├── Dockerfile                            # Clean-environment runtime image
├── Makefile                              # Convenience commands
├── pyproject.toml                        # Packaging, dependencies, pytest config
└── README.md
```

## Key Documents

- [Data contract](docs/data_contract.md)
- [Operations runbook](docs/operations_runbook.md)
- [Testing strategy](docs/testing_strategy.md)
- [Task breakdown](docs/task_breakdown.md)
- [System design note](design_note/system_design_note.md)
- [Validation design note](design_note/validation_design_note.md)
- [Feature design note](design_note/feature_design_note.md)
- [Architecture design note](design_note/architecture_design_note.md)
- [Selective AI assistance note](design_note/ai_assistance_note.md)

## Setup

Use Python 3.10 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,parquet]"
```

The `parquet` extra installs `pyarrow`. If a parquet engine is not installed, the pipeline still emits CSV and records the fallback reason in `feature_build_report.json`.

For a one-command local setup, use `make setup`. `requirements.lock` records the dependency versions used for the verified handover run.

## Run Validation

```bash
bet-pipeline validate --input data/bets.csv --output validation_outputs
```

Equivalent command without installing the console entry point:

```bash
PYTHONPATH=source_code/src python -m bet_pipeline.cli validate --input data/bets.csv --output validation_outputs
```

Validation outputs:

- `validation_outputs/valid_bets.csv`
- `validation_outputs/invalid_bets.csv`
- `validation_outputs/validation_report.json`

The validation job checks:

- required columns;
- extra columns, which are reported but not treated as fatal;
- integer `bet_id` and `bet_num`;
- UUID `customer_id`;
- parseable `bet_datetime`;
- positive `bet_num`;
- positive `betting_amount`;
- `price > 1`;
- allowed `category`, `stake_type`, and `bet_result`;
- numeric `payout` and `return_for_entain`;
- payout business rules;
- return-for-Entain business rules;
- unique `bet_id`;
- unique `(customer_id, bet_num)`;
- non-decreasing `bet_datetime` as `bet_num` increases for a customer.

Reports include schema contract version, input SHA-256, output paths, optional run ID, and the Decimal cent-precision money policy. Reproducible runs can pin metadata:

```bash
bet-pipeline validate --input data/bets.csv --output validation_outputs --generated-at 2026-06-19T01:49:26+00:00 --run-id submitted-validation
```

## Build Customer Features

```bash
bet-pipeline build-features --input data/bets.csv --output customer_feature_output
```

Equivalent module command:

```bash
PYTHONPATH=source_code/src python -m bet_pipeline.cli build-features --input data/bets.csv --output customer_feature_output
```

Feature outputs:

- `customer_feature_output/customer_features.csv`
- `customer_feature_output/customer_features.parquet`
- `customer_feature_output/feature_build_report.json`

The feature job validates the raw file internally before aggregation. It uses `bet_num` as the authoritative customer sequence and includes only valid rows where `1 <= bet_num <= 20`. If an early bet is invalid, the pipeline does not pull in bet 21 to fill the gap.

Feature reports include schema contract version, feature-set version, input SHA-256, output paths, and optional run ID. Use `--generated-at` when feature timestamps need to be deterministic.

## Feature Columns

Required columns:

- `customer_id`
- `first_bet_datetime`
- `twentieth_bet_datetime`
- `bets_used`
- `total_betting_amount`
- `mean_betting_amount`
- `mean_price`
- `pct_racing`
- `pct_cash`
- `pct_return`
- `total_payout`
- `total_return_for_entain`
- `feature_generated_at`

Operational safety columns:

- `feature_window_policy`
- `invalid_first20_count`
- `feature_quality_flag`

`feature_quality_flag` is `FULL_20_VALID_BETS` when the customer has 20 valid first-window records and no invalid first-window records. Otherwise, it is `PARTIAL_OR_REVIEW_FIRST20_WINDOW`.

## Submitted Output Summary

The checked-in outputs were regenerated from the full `data/bets.csv`.

Validation:

- input rows: `372,296`
- valid rows: `367,556`
- invalid rows: `4,740`
- invalid row rate: `1.2732%`

Feature generation:

- customer rows: `5,000`
- full-quality customers: `3,894`
- partial/review customers: `1,106`
- customers without a valid first-window row: `0`
- CSV and Parquet outputs are present.

## Testing

```bash
.venv/bin/pytest
```

The tests cover validation rules, Decimal monetary formulas, contract drift, duplicate keys, ordering checks, raw quarantine preservation, extra-column reporting, multiple failures on one row, first-20 feature semantics, canonical invalid-window counting, golden feature output, deterministic timestamps, and CLI metadata.

Full local verification:

```bash
make verify
```

## Docker

Build:

```bash
docker build -t entain-bet-pipeline .
```

Build and run the Docker test stage:

```bash
docker build --target test -t entain-bet-pipeline-test .
```

Run validation:

```bash
docker run --rm \
  -v "$(pwd)/data:/data" \
  -v "$(pwd)/validation_outputs:/outputs" \
  entain-bet-pipeline validate --input /data/bets.csv --output /outputs
```

Run feature generation:

```bash
docker run --rm \
  -v "$(pwd)/data:/data" \
  -v "$(pwd)/customer_feature_output:/outputs" \
  entain-bet-pipeline build-features --input /data/bets.csv --output /outputs
```

Docker was verified against the full input file. The containerized runs produced the same headline counts as the local runs:

- validation: `367,556` valid rows and `4,740` invalid rows;
- features: `5,000` customer rows with Parquet output.

## Design Decisions

Raw input is read as strings first. This prevents accidental type coercion from hiding source defects before validation can report them.

Invalid rows are quarantined rather than silently dropped. This gives operators a review path and gives downstream ML consumers a clear reason for partial customer windows.

The first-20 policy is conservative. The pipeline uses `bet_num`, excludes invalid rows, and never replaces an invalid early bet with a later valid bet. This avoids leaking later behaviour into a feature window that is meant to represent the customer's first 20 bets.

CSV is always emitted because it is easy to inspect locally. Parquet is emitted when available because typed tabular output is the better interface for production consumers.

Batch processing is appropriate because the source is file-based and the features are historical customer aggregates. A streaming version would reuse the same contracts but would need event-time state, late-event handling, idempotent writes, and stronger serving guarantees.
