# Selective AI Assistance Note

I used AI the way I’d use a sharp second set of eyes: to sanity-check assumptions, catch edge cases, and tighten the handover. The actual design calls, implementation, and final sign-off were mine.

## Guardrails

- Keep each prompt scoped to one area.
- Point the model at the exact files I want checked.
- Ask for risks, gaps, and test ideas before asking for edits.
- Cross-check anything useful against the task brief, the data, and runnable tests.
- Treat the output as review input, not as an answer key.
- Re-run the relevant commands myself after each change.

## Prompt Style

I kept the prompts short on purpose. The goal was not to have the model explain the basics back to me. It was to pressure-test decisions I had already made and make sure I wasn’t missing a boring but important detail.

## Example Prompt 1: Validation Review

I started by checking the validation layer because that’s the part that can quietly ruin everything downstream if it’s loose.

```text
Review @docs/jr-mle-task.docx and @source_code/src/bet_pipeline/validate.py.

Focus only on validation correctness. Check whether the code covers:
- required columns;
- numeric constraints;
- allowed domain values;
- payout and return_for_entain formulas;
- duplicate bet_id;
- duplicate (customer_id, bet_num);
- bet_datetime ordering by bet_num.

Return only:
1. missing rules;
2. ambiguous rules that need a documented policy;
3. test cases that would catch regressions.

Do not rewrite the code in this pass.
```

## Example Prompt 2: Feature-Window Edge Cases

This was mostly about the first-20 window and keeping later activity from creeping into the feature build.

```text
Review @source_code/src/bet_pipeline/build_features.py and @tests/test_features.py.

The intended policy is:
- validate raw rows before aggregation;
- use bet_num as authoritative order;
- include only valid rows where 1 <= bet_num <= 20;
- never use bet_num > 20 to replace an invalid early bet;
- keep partial windows visible.

Identify edge cases that should be tested. Prioritise cases that could create ML leakage or silently drop customers.
```

## Example Prompt 3: CLI and Packaging Check

I wanted to make sure the repo worked like a package and not just as a set of scripts that only behave in one developer shell.

```text
Inspect @pyproject.toml, @Dockerfile, @Makefile, and @source_code/src/bet_pipeline/cli.py.

Check whether a reviewer can run:
- bet-pipeline validate --input data/bets.csv --output validation_outputs
- bet-pipeline build-features --input data/bets.csv --output customer_feature_output
- docker build -t entain-bet-pipeline .

List packaging or path mismatches only. Do not suggest unrelated refactors.
```

## Example Prompt 4: Documentation Review

This was a plain handover pass. I was looking for anything that would confuse a reviewer, an operator, or a teammate coming in cold.

```text
Review @README.md, @docs/data_contract.md, @docs/operations_runbook.md, and @design_note/system_design_note.md.

Audience:
- ML/data engineering reviewers;
- downstream data consumers;
- operators who need to rerun the batch.

Check for:
- unclear command examples;
- missing output contracts;
- undocumented trade-offs;
- wording that sounds generated or vague.

Suggest concise improvements in a senior engineering voice.
```

## Example Prompt 5: Test Coverage Audit

After the implementation was in place, I used AI as a checklist to see whether the tests really matched the riskiest parts of the task.

```text
Review @tests/ against @docs/jr-mle-task.docx.

Map tests to the assessment requirements and identify gaps. Focus on high-risk logic:
- formula correctness;
- duplicate keys;
- multiple failures on one invalid row;
- invalid early bets inside the first-20 window;
- all-invalid or partial feature windows;
- CLI file outputs.

Return a short coverage table and any missing tests.
```

## Example Prompt 6: Release and Handover QA

This was the last pass before calling it done. I wanted to know whether the story was clear enough for someone else to pick up without a guided tour.

```text
Review @README.md, @docs/, @design_note/, and the runnable commands in the repo.

Assume the implementation is done. Focus on whether a reviewer can:
- understand the data contract quickly;
- reproduce validation and feature outputs;
- see how AI was used without it becoming the story;
- confirm the project is ready to ship and maintain.

Return:
1. any missing handover detail;
2. any release risk;
3. any documentation gap that would slow a teammate down.

Do not ask for trivial stylistic changes.
```

## How Suggestions Were Accepted

I only kept suggestions that matched the task brief, improved deterministic behaviour, or made the handover easier to trust. If something felt clever but didn’t change the result, I left it out. The final checks were always executable:

```bash
pytest
bet-pipeline validate --input data/bets.csv --output validation_outputs
bet-pipeline build-features --input data/bets.csv --output customer_feature_output
docker build -t entain-bet-pipeline .
```

The Docker validation and feature commands were also run against the full input file after Docker was available.
