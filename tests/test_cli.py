from __future__ import annotations

import pandas as pd

from bet_pipeline.cli import main


def _row():
    return {
        "bet_id": "1",
        "customer_id": "11111111-1111-4111-8111-111111111111",
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


def test_validate_command_writes_outputs(tmp_path):
    input_path = tmp_path / "bets.csv"
    output_dir = tmp_path / "validation"
    pd.DataFrame([_row()]).to_csv(input_path, index=False)

    exit_code = main(
        [
            "validate",
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--generated-at",
            "2026-01-01T00:00:00+00:00",
            "--run-id",
            "cli-validation",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "valid_bets.csv").exists()
    assert (output_dir / "invalid_bets.csv").exists()
    assert (output_dir / "validation_report.json").exists()


def test_build_features_command_writes_outputs(tmp_path):
    input_path = tmp_path / "bets.csv"
    output_dir = tmp_path / "features"
    pd.DataFrame([_row()]).to_csv(input_path, index=False)

    exit_code = main(
        [
            "build-features",
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--generated-at",
            "2026-01-01T00:00:00+00:00",
            "--run-id",
            "cli-features",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "customer_features.csv").exists()
    assert (output_dir / "feature_build_report.json").exists()
