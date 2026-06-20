"""Surface dataset heuristics that motivated cleansing rules."""

from __future__ import annotations

from typing import Any

import pandas as pd

from bet_pipeline.io import read_bets_csv
from bet_pipeline.validate import validate_bets


DATA_PATH = "data/bets.csv"


def _normalized_failure_counts(report: dict[str, Any]) -> dict[str, int]:
    return report["failure_counts_by_rule"]


def test_expected_anomalies_are_quarantined() -> None:
    """Ensure the supplied extract still contains edge cases our rules catch."""
    raw = read_bets_csv(DATA_PATH)
    result = validate_bets(raw)
    failure_counts = _normalized_failure_counts(result.report)

    assert failure_counts["bet_datetime_decreases_with_bet_num"] >= 3000
    assert failure_counts["betting_amount_not_positive"] >= 800
    assert failure_counts["price_not_greater_than_one"] >= 1
    assert failure_counts["return_for_entain_calculation_mismatch"] >= 20


def test_distribution_matches_observations() -> None:
    """Verify the empirical shape that influenced the balancing and trimming rules."""
    raw = read_bets_csv(DATA_PATH)
    category_mix = raw["category"].value_counts(normalize=True)
    stake_mix = raw["stake_type"].value_counts(normalize=True)

    assert raw["customer_id"].nunique() == 5000
    assert category_mix.get("racing", 0) >= 0.7
    assert stake_mix.get("bonus", 0) >= 0.05

    price = pd.to_numeric(raw["price"], errors="coerce")
    betting_amount = pd.to_numeric(raw["betting_amount"], errors="coerce")

    assert price.min() < 1.0  # highlights the discrete price validation rule
    assert price.max() > 25.0
    assert betting_amount.min() < 0
    assert betting_amount.max() > 80
