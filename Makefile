.PHONY: setup validate features test verify clean

PYTHON ?= python3

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev,parquet]"

validate:
	PYTHONPATH=source_code/src python -m bet_pipeline.cli validate --input data/bets.csv --output validation_outputs

features:
	PYTHONPATH=source_code/src python -m bet_pipeline.cli build-features --input data/bets.csv --output customer_feature_output

test:
	PYTHONPATH=source_code/src pytest

verify:
	.venv/bin/pytest
	.venv/bin/bet-pipeline validate --input data/bets.csv --output validation_outputs --generated-at 2026-06-19T01:49:26+00:00 --run-id submitted-validation
	.venv/bin/bet-pipeline build-features --input data/bets.csv --output customer_feature_output --generated-at 2026-06-19T01:49:39+00:00 --run-id submitted-feature-build

clean:
	rm -rf validation_outputs/* customer_feature_output/* .pytest_cache
