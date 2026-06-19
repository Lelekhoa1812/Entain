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
