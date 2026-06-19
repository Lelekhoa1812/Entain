from __future__ import annotations

import pandas as pd
import pytest

from bet_pipeline.build_features import build_customer_features, build_features_file


CUSTOMER_A = "11111111-1111-4111-8111-111111111111"
CUSTOMER_B = "22222222-2222-4222-8222-222222222222"
FIXED_TIME = "2026-01-01T00:00:00+00:00"


def _row(
    bet_num: int,
    *,
    amount: float = 10.0,
    customer_id: str = CUSTOMER_A,
    valid: bool = True,
    bet_id_offset: int = 100,
):
    result = "return" if bet_num % 2 == 0 else "no-return"
    stake = "cash"
    price = 2.0
    payout = amount * price if result == "return" else 0.0
    entain_return = amount - payout if result == "return" else amount
    if not valid:
        amount = -1.0
        payout = 0.0
        entain_return = 0.0
    return {
        "bet_id": str(bet_id_offset + bet_num),
        "customer_id": customer_id,
        "bet_datetime": f"2025-01-{bet_num:02d} 10:00:00",
        "bet_num": str(bet_num),
        "betting_amount": f"{amount:.2f}",
        "price": f"{price:.2f}",
        "category": "racing" if bet_num % 2 == 0 else "sports",
        "stake_type": stake,
        "bet_result": result,
        "payout": f"{payout:.2f}",
        "return_for_entain": f"{entain_return:.2f}",
    }


def test_feature_aggregations_for_full_customer_window():
    result = build_customer_features(pd.DataFrame([_row(i, amount=10.0) for i in range(1, 21)]), generated_at=FIXED_TIME)
    record = result.customer_features.iloc[0]

    assert record["bets_used"] == 20
    assert record["total_betting_amount"] == 200.0
    assert record["mean_betting_amount"] == 10.0
    assert record["pct_racing"] == 0.5
    assert record["pct_cash"] == 1.0
    assert record["pct_return"] == 0.5
    assert record["first_bet_datetime"] == "2025-01-01T10:00:00Z"
    assert record["twentieth_bet_datetime"] == "2025-01-20T10:00:00Z"
    assert record["feature_generated_at"] == FIXED_TIME
    assert record["feature_quality_flag"] == "FULL_20_VALID_BETS"


def test_first20_features_do_not_replace_invalid_early_bet_with_later_bet():
    rows = [_row(i) for i in range(1, 22)]
    rows[4] = _row(5, valid=False)

    result = build_customer_features(pd.DataFrame(rows), generated_at=FIXED_TIME)
    record = result.customer_features.iloc[0]

    assert record["bets_used"] == 19
    assert record["invalid_first20_count"] == 1
    assert record["feature_quality_flag"] == "PARTIAL_OR_REVIEW_FIRST20_WINDOW"
    assert record["twentieth_bet_datetime"] == "2025-01-20T10:00:00Z"


def test_invalid_first20_count_uses_canonical_customer_id():
    rows = [_row(i) for i in range(1, 21)]
    invalid_upper_uuid = _row(5, valid=False)
    invalid_upper_uuid["customer_id"] = CUSTOMER_A.upper()
    rows[4] = invalid_upper_uuid

    result = build_customer_features(pd.DataFrame(rows), generated_at=FIXED_TIME)
    record = result.customer_features.iloc[0]

    assert record["customer_id"] == CUSTOMER_A
    assert record["invalid_first20_count"] == 1
    assert record["feature_quality_flag"] == "PARTIAL_OR_REVIEW_FIRST20_WINDOW"


def test_partial_window_without_bet_20_has_null_twentieth_datetime():
    result = build_customer_features(pd.DataFrame([_row(i) for i in range(1, 6)]), generated_at=FIXED_TIME)
    record = result.customer_features.iloc[0]

    assert record["bets_used"] == 5
    assert pd.isna(record["twentieth_bet_datetime"])
    assert record["feature_quality_flag"] == "PARTIAL_OR_REVIEW_FIRST20_WINDOW"


def test_all_invalid_input_returns_empty_feature_frame():
    result = build_customer_features(pd.DataFrame([_row(1, valid=False)]), generated_at=FIXED_TIME)

    assert result.customer_features.empty
    assert result.report["customer_count"] == 0
    assert result.report["customers_without_valid_first_window_count"] == 1


def test_customers_without_valid_first_window_are_counted():
    rows = [_row(i, customer_id=CUSTOMER_A) for i in range(21, 24)]
    rows.extend(_row(i, customer_id=CUSTOMER_B, bet_id_offset=200) for i in range(1, 3))

    result = build_customer_features(pd.DataFrame(rows), generated_at=FIXED_TIME)

    assert len(result.customer_features) == 1
    assert result.customer_features.loc[0, "customer_id"] == CUSTOMER_B
    assert result.report["customers_without_valid_first_window_count"] == 1


def test_first_n_bets_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        build_customer_features(pd.DataFrame([_row(1)]), first_n_bets=0)


def test_build_features_file_writes_csv_report_and_optional_parquet_metadata(tmp_path):
    input_path = tmp_path / "bets.csv"
    output_dir = tmp_path / "features"
    pd.DataFrame([_row(i) for i in range(1, 3)]).to_csv(input_path, index=False)

    result = build_features_file(input_path, output_dir, generated_at=FIXED_TIME, run_id="feature-unit-run")

    assert result.report["customer_count"] == 1
    assert result.report["generated_at"] == FIXED_TIME
    assert result.report["run_id"] == "feature-unit-run"
    assert result.report["feature_set_version"] == "1.0.0"
    assert "input_sha256" in result.report["input_metadata"]
    assert (output_dir / "customer_features.csv").exists()
    assert (output_dir / "feature_build_report.json").exists()
    assert "csv" in result.report["table_outputs"]


def test_small_golden_feature_fixture_is_stable():
    rows = [_row(1, amount=5.0), _row(2, amount=7.0), _row(3, valid=False), _row(4, amount=11.0)]

    result = build_customer_features(pd.DataFrame(rows), first_n_bets=4, generated_at=FIXED_TIME, run_id="golden")
    record = result.customer_features.iloc[0].to_dict()

    assert record == {
        "customer_id": CUSTOMER_A,
        "first_bet_datetime": "2025-01-01T10:00:00Z",
        "twentieth_bet_datetime": "2025-01-04T10:00:00Z",
        "bets_used": 3,
        "total_betting_amount": 23.0,
        "mean_betting_amount": 7.6667,
        "mean_price": 2.0,
        "pct_racing": 0.666667,
        "pct_cash": 1.0,
        "pct_return": 0.666667,
        "total_payout": 36.0,
        "total_return_for_entain": -13.0,
        "feature_generated_at": FIXED_TIME,
        "feature_window_policy": "valid rows where 1 <= bet_num <= 4; no replacement from later bets",
        "invalid_first20_count": 1,
        "feature_quality_flag": "PARTIAL_OR_REVIEW_FIRST20_WINDOW",
    }
