# Betting Customer Feature Pipeline Architecture

## 1. System purpose

This architecture describes how a local batch Python pipeline for betting data can fit into a broader production-style machine-learning system. The local implementation validates raw bet-level records, quarantines invalid rows, produces a curated validated-bets layer, and generates customer-level features based on each customer’s first 20 bets. In a broader enterprise setting, the same pattern supports model training, batch scoring, analytics, CRM activation, and operational decisioning.

The system is designed around five principles:

1. Raw source data is untrusted until validated.
2. Invalid records are isolated and made reviewable rather than silently dropped.
3. Feature generation reads from validated data, not directly from raw input.
4. Feature outputs are versioned so downstream consumers can rely on stable contracts.
5. Reruns and backfills are deterministic, auditable, and safe for downstream users.

## 2. Diagram files

The architecture pack contains two PNG diagrams:

- `batch_ml_architecture.png`  
  Shows the end-to-end batch ML architecture: ingestion, orchestration, governance, validation, curated data, feature generation, feature serving, observability, downstream consumers, and rerun/backfill path.

- `backfill_data_quality_flow.png`  
  Shows the operating flow for defects, source corrections, schema changes, reruns, backfills, idempotency controls, consumer notification, and auditability.

## 3. End-to-end architecture

![Enterprise batch ML architecture](batch_ml_architecture.png)

The broader system starts from raw betting data and ends with versioned customer features consumed by multiple downstream systems. The main path is:

1. Source systems export raw betting records into a landing area.
2. A scheduler or batch trigger starts the workflow with a run ID and partition date.
3. Governance assets, including schema contracts, business rules, feature definitions, configuration, and metadata registry, control the pipeline.
4. The validation job checks raw records against structural, domain, numeric, payout, return, uniqueness, and ordering rules.
5. Valid records are written to a curated validated-bets layer.
6. Invalid records are written to a quarantine and review path.
7. A customer feature generation job creates first-20-bet customer features.
8. Features are published as a versioned output, feature store table, or serving table.
9. Logs, metrics, monitoring, and alerts observe every stage.
10. Downstream consumers read stable feature snapshots through documented contracts.

## 4. Component responsibilities

### 4.1 Source and ingestion

The source and ingestion layer represents the raw betting data source and the landing area. In the local assessment, this is represented by `data/bets.csv`. In a production-like system, the landing area would also keep source metadata such as file checksum, extract timestamp, source system, and batch identifier.

Data entering this layer:

- raw bet-level records;
- source extract metadata;
- file or partition arrival events.

Data leaving this layer:

- a raw batch file or partition path;
- metadata used by the scheduler and validation job.

This layer should remain immutable. Corrections should land as a new source extract rather than editing the previous file in place.

### 4.2 Scheduler and orchestration

The scheduler owns repeatable execution. It starts validation and feature generation with explicit run parameters such as input path, output path, run ID, date partition, and optional backfill scope.

In the local package, the equivalent commands are:

```bash
bet-pipeline validate --input /data/bets.csv --output /outputs/validation
bet-pipeline build-features --input /data/bets.csv --output /outputs/features
```

In an enterprise implementation, the scheduler would also manage dependency ordering. The feature job should only publish trusted features after validation has completed and quality gates have passed.

### 4.3 Governance and metadata control plane

The governance layer prevents silent contract drift. It contains:

- schema contract for required columns and data types;
- business rules for domain values, numeric constraints, payout logic, and return logic;
- feature definitions for metric names, logic, windows, and entity keys;
- configuration for paths, thresholds, and lookbacks;
- metadata or version registry for schemas, features, runs, and lineage.

This layer governs validation and feature generation. Downstream consumers should rely on registered feature definitions and versions rather than reverse-engineering feature meaning from output files.

### 4.4 Data quality and validation

The validation job is the main quality gate between raw input and trusted data. It checks:

- `betting_amount > 0`;
- `price > 1`;
- `category` is one of `sports` or `racing`;
- `stake_type` is one of `cash` or `bonus`;
- `bet_result` is one of `return` or `no-return`;
- payout matches the business formula;
- `return_for_entain` matches the business formula;
- `bet_id` is unique;
- `bet_num` ordering is consistent within each customer where applicable.

Data entering validation:

- raw betting extract;
- schema and business rule configuration.

Data leaving validation:

