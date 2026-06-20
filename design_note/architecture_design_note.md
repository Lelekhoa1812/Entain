# Architecture Prompt

```text
Review the end-to-end architecture at the level of an experienced engineer.

Do not explain what batch processing is. Assume the core implementation skills are already covered.

Focus on:
- whether the responsibilities are separated cleanly;
- whether raw, validated, quarantined, and curated data are treated as distinct contracts;
- whether reruns and backfills are deterministic;
- whether monitoring and versioning are good enough for downstream consumers;
- whether batch is the right default for this data shape and feature window.

Return the most important design risks or missing pieces only.
```

This was the first pass where I wanted to sanity-check the shape of the system, not the implementation details. The main question was whether the pieces hang together in a way I’d be comfortable defending in a review.

The local package represents the batch feature engineering slice of a broader ML system. In production, the same responsibilities would usually sit behind a scheduler and publish to a versioned feature table or feature store.

The architecture separates responsibilities cleanly:

- raw landing keeps the source extract unchanged for audit and replay;
- validation applies the schema and business contract;
- quarantine exposes invalid rows for investigation;
- the curated bet layer contains only validated records;
- feature generation aggregates stable customer features;
- versioned feature output gives downstream consumers a predictable interface;
- monitoring records row counts, invalid rates, runtime, and output health;
- rerun and backfill paths allow corrected source data or logic changes to be reprocessed.

Batch is the right default here because the input is file-based and the first-20 feature window is naturally historical. Streaming would matter for live decisioning, but it would bring in state management, late-event policy, and stronger serving guarantees that are outside this assessment.

The important production discipline is contract management. Schema rules, feature definitions, code version, source checksum, and output version should travel together so downstream consumers know exactly what they are consuming and can reproduce or supersede a run when defects show up.

## Data Observations & Sanitization

Reviewing `data/bets.csv` for this submission surfaces the same signal that inspired the validation rules: 372,296 bets from 5,000 customers skew heavily toward racing bets (≈74.8%) and cash stakes (≈95%). `betting_amount` spans −50.71 to 89.40 AUD and `price` ranges from 0.356 to 26.71, so the extract already contains negative wagers, sub‑unit odds, and other corrupted records before the pipeline even runs. The dominant validation failures (3,884 rows where `bet_datetime` decreases while `bet_num` climbs, 835 non-positive `betting_amount` rows, and several hundred more caught by payout/return math) prove that the source remains untrusted.

This dataset profile is encoded directly in the cleansing stage housed in `source_code/src/bet_pipeline`:

- `io.read_bets_csv` retains the raw strings rather than letting pandas coerce types, keeping the validation layer fully responsible for detecting misformatted UUIDs, timestamps, and numerics.
- `_normalise_raw_frame` trims, lowercases, and rehydrates enumerated text fields; parses decimals and timestamps with `Decimal`/`pandas`; stamps `source_row_number` so inspectors can trace quarantined data back into the raw landing zone.
- `validate_bets` enforces the task brief rules, recomputes `payout`/`return_for_entain` with deterministic rounding, prevents duplicate `(customer_id, bet_num)` pairs, and writes every failed row to `invalid_bets.csv` with its rule tags intact.

The `tests/test_data_observation.py` asset keeps these observations honest: it asserts that the expected failure classes still exist and documents the distributional skew so that future refactors do not drift from the signal that motivated this architecture.
