from __future__ import annotations

import pandas as pd
import pytest

from bet_pipeline.validate import SchemaError, validate_bets, validate_file
from bet_pipeline.contracts import (
    ALLOWED_BET_RESULT,
    ALLOWED_CATEGORY,
    ALLOWED_STAKE_TYPE,
    REQUIRED_COLUMNS,
    schema_contract,
)


CUSTOMER_A = "11111111-1111-4111-8111-111111111111"
CUSTOMER_B = "22222222-2222-4222-8222-222222222222"


def _valid_row(**overrides):
    row = {
        "bet_id": "1",
        "customer_id": CUSTOMER_A,
        "bet_datetime": "2025-01-01 10:00:00",
        "bet_num": "1",
        "betting_amount": "10.00",
        "price": "2.50",
        "category": "sports",
        "stake_type": "cash",
        "bet_result": "return",
        "payout": "25.00",
        "return_for_entain": "-15.00",
    }
    row.update(overrides)
    return row


def _errors_for_single_row(result) -> set[str]:
    return set(result.invalid_bets.loc[0, "validation_errors"].split("|"))


def test_valid_cash_return_row_passes():
    result = validate_bets(pd.DataFrame([_valid_row()]))

    assert len(result.valid_bets) == 1
    assert result.report["invalid_rows"] == 0
    assert result.report["failure_counts_by_rule"] == {}


def test_runtime_contract_matches_packaged_schema_contract():
    contract = schema_contract()

    assert REQUIRED_COLUMNS == list(contract["required_columns"])
    assert ALLOWED_CATEGORY == set(contract["domain_values"]["category"])
    assert ALLOWED_STAKE_TYPE == set(contract["domain_values"]["stake_type"])
    assert ALLOWED_BET_RESULT == set(contract["domain_values"]["bet_result"])


def test_missing_required_column_raises_schema_error():
    frame = pd.DataFrame([_valid_row()]).drop(columns=["payout"])

    with pytest.raises(SchemaError, match="payout"):
        validate_bets(frame)


def test_invalid_uuid_and_datetime_are_reported_together():
    result = validate_bets(pd.DataFrame([_valid_row(customer_id="not-a-uuid", bet_datetime="bad-date")]))

    assert _errors_for_single_row(result) == {"customer_id_not_uuid", "bet_datetime_not_parseable"}


def test_non_integer_and_non_positive_bet_num_rules():
    decimal_result = validate_bets(pd.DataFrame([_valid_row(bet_num="1.5")]))
    zero_result = validate_bets(pd.DataFrame([_valid_row(bet_num="0")]))

    assert "bet_num_not_integer" in _errors_for_single_row(decimal_result)
    assert "bet_num_not_positive" in _errors_for_single_row(zero_result)


@pytest.mark.parametrize(
    ("stake_type", "payout", "return_for_entain"),
    [
        ("cash", "60.00", "-40.00"),
        ("bonus", "40.00", "-40.00"),
    ],
)
def test_return_payout_rules_for_cash_and_bonus(stake_type, payout, return_for_entain):
    row = _valid_row(stake_type=stake_type, betting_amount="20.00", price="3.00", payout=payout, return_for_entain=return_for_entain)

    result = validate_bets(pd.DataFrame([row]))

    assert len(result.valid_bets) == 1


def test_no_return_rules_for_cash_and_bonus():
    rows = [
        _valid_row(bet_id="1", bet_result="no-return", stake_type="cash", payout="0.00", return_for_entain="10.00"),
        _valid_row(bet_id="2", bet_num="2", bet_result="no-return", stake_type="bonus", payout="0.00", return_for_entain="0.00"),
    ]

    result = validate_bets(pd.DataFrame(rows))

    assert len(result.valid_bets) == 2


def test_payout_and_return_mismatches_are_separate_rules():
    payout_result = validate_bets(pd.DataFrame([_valid_row(payout="24.00")]))
    return_result = validate_bets(pd.DataFrame([_valid_row(return_for_entain="-14.00")]))

    assert "payout_calculation_mismatch" in _errors_for_single_row(payout_result)
    assert "return_for_entain_calculation_mismatch" in _errors_for_single_row(return_result)


