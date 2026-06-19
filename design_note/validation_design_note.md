# Validation Prompt

```text
Review the validation job as a quality gate, not as a beginner exercise.

Assume the core schema and data contract are already known. Focus on whether the validation layer is strong enough to protect downstream ML and analytics consumers.

Check for:
- raw input handled as strings before parsing;
- all failures collected per row, not just the first one;
- required columns and type parsing;
- domain, uniqueness, ordering, and monetary formula checks;
- quarantine output that is actionable for operators;
- JSON/reporting that makes defect counts and row counts trustworthy.

Return only:
1. missing or weak validation rules;
2. ambiguous rules that need an explicit policy;
3. tests that would catch a regression in the gate.

Do not explain generic validation theory.
```

This was the bit I cared about most. If the validation is weak, the rest of the pipeline can look fine while still producing bad output.

The validation job is the quality gate between the raw betting extract and anything an ML or analytics consumer should trust. The source file is read as strings, then parsed and checked inside the validation layer so bad values are not hidden by automatic type coercion. The runtime loads the packaged schema contract, which keeps domain values and required columns from drifting away from the documented contract.

The job deliberately collects multiple failures per row. In real data operations, a row with an invalid category can also have a bad payout or malformed timestamp; stopping at the first error slows investigation and makes defect counts misleading.

The row-level checks cover:

- required schema columns;
- integer keys and positive `bet_num`;
- UUID and datetime parseability;
- numeric `betting_amount`, `price`, `payout`, and `return_for_entain`;
- allowed domains for category, stake type, and bet result;
- payout and return-for-Entain formulas;
- unique `bet_id`;
- unique `(customer_id, bet_num)`;
- non-decreasing `bet_datetime` as `bet_num` increases for a customer.

Invalid rows are written to `invalid_bets.csv` with the source row number, original values, canonical customer ID where parseable, normalized helper fields, expected monetary values where they can be calculated, and pipe-separated rule names. The JSON report gives operators the aggregate view: row counts, invalid rate, failure counts by rule, Decimal money policy, contract version, input checksum, extra columns, output contract, and non-fatal sequence warnings.

The guiding principle is simple: valid output should be boring and dependable; invalid output should be rich enough for a human to investigate without rerunning the pipeline in a debugger.
