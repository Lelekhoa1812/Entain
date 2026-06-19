# Feature Prompt

```text
Review the first-20 feature build with the assumption that the core ML contract is already understood.

Focus on whether the implementation is safe, deterministic, and non-leaky.
Check specifically:
- `bet_num` is the authoritative order, not timestamp order;
- only valid rows with `1 <= bet_num <= 20` are used;
- later bets never backfill or replace invalid early bets;
- partial windows are retained rather than silently dropped;
- output fields make the window policy and quality state explicit.

Return:
1. any leakage risk;
2. any edge case that changes customer-level counts or sequencing;
3. any test scenario that would protect the business rule.

Do not restate basic ML concepts or ask for a redesign of the feature set.
```

This was the prompt I used once the core logic existed and I wanted to be sure I wasn’t accidentally leaking later customer behaviour into the feature window.

The feature job creates one customer-level row from the first 20 bets, using `bet_num` as the authoritative sequence. That choice matters: event timestamps can be late, corrected, or inconsistent, but the task defines `bet_num` as the customer order that downstream ML consumers care about.

The job validates the raw file internally before aggregating. This repeats work if validation has already run, but it makes the command safe to execute on its own and prevents accidental feature generation from untrusted rows.

The first-20 policy is intentionally conservative:

- include valid records only;
- include only `1 <= bet_num <= 20`;
- never use bet 21 or later to replace a missing or invalid early bet;
- keep partial customer windows visible rather than dropping them silently.

The output includes the required customer features plus operational fields:

- `feature_window_policy` states the window rule in the dataset itself;
- `invalid_first20_count` shows how many quarantined early rows were excluded;
- `feature_quality_flag` separates full-quality windows from rows that need downstream filtering or review.

The invalid-window count uses canonical UUIDs from validation rather than raw customer strings, so an uppercase UUID in quarantine still matches the normalized customer feature row. The feature report also carries the feature-set version, schema contract version, input checksum, and run ID when supplied.

This keeps model training, scoring, BI, and CRM users aligned on the same semantics. A downstream team can choose to train only on `FULL_20_VALID_BETS`, but the pipeline does not hide the fact that partial windows exist.
