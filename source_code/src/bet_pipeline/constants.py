"""Shared constants for the betting batch pipeline.

The values that form the public data contract are loaded from the packaged
JSON contract so documentation and runtime behavior cannot quietly diverge.
"""

from __future__ import annotations

from bet_pipeline.contracts import (
    ALLOWED_BET_RESULT,
    ALLOWED_CATEGORY,
    ALLOWED_STAKE_TYPE,
    MONEY_TOLERANCE_ABS,
    REQUIRED_COLUMNS,
)

TEXT_COLUMNS = ["category", "stake_type", "bet_result"]

MONEY_TOLERANCE = MONEY_TOLERANCE_ABS
DEFAULT_FIRST_N_BETS = 20
