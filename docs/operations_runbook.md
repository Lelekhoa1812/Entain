# Operations Runbook

This runbook describes how to operate the local batch pipeline and how the same workflow would be managed in production.

## Normal Run

1. Confirm the raw extract is present at `data/bets.csv`.
2. Run validation.
3. Review `validation_report.json`.
4. Run feature generation.
5. Review `feature_build_report.json`.
6. Hand the versioned feature output to downstream consumers.

## Commands

```bash
bet-pipeline validate --input data/bets.csv --output validation_outputs
bet-pipeline build-features --input data/bets.csv --output customer_feature_output
pytest
```

For reproducible handover runs, pin the timestamps and run IDs:

```bash
bet-pipeline validate --input data/bets.csv --output validation_outputs --generated-at 2026-06-19T01:49:26+00:00 --run-id submitted-validation
bet-pipeline build-features --input data/bets.csv --output customer_feature_output --generated-at 2026-06-19T01:49:39+00:00 --run-id submitted-feature-build
```

Without installing the console script:

```bash
PYTHONPATH=source_code/src python -m bet_pipeline.cli validate --input data/bets.csv --output validation_outputs
PYTHONPATH=source_code/src python -m bet_pipeline.cli build-features --input data/bets.csv --output customer_feature_output
PYTHONPATH=source_code/src pytest
```

## Validation Review

Check:

- `input_rows` matches the expected source volume;
- `invalid_row_rate` is within the agreed tolerance;
- `failure_counts_by_rule` has no unexpected spikes;
- `schema_contract_version`, input checksum, and run ID match the expected release;
- `extra_columns` are expected or have a documented upstream owner;
- duplicate key failures are investigated immediately;
- monetary mismatch failures are reviewed with the source owner;
- sequence warnings are assessed for first-20 feature impact.

## Feature Review

Check:

- `customer_count` is within the expected range;
- `full_quality_customer_count` has not dropped unexpectedly;
- `partial_or_review_customer_count` is explainable;
- `customers_without_valid_first_window_count` is monitored;
- `table_outputs` records CSV and, where available, Parquet output.

## Suggested Alert Thresholds

| Metric | Example alert |
|---|---|
| Input availability | No file by scheduled run time |
| Invalid row rate | Greater than 2% after baseline is established |
| Duplicate bet IDs | Any duplicate in production |
| Payout or return mismatches | Any sudden spike or sustained non-zero rate |
| Feature row count | More than 20% below recent median |
| Partial first-20 windows | Material increase from recent baseline |
| Runtime | More than 2x rolling median |

## Rerun and Backfill

For a corrected source file:

1. Preserve the original raw file and its outputs.
2. Land the corrected file with a new checksum or source version.
3. Run validation into a new output location in production.
4. Run feature generation against the corrected source.
5. Compare counts and quality metrics with the previous run.
6. Notify downstream consumers if prior feature output is superseded.

For historical backfills, pin the code version and contract version, then process each partition deterministically.

## Incident Notes

When validation fails because of schema or systemic data quality issues, do not patch feature outputs manually. Fix the source or contract, rerun the pipeline, and keep the old quarantine artefacts for audit.