def test_duplicate_bet_id_quarantines_all_duplicate_rows():
    frame = pd.DataFrame(
        [
            _valid_row(bet_id="1", bet_num="1"),
            _valid_row(bet_id="1", bet_num="2", bet_datetime="2025-01-01 11:00:00"),
        ]
    )

    result = validate_bets(frame)

    assert len(result.invalid_bets) == 2
    assert result.report["failure_counts_by_rule"]["bet_id_not_unique"] == 2


def test_duplicate_customer_bet_number_is_quarantined():
    frame = pd.DataFrame(
        [
            _valid_row(bet_id="1", bet_num="1"),
            _valid_row(bet_id="2", bet_num="1", bet_datetime="2025-01-01 11:00:00"),
        ]
    )

    result = validate_bets(frame)

    assert len(result.invalid_bets) == 2
    assert result.report["failure_counts_by_rule"]["customer_bet_num_not_unique"] == 2


def test_datetime_must_not_decrease_as_bet_num_increases():
    frame = pd.DataFrame(
        [
            _valid_row(bet_id="1", bet_num="1", bet_datetime="2025-01-02 10:00:00"),
            _valid_row(bet_id="2", bet_num="2", bet_datetime="2025-01-01 10:00:00"),
        ]
    )

    result = validate_bets(frame)

    assert len(result.invalid_bets) == 1
    assert "bet_datetime_decreases_with_bet_num" in result.invalid_bets.loc[0, "validation_errors"]


def test_multiple_failures_are_preserved_on_one_row():
    result = validate_bets(
        pd.DataFrame(
            [
                _valid_row(
                    customer_id=CUSTOMER_B,
                    category="casino",
                    betting_amount="-1.00",
                    price="1.00",
                    bet_result="settled",
                    payout="not-money",
                )
            ]
        )
    )

    assert _errors_for_single_row(result) == {
        "betting_amount_not_positive",
        "price_not_greater_than_one",
        "category_not_allowed",
        "bet_result_not_allowed",
        "payout_not_numeric",
    }


def test_quarantine_preserves_raw_text_and_adds_normalized_helpers():
    row = _valid_row(category=" Sports ", stake_type=" CASH ", betting_amount="-1.00")

    result = validate_bets(pd.DataFrame([row]))
    invalid = result.invalid_bets.iloc[0]

    assert invalid["category"] == " Sports "
    assert invalid["stake_type"] == " CASH "
    assert invalid["category_normalized"] == "sports"
    assert invalid["stake_type_normalized"] == "cash"
    assert invalid["canonical_customer_id"] == CUSTOMER_A


def test_extra_columns_are_reported_without_failing_valid_rows():
    row = _valid_row(extra_source_field="kept outside contract")

    result = validate_bets(pd.DataFrame([row]))

    assert len(result.valid_bets) == 1
    assert result.report["extra_columns"] == ["extra_source_field"]


def test_decimal_money_rules_use_exact_cent_precision():
    accepted = validate_bets(pd.DataFrame([_valid_row(betting_amount="10.005", price="2.00", payout="20.01", return_for_entain="-10.01")]))
    rejected = validate_bets(pd.DataFrame([_valid_row(betting_amount="10.005", price="2.00", payout="19.99", return_for_entain="-10.01")]))

    assert len(accepted.valid_bets) == 1
    assert "payout_calculation_mismatch" in _errors_for_single_row(rejected)


def test_validate_file_writes_expected_outputs(tmp_path):
    input_path = tmp_path / "bets.csv"
    output_dir = tmp_path / "validation"
    pd.DataFrame([_valid_row()]).to_csv(input_path, index=False)

    result = validate_file(input_path, output_dir, generated_at="2026-01-01T00:00:00+00:00", run_id="unit-run")

    assert result.report["valid_rows"] == 1
    assert result.report["generated_at"] == "2026-01-01T00:00:00+00:00"
    assert result.report["run_id"] == "unit-run"
    assert "input_sha256" in result.report["input_metadata"]
    assert "schema_contract_version" in result.report
    assert (output_dir / "valid_bets.csv").exists()
    assert (output_dir / "invalid_bets.csv").exists()
    assert (output_dir / "validation_report.json").exists()
