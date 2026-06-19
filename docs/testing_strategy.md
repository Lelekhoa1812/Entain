# Testing Strategy

The tests focus on the parts of the pipeline most likely to create downstream ML risk: business-rule correctness, quarantine behaviour, first-20 window semantics, and the public CLI contract.

## Current Coverage

Validation tests cover:

- missing required columns;
- invalid UUID and datetime parsing;
- non-integer and non-positive `bet_num`;
- payout rules for cash and bonus returns;
- no-return rules for cash and bonus stakes;
- return-for-Entain mismatches;
- duplicate `bet_id`;
- duplicate `(customer_id, bet_num)`;
- timestamp ordering by customer bet number;
- multiple failures preserved on one row;
- contract JSON/runtime drift checks;
- raw quarantine value preservation;
- extra-column reporting;
- Decimal cent-precision money boundaries;
- validation file outputs.

Feature tests cover:

- full 20-bet customer aggregation;
- invalid early bets not being replaced by later bets;
- partial windows without bet 20;
- all-invalid input;
- customers with no valid first-window records;
- deterministic `feature_generated_at`;
- canonical customer matching for invalid first-window counts;
- feature-set version and checksum metadata;
- a small golden-output fixture;
- feature file outputs.

CLI tests cover:

- `validate` command output files;
- `build-features` command output files.

## Why These Tests Matter

The highest-risk bugs here are subtle: a formula that is off by one stake type, a duplicate key that only quarantines one side, a later bet leaking into a first-20 window, or a CLI that works in a notebook but not when packaged. The tests are built around those failure modes rather than superficial line coverage.

## Manual Validation

Before handover, run:

```bash
.venv/bin/pytest
bet-pipeline validate --input data/bets.csv --output validation_outputs
bet-pipeline build-features --input data/bets.csv --output customer_feature_output
```

The project also provides `make setup` and `make verify`. Use Python 3.10 or later; the system Python on some macOS machines is still 3.9 and will correctly fail the package requirement.

If Docker is available:

```bash
docker build -t entain-bet-pipeline .
docker run --rm -v "$(pwd)/data:/data" -v "$(pwd)/validation_outputs:/outputs" entain-bet-pipeline validate --input /data/bets.csv --output /outputs
docker run --rm -v "$(pwd)/data:/data" -v "$(pwd)/customer_feature_output:/outputs" entain-bet-pipeline build-features --input /data/bets.csv --output /outputs
```

## Future Hardening

For production, I would add property-based tests for larger monetary combinations, performance baselines, and compatibility checks between historical feature-set versions.
