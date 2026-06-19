"""Runtime access to the packaged data and feature contracts."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=1)
def schema_contract() -> dict[str, Any]:
    """Load the schema contract shipped with the package."""
    with resources.files("bet_pipeline.config").joinpath("schema_contract.json").open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def feature_contract() -> dict[str, Any]:
    """Load the feature contract shipped with the package."""
    with resources.files("bet_pipeline.config").joinpath("feature_definitions.json").open(encoding="utf-8") as f:
        return json.load(f)


SCHEMA_CONTRACT_VERSION = schema_contract()["contract_version"]
FEATURE_SET_NAME = feature_contract()["feature_set_name"]
FEATURE_SET_VERSION = feature_contract()["feature_set_version"]

REQUIRED_COLUMNS = list(schema_contract()["required_columns"])
ALLOWED_CATEGORY = set(schema_contract()["domain_values"]["category"])
ALLOWED_STAKE_TYPE = set(schema_contract()["domain_values"]["stake_type"])
ALLOWED_BET_RESULT = set(schema_contract()["domain_values"]["bet_result"])

MONEY_SCALE = schema_contract()["money_precision"]["scale"]
MONEY_ROUNDING = schema_contract()["money_precision"]["rounding"]
MONEY_TOLERANCE_ABS = schema_contract()["money_precision"]["tolerance_abs"]

FEATURE_OUTPUT_COLUMNS = list(feature_contract()["output_columns"])