- `valid_bets.csv`;
- `invalid_bets.csv`;
- `validation_report.json`.

The validation report should include failure counts by rule, row counts, valid/invalid rates, and any warnings that operators or downstream users need to understand.

### 4.5 Invalid-record quarantine and review path

Invalid rows are isolated into a quarantine path instead of being ignored. This supports investigation, correction, and auditability.

A good quarantine output should preserve:

- original source row number;
- original field values;
- failed rule names;
- expected payout and expected return where calculable;
- run ID and source batch ID;
- timestamp of validation.

Operators should review the validation report first to detect systemic problems. For example, a sudden spike in payout mismatches may indicate upstream logic changed, while a few invalid domain values may be a localized data-entry issue.

### 4.6 Curated validated-bets layer

The curated layer contains only rows that passed validation. This is the trusted bet-level input for feature generation.

The curated layer exists because downstream feature logic should not repeatedly decide how to handle raw defects. It should operate from a stable, validated, documented bet-level table.

In the local implementation, the curated layer is represented by `valid_bets.csv`.

### 4.7 Customer feature generation

The customer feature generation job creates customer-level features from validated records. The key rule is that each customer’s first 20 bets are selected using `bet_num` as the authoritative sequence.

Core feature outputs include:

- `customer_id`;
- `first_bet_datetime`;
- `twentieth_bet_datetime`;
- `bets_used`;
- `total_betting_amount`;
- `mean_betting_amount`;
- `mean_price`;
- `pct_racing`;
- `pct_cash`;
- `pct_return`;
- `total_payout`;
- `total_return_for_entain`;
- `feature_generated_at`.

Where invalid records appear within a customer’s first-20 window, the deterministic policy is to exclude invalid rows from aggregation, record how many were excluded, and expose a quality flag so downstream consumers can filter or review partial windows.

### 4.8 Feature serving and versioned output

The feature serving layer exposes feature snapshots to consumers. In a local setting this can be a CSV or Parquet output. In a production-like system this could be a feature store, a serving table, or a versioned data lake table.

Each feature snapshot should include metadata such as:

- `feature_set_version`;
- `generated_at`;
- `run_id`;
- `source_batch_id`;
- `schema_contract_version`;
- `feature_definition_version`;
- `quality_flag`.

Versioning is important because downstream consumers may train or score models against a specific feature definition. Breaking changes should create a new feature set version rather than silently modifying an existing one.

### 4.9 Observability

Observability makes the pipeline operable in production. The system should collect logs, metrics, dashboards, and alerts from ingestion, validation, feature generation, and publishing.

Recommended logs:

- run ID;
- input path and checksum;
- schema contract version;
- feature definition version;
- start and end times;
- row counts;
- output paths;
- exception details.

Recommended metrics:

- input row count;
- valid row count;
- invalid row count;
- invalid row rate;
- failure counts by rule;
- duplicate bet count;
- payout mismatch count;
- return mismatch count;
- customer feature row count;
- full-quality customer count;
- partial-window customer count;
- runtime;
- output file size.

Recommended alerts:

- input file missing;
- schema mismatch;
- invalid row rate above threshold;
- duplicate `bet_id` detected;
- payout or return mismatch spike;
- feature row count drops unexpectedly;
- job failure;
- unusually long runtime;
- publish failure.

### 4.10 Downstream consumers

The versioned customer feature table can be consumed by several systems:

1. Batch model training  
   Uses historical feature snapshots to train and evaluate ML models.

2. Batch scoring  
   Uses the latest feature snapshot to score customers offline.

3. BI and analytics  
   Uses the feature table and validation metrics for reporting, segmentation, and quality monitoring.

4. CRM activation or operational decisioning  
   Uses features, quality flags, and model scores for campaigns, customer prioritisation, eligibility logic, or operational actions.

Consumers should depend on stable interfaces:

- entity key: `customer_id`;
- feature set version;
- generation timestamp;
- documented column names;
- documented feature semantics;
- quality filtering rules.

## 5. Rerun, backfill, and correction flow

![Rerun, backfill, and data quality operating flow](backfill_data_quality_flow.png)

The rerun and backfill flow describes how the system reacts when data defects, source corrections, schema changes, or consumer issues are discovered.

The operating flow is:

