# Task Breakdown

This document maps the assessment brief to the implemented deliverables.

| Requirement | Implementation |
|---|---|
| Use Python | Installable package under `source_code/src/bet_pipeline`. |
| Keep local and batch-oriented | CLI commands read local CSV and write local output directories. |
| Do not train a model | The project validates data and builds features only. |
| Do not build an API | No service layer or HTTP dependency is included. |
| Validate business rules | `validate.py` implements schema, domain, numeric, monetary, uniqueness, and ordering checks. |
| Produce valid/invalid/report outputs | `validation_outputs/valid_bets.csv`, `invalid_bets.csv`, and `validation_report.json`. |
| Build first-20 customer features | `build_features.py` aggregates valid rows where `1 <= bet_num <= 20`. |
| Package and CLI | `pyproject.toml` exposes the `bet-pipeline` entry point. |
| Dockerise | `Dockerfile` installs the package and uses the CLI as entry point. |
| Tests | Unit and CLI tests live under `tests/`. |
| Architecture diagram and design note | `architecture_diagram/` and `design_note/system_design_note.md`. |

## Implementation Sequence

1. Define the input contract and required business rules.
2. Parse raw values inside validation rather than trusting pandas inference.
3. Quarantine any row with one or more failures.
4. Emit a machine-readable validation report for operators and automation.
5. Build customer features from validated first-20 windows.
6. Publish feature quality metadata so downstream users can filter deliberately.
7. Package the CLI and Docker image.
8. Test the business logic and command surface.
9. Regenerate outputs from the full provided dataset.

## Acceptance Checklist

- `pytest` passes.
- `bet-pipeline validate` runs on `data/bets.csv`.
- `bet-pipeline build-features` runs on `data/bets.csv`.
- Outputs are generated from the full dataset, not a small sample.
- README and design notes explain the main decisions in business and engineering terms.
- Architecture material includes raw landing, scheduler, validation, quarantine, curated layer, feature generation, feature output, metadata/config, monitoring, downstream consumers, and rerun/backfill path.
