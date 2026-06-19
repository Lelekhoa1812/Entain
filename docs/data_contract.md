# Data Contract

Contract version: `1.0.0`

Machine-readable contract: `source_code/src/bet_pipeline/config/schema_contract.json`

The validation job treats the source CSV as an external system boundary. Every required field is parsed and checked before a row can enter the curated bet layer.

## Input Columns

| Column | Rule | Notes |
|---|---|---|
| `bet_id` | Integer, unique | Primary row identifier for the extract. |
| `customer_id` | UUID | Entity key used for feature aggregation. |
| `bet_datetime` | Parseable datetime | Normalised to UTC ISO format in valid output. |
| `bet_num` | Positive integer | Authoritative sequence order for each customer. |
| `betting_amount` | Numeric and greater than 0 | Amount wagered in AUD. |
| `price` | Numeric and greater than 1 | Decimal odds agreed for the bet. |
| `category` | `sports` or `racing` | Whitespace is stripped and value is lower-cased before validation. |
| `stake_type` | `cash` or `bonus` | Determines payout and Entain return formulas. |
| `bet_result` | `return` or `no-return` | Determines payout and Entain return formulas. |
| `payout` | Numeric | Must match the business rule below. |
| `return_for_entain` | Numeric | Must match the business rule below. |

## Monetary Rules

Payout:

| Condition | Expected payout |
|---|---:|
| `bet_result == no-return` | `0` |
| `bet_result == return` and `stake_type == cash` | `betting_amount * price` |
| `bet_result == return` and `stake_type == bonus` | `betting_amount * (price - 1)` |

Return for Entain:

| Condition | Expected return_for_entain |
|---|---:|
| `bet_result == no-return` and `stake_type == cash` | `betting_amount` |
| `bet_result == no-return` and `stake_type == bonus` | `0` |
| `bet_result == return` and `stake_type == cash` | `betting_amount - payout` |
| `bet_result == return` and `stake_type == bonus` | `-payout` |

Monetary formulas are calculated with Python `Decimal`, rounded to cents using `ROUND_HALF_UP`, and compared with a deterministic one-cent absolute tolerance. This avoids float drift, absorbs source floating-point residue, and makes borderline currency cases reproducible.

## Quarantine Contract

A row is quarantined if it fails any rule. `invalid_bets.csv` includes:

- source row number;
- original business fields;
- canonical customer ID where the UUID can be parsed;
- normalized category, stake type, and bet result helper fields;
- expected payout where calculable;
- expected return for Entain where calculable;
- pipe-separated validation errors.

Rows with multiple defects retain all detected rule names. This is intentional: operators need the full picture when investigating upstream data quality.

## Feature Contract

Machine-readable feature definitions: `source_code/src/bet_pipeline/config/feature_definitions.json`

Feature window policy:

- validate before aggregation;
- use valid records only;
- include records where `1 <= bet_num <= 20`;
- never use later bets to replace invalid or missing early bets;
- keep partial windows visible with quality metadata.

Downstream consumers should rely on `customer_id`, stable column names, feature-set version, generation timestamp, input checksum, and `feature_quality_flag`.