1. A triggering event occurs.
2. Operators inspect validation reports and invalid-record quarantine.
3. Root cause is classified as source data, business rule, or code/config defect.
4. The corrected source, contract, config, or code version is pinned.
5. A rerun request is created with an explicit run scope.
6. Validation and feature generation are reprocessed.
7. A corrected versioned feature snapshot is published.
8. Downstream users are notified, and the previous snapshot is marked as superseded when required.
9. Logs, lineage, audit records, and quality metrics are retained.

## 6. Batch versus streaming

Batch processing is the correct default for this assessment because the input is a file-based extract and the downstream requirement is a customer-level dataset derived from the first 20 bets. These features are suitable for offline training, periodic scoring, analytics, and CRM activation. Batch processing also supports easier validation reports, deterministic replay, simpler local reproducibility, and lower operational complexity.

Streaming may fit if the organisation needs near-real-time decisions, such as live risk signals, in-session personalisation, immediate offer eligibility, or operational intervention. A streaming design would need event-time processing, late-event handling, stateful customer windows, stronger idempotency controls, and more complex monitoring. The schema contract and feature definitions should still be shared between batch and streaming implementations to avoid inconsistent feature semantics.

## 7. Schema validation, versioning, and downstream safety

Schemas are validated before feature generation. Business rules define the contract for domain values, numeric ranges, payout, and Entain return calculations. Feature definitions define aggregation logic and customer-level semantics.

Downstream safety is achieved through:

- explicit schema contracts;
- row-level validation;
- invalid-record quarantine;
- validation reports;
- feature definition files;
- feature set versioning;
- stable column names;
- quality flags;
- audit metadata.

Breaking changes should be released as a new feature set version. Non-breaking changes, such as adding a nullable feature, can be introduced with release notes and consumer notification.

## 8. Invalid records and operator workflow

Invalid records are not silently removed. They are written to quarantine with enough context for investigation. Operators should use `validation_report.json` to understand failure rates and then inspect `invalid_bets.csv` for row-level details.

Common operator actions include:

- route source defects to upstream data owners;
- correct the raw extract and rerun;
- adjust the schema contract if business rules have legitimately changed;
- patch pipeline code if the validation implementation is incorrect;
- notify downstream consumers if a previous feature snapshot is affected.

## 9. Feature consistency across producers and consumers

Feature consistency is maintained by treating feature definitions as governed assets. The pipeline should use a single definition of each feature, including entity key, input layer, aggregation window, formula, null handling, and quality policy.

Consumers should not reimplement feature logic independently. They should read the published feature snapshot or serving table and filter using documented quality flags.

## 10. Idempotency, reruns, and backfills

A rerun should be deterministic for a fixed set of inputs:

- raw source file or partition;
- source checksum;
- code version;
- schema contract version;
- feature definition version;
- run parameters.

Recommended idempotency controls:

- unique run ID;
- immutable raw source storage;
- content checksum;
- date or batch partition;
- atomic publish;
- versioned outputs;
- never overwrite historical snapshots silently;
- mark superseded snapshots instead of deleting history.

For backfills, the system should process a bounded scope such as date range, partition list, or customer segment. After completion, operators should compare row counts, invalid rates, feature row counts, and consumer-impact metrics against the previous run.

## 11. Production logging, metrics, and alerting

The most important production metrics are:

- validation pass rate;
- invalid row rate;
- failure counts by rule;
- payout mismatch count;
- return mismatch count;
- feature row count;
- partial-window feature row count;
- runtime;
- publish success;
- backfill completion status.

Alerts should focus on conditions that threaten downstream trust, including schema drift, high invalid rates, duplicate identifiers, broken payout logic, feature row-count drops, missing inputs, or repeated job failures.

## 12. Main trade-offs and assumptions

### Trade-offs

- Batch processing is simpler and reproducible, but it does not provide real-time feature updates.
- CSV is easy to inspect locally, while Parquet is better for typed production use.
- Keeping partial customer feature rows improves auditability, but downstream users must respect quality flags.
- Running validation inside the feature command improves safety, but repeats some work if validation already ran separately.
- Pandas is appropriate for the local assessment, but large-scale production data may require a distributed engine.

### Assumptions

- `bet_num` is the authoritative order for each customer.
- Raw betting records can contain multiple defects per row.
- Source data corrections should be landed as new versions, not edited in place.
- Feature consumers prefer stable, documented snapshots over ad hoc transformations.
- The system does not train models or expose APIs; it produces validated data and customer features for downstream ML consumers.
