# Betting Feature Pipeline System Design

## Executive Summary

This project is the local batch slice of a betting ML feature pipeline. The basic job is simple enough: take an untrusted bet-level extract, split out the rows that are safe to use, quarantine the ones that are not, and publish customer-level first-20 features with enough metadata that downstream teams can consume them without guessing.

The package is intentionally local and lightweight, but I kept the controls close to what I’d expect around a production feature feed: explicit runtime-loaded contracts, deterministic transforms, quarantine, reports with checksums and run IDs, versioned outputs, and a clean rerun story.

For transparency, I used AI in a few focused review sessions. The prompts and the rough shape of that collaboration are in `design_note/ai_assistance_note.md`.

## End-to-End Flow

The architecture diagram in `architecture_diagram/batch_ml_architecture.png` shows the broader system:

1. Raw betting data lands as a file or partitioned extract.
2. A scheduler or operator triggers the batch workflow.
3. Validation checks the raw file against schema, domain, monetary, uniqueness, and ordering rules.
4. Valid records are published to a curated bet-level layer.
5. Invalid records are written to quarantine with rule-level explanations.
6. Customer feature generation aggregates valid first-20 bet windows.
7. Versioned feature output is made available to training, scoring, BI, CRM, and operational decisioning.
8. Monitoring captures counts, rates, failures, runtime, and output health.
9. Corrected source data or logic changes can be rerun or backfilled deterministically.

## Prompt Trail

The notes under `design_note/` are basically the working trail of those review sessions. Each one maps to a question I wanted to pressure-test:

- architecture and responsibilities;
- validation rules and defect capture;
- first-20 feature logic and leakage control;
- packaging, docs, and handover;
- test coverage and release readiness;
- the AI usage policy itself.

The point of keeping this in the repo is just honesty. AI helped me move faster, but the design and final decisions still came from the engineering work.

## Component Responsibilities

### Raw Betting Data Landing

The landing area stores exactly what arrived from upstream before any correction or transformation. In production I would keep the source filename, batch ID, checksum, arrival time, and owner so there’s a defensible audit trail when something looks off later.

### Scheduler or Job Trigger

The scheduler owns repeatability: when the job runs, which partition it reads, where outputs go, and which code/config version it uses. Locally, the equivalent interface is:

```bash
bet-pipeline validate --input data/bets.csv --output validation_outputs
bet-pipeline build-features --input data/bets.csv --output customer_feature_output
```

### Schema and Feature Configuration

The schema contract and feature definitions live under `source_code/src/bet_pipeline/config/`. Runtime code loads those files for required columns, domain values, feature output columns, and version metadata, so they are not just passive documentation.

In production, I’d register those contracts centrally and treat breaking changes as new feature-set versions rather than silent column changes.

### Validation Job

Validation treats the CSV as untrusted input. It parses fields, checks domains, validates monetary formulas, enforces uniqueness, checks customer ordering, and records all rule failures per row.

Outputs:

- `valid_bets.csv`: clean, typed, normalised bet records;
- `invalid_bets.csv`: quarantined records with source row number, original values, canonical customer ID, normalized helper fields, expected monetary values where calculable, and failed rule names;
- `validation_report.json`: row counts, invalid rate, failure counts, Decimal money policy, contract version, checksum, output contract, and sequence warnings.

### Invalid-Record Quarantine

Quarantine exists so defects stay visible instead of disappearing into the job output. The JSON report gives the broad shape of the issue, then the invalid rows tell you whether it’s a one-off or something upstream is doing repeatedly.

The usual flow is pretty standard: identify the rule, route the systemic issue to the source owner, fix upstream where needed, land a corrected extract, and rerun into a new output version.

### Curated Validated-Bets Layer

This layer is the clean bet-level handoff from validation to feature engineering. Feature jobs should read from a validated contract, not from raw input. The local feature command validates internally so it can be run independently, but the production design still treats the curated bet layer as the trusted boundary.

### Customer Feature Generation

The feature job builds customer rows using valid records where `1 <= bet_num <= 20`. I kept `bet_num` as the ordering source because timestamp order is exactly the kind of thing that gets messy in real extracts. Later bets are not used to replace invalid early bets, since that would leak later customer behaviour into a window that is supposed to represent the first 20 bets.

The output includes required ML features plus operational fields:

- `feature_window_policy`;
- `invalid_first20_count`;
- `feature_quality_flag`.

Those fields let downstream teams decide whether to consume only full-quality windows or include partial rows with review controls.

### Versioned Feature Output

The local project writes CSV and, when possible, Parquet. In production I’d publish to a versioned serving table or feature store with source run ID, feature-set version, generation timestamp, and quality metadata.

Consumers should rely on the documented feature contract, not on whatever happens to be sitting in an ad hoc file.

### Monitoring and Alerting

The pipeline should log source path, checksum, code version, contract version, row counts, invalid rate, failure counts, feature row count, runtime, and output paths.

Useful alerts are the usual ones:

- missing or late input file;
- schema failure;
- invalid-row rate above threshold;
- duplicate bet IDs;
- payout or return mismatch spike;
- feature row count drop;
- partial-window rate spike;
- job failure or unusual runtime.

### Downstream Consumers

The same feature output can support several consumers:

- batch model training on historical snapshots;
- batch scoring for current customer populations;
- BI and analytics for reporting and monitoring;
- CRM activation or operational decisioning where feature quality flags are respected.

Each consumer should pin the feature-set version and agree how to handle `PARTIAL_OR_REVIEW_FIRST20_WINDOW` rows.

## Batch Versus Streaming

Batch is the right fit for this exercise. The input is a file, the feature window is historical, and the likely use cases are model training, offline scoring, reporting, and periodic activation. Batch also keeps replay and backfill straightforward.

Streaming would become relevant if the business needed live risk signals, in-session decisioning, or immediate eligibility updates. A streaming implementation should reuse the same schema and feature definitions, but it would need event-time state, late-arriving event policy, idempotent writes, and tighter serving monitoring.

## Reruns, Backfills, and Idempotency

A run should be reproducible for a fixed input file, code version, contract version, and feature generation timestamp. Production runs should write to versioned output locations instead of mutating historical results in place.

Rerun approach:

1. Preserve the original source extract.
2. Land the corrected extract with a new checksum or source version.
3. Run validation and feature generation again.
4. Publish corrected outputs to a new versioned partition.
5. Notify consumers if previous features are superseded.

Backfills should process historical partitions under a pinned contract and code version, then compare counts and quality metrics against prior runs before release.

## Trade-Offs and Assumptions

The pipeline always writes CSV because it’s easy to inspect locally. It also attempts Parquet because typed tabular output is a better fit once you move beyond a single developer machine.

Partial feature windows are retained instead of dropped. That makes the output more honest, but it does mean downstream consumers have to make an explicit quality call.

The feature command validates internally. It’s a little repetitive, but it keeps the command safe and self-contained.

The implementation uses pandas. If the volume grew materially, I’d revisit the execution engine, but this dataset is fine as a local batch job.

Key assumptions:

- `bet_num` is the authoritative customer sequence;
- the source extract contains enough customer history to evaluate first-20 windows;
- monetary mismatches greater than `0.01` are meaningful defects;
- this assessment values correctness, reproducibility, and design reasoning over cloud-specific tooling.
