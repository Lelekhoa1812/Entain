"""Validation rules for the raw betting extract."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable
from uuid import UUID

import numpy as np
import pandas as pd

from bet_pipeline.contracts import SCHEMA_CONTRACT_VERSION, schema_contract
from bet_pipeline.constants import (
    ALLOWED_BET_RESULT,
    ALLOWED_CATEGORY,
    ALLOWED_STAKE_TYPE,
    MONEY_TOLERANCE,
    REQUIRED_COLUMNS,
    TEXT_COLUMNS,
)
from bet_pipeline.io import ensure_dir, file_sha256, read_bets_csv, write_csv, write_json


CANONICAL_BET_COLUMNS = [
    "bet_id",
    "customer_id",
    "bet_datetime",
    "bet_num",
    "betting_amount",
    "price",
    "category",
    "stake_type",
    "bet_result",
    "payout",
    "return_for_entain",
]

NORMALIZED_TEXT_COLUMNS = {col: f"{col}_normalized" for col in TEXT_COLUMNS}
MONEY_SCALE = Decimal(str(schema_contract()["money_precision"]["scale"]))
MONEY_ROUNDING = ROUND_HALF_UP
MONEY_TOLERANCE_DECIMAL = Decimal(str(schema_contract()["money_precision"]["tolerance_abs"]))


@dataclass(frozen=True)
class ValidationResult:
    valid_bets: pd.DataFrame
    invalid_bets: pd.DataFrame
    report: dict


class SchemaError(ValueError):
    """Raised when an input file is missing mandatory columns."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_uuid(value: object) -> str | None:
    try:
        return str(UUID(str(value)))
    except Exception:
        return None


def _as_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _as_integer(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    is_int_like = numeric.notna() & np.isclose(numeric, np.floor(numeric))
    return numeric.where(is_int_like)


def _parse_decimal(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value).strip())
        return parsed if parsed.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _money_to_cents(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(MONEY_SCALE, rounding=MONEY_ROUNDING)


def _money_matches(observed: Decimal | None, expected: Decimal | None) -> bool:
    observed_cents = _money_to_cents(observed)
    expected_cents = _money_to_cents(expected)
    if observed_cents is None or expected_cents is None:
        return False
    return abs(observed_cents - expected_cents) <= MONEY_TOLERANCE_DECIMAL


def _decimal_series(series: pd.Series) -> pd.Series:
    return series.map(_parse_decimal)


def _decimal_is_missing(series: pd.Series) -> pd.Series:
    return series.map(lambda value: value is None)


def _decimal_le(series: pd.Series, threshold: Decimal) -> pd.Series:
    return series.map(lambda value: value is not None and value <= threshold)


def _append_error(errors: list[list[str]], mask: Iterable[bool], rule_name: str) -> None:
    for idx, failed in enumerate(mask):
        if bool(failed):
            errors[idx].append(rule_name)


def _calculate_expected_money(df: pd.DataFrame, can_check_money: pd.Series) -> pd.DataFrame:
    """Attach Decimal expected payout/return values for rows with enough clean fields."""
    df = df.copy()
    df["expected_payout_decimal"] = None
    df["expected_return_for_entain_decimal"] = None

    no_return = can_check_money & df["bet_result_normalized"].eq("no-return")
    cash_return = can_check_money & df["bet_result_normalized"].eq("return") & df["stake_type_normalized"].eq("cash")
    bonus_return = can_check_money & df["bet_result_normalized"].eq("return") & df["stake_type_normalized"].eq("bonus")

    df.loc[no_return, "expected_payout_decimal"] = Decimal("0")
    df.loc[cash_return, "expected_payout_decimal"] = df.loc[cash_return].apply(
        lambda row: row["betting_amount_decimal"] * row["price_decimal"], axis=1
    )
    df.loc[bonus_return, "expected_payout_decimal"] = df.loc[bonus_return].apply(
        lambda row: row["betting_amount_decimal"] * (row["price_decimal"] - Decimal("1")), axis=1
    )

    df.loc[no_return & df["stake_type_normalized"].eq("cash"), "expected_return_for_entain_decimal"] = df.loc[
        no_return & df["stake_type_normalized"].eq("cash"), "betting_amount_decimal"
    ]
    df.loc[no_return & df["stake_type_normalized"].eq("bonus"), "expected_return_for_entain_decimal"] = Decimal("0")
    df.loc[cash_return, "expected_return_for_entain_decimal"] = df.loc[cash_return].apply(
        lambda row: row["betting_amount_decimal"] - row["expected_payout_decimal"], axis=1
    )
    df.loc[bonus_return, "expected_return_for_entain_decimal"] = df.loc[bonus_return].apply(
        lambda row: -row["expected_payout_decimal"], axis=1
    )
    df["expected_payout"] = df["expected_payout_decimal"].map(_money_to_cents).map(lambda v: None if v is None else f"{v:.2f}")
    df["expected_return_for_entain"] = (
        df["expected_return_for_entain_decimal"].map(_money_to_cents).map(lambda v: None if v is None else f"{v:.2f}")
    )
    return df


def _normalise_raw_frame(raw: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in raw.columns]
    if missing_columns:
        raise SchemaError(f"Input is missing required columns: {missing_columns}")

    df = raw.copy()
    for col in TEXT_COLUMNS:
        df[NORMALIZED_TEXT_COLUMNS[col]] = df[col].astype(str).str.strip().str.lower()

    # Keep input order around so quarantine output stays stable and easy to diff.
    df.insert(0, "source_row_number", range(2, len(df) + 2))

    df["bet_id_num"] = _as_integer(df["bet_id"])
    df["bet_num_num"] = _as_integer(df["bet_num"])
    df["betting_amount_num"] = _as_numeric(df["betting_amount"])
    df["price_num"] = _as_numeric(df["price"])
    df["payout_num"] = _as_numeric(df["payout"])
    df["return_for_entain_num"] = _as_numeric(df["return_for_entain"])
    df["betting_amount_decimal"] = _decimal_series(df["betting_amount"])
    df["price_decimal"] = _decimal_series(df["price"])
    df["payout_decimal"] = _decimal_series(df["payout"])
    df["return_for_entain_decimal"] = _decimal_series(df["return_for_entain"])
    df["bet_datetime_ts"] = pd.to_datetime(df["bet_datetime"], errors="coerce", utc=True)
    df["customer_uuid"] = df["customer_id"].map(_parse_uuid)
    df["canonical_customer_id"] = df["customer_uuid"]
    return df


def _order_violation_mask(df: pd.DataFrame, duplicate_customer_bet_num: pd.Series) -> pd.Series:
    """Flag rows where event time moves backwards as bet_num increases."""
    candidates = df[
        df["customer_uuid"].notna()
        & df["bet_num_num"].notna()
        & df["bet_datetime_ts"].notna()
        & ~duplicate_customer_bet_num
    ].copy()
    if candidates.empty:
        return pd.Series(False, index=df.index)

    ordered = candidates.sort_values(["customer_uuid", "bet_num_num", "bet_datetime_ts", "bet_id_num"])
    previous_ts = ordered.groupby("customer_uuid")["bet_datetime_ts"].shift()
    violating_index = ordered.index[previous_ts.notna() & (ordered["bet_datetime_ts"] < previous_ts)]
    mask = pd.Series(False, index=df.index)
    mask.loc[violating_index] = True
    return mask


def _sequence_warnings(df: pd.DataFrame) -> list[dict]:
    """Summarise gaps without failing the rows."""
    warnings = []
    sequence_candidates = df[df["customer_uuid"].notna() & df["bet_num_num"].notna() & (df["bet_num_num"] > 0)]
    for customer_id, group in sequence_candidates.groupby("customer_uuid"):
        observed = sorted(set(group["bet_num_num"].astype(int).tolist()))
        expected = set(range(1, max(observed) + 1))
        missing = sorted(expected.difference(observed))
        if missing:
            warnings.append(
                {
                    "customer_id": customer_id,
                    "max_bet_num_observed": max(observed),
                    "missing_bet_nums": missing[:50],
                    "missing_count": len(missing),
                }
            )
    return warnings


def validate_bets(
    raw: pd.DataFrame,
    generated_at: str | None = None,
    run_id: str | None = None,
    input_metadata: dict | None = None,
) -> ValidationResult:
    """Split a raw bets DataFrame into valid rows, quarantined rows, and a report."""
    df = _normalise_raw_frame(raw)
    generated_at = generated_at or _utc_now_iso()
    extra_columns = [col for col in raw.columns if col not in REQUIRED_COLUMNS]
    errors: list[list[str]] = [[] for _ in range(len(df))]

    # Cheap single-field checks first. Later checks rely on these parsed columns.
    _append_error(errors, df["bet_id_num"].isna(), "bet_id_not_integer")
    _append_error(errors, df["customer_uuid"].isna(), "customer_id_not_uuid")
    _append_error(errors, df["bet_datetime_ts"].isna(), "bet_datetime_not_parseable")
    _append_error(errors, df["bet_num_num"].isna(), "bet_num_not_integer")
    _append_error(errors, df["bet_num_num"].notna() & (df["bet_num_num"] <= 0), "bet_num_not_positive")
    _append_error(errors, _decimal_is_missing(df["betting_amount_decimal"]), "betting_amount_not_numeric")
    _append_error(errors, _decimal_le(df["betting_amount_decimal"], Decimal("0")), "betting_amount_not_positive")
    _append_error(errors, _decimal_is_missing(df["price_decimal"]), "price_not_numeric")
    _append_error(errors, _decimal_le(df["price_decimal"], Decimal("1")), "price_not_greater_than_one")
    _append_error(errors, ~df["category_normalized"].isin(ALLOWED_CATEGORY), "category_not_allowed")
    _append_error(errors, ~df["stake_type_normalized"].isin(ALLOWED_STAKE_TYPE), "stake_type_not_allowed")
    _append_error(errors, ~df["bet_result_normalized"].isin(ALLOWED_BET_RESULT), "bet_result_not_allowed")
    _append_error(errors, _decimal_is_missing(df["payout_decimal"]), "payout_not_numeric")
    _append_error(errors, _decimal_is_missing(df["return_for_entain_decimal"]), "return_for_entain_not_numeric")

    # A duplicate id or duplicate customer/bet_num pair is ambiguous, so both
    # sides of the duplicate are quarantined rather than trying to guess.
    duplicate_bet_id = df["bet_id_num"].notna() & df.duplicated("bet_id_num", keep=False)
    _append_error(errors, duplicate_bet_id, "bet_id_not_unique")

    duplicate_customer_bet_num = (
        df["customer_uuid"].notna()
        & df["bet_num_num"].notna()
        & df.duplicated(["customer_uuid", "bet_num_num"], keep=False)
    )
    _append_error(errors, duplicate_customer_bet_num, "customer_bet_num_not_unique")

    # Only check money math when the inputs are sane; otherwise the row already
    # has clearer validation errors and the calculated fields would be noise.
    can_check_money = (
        ~_decimal_is_missing(df["betting_amount_decimal"])
        & ~_decimal_le(df["betting_amount_decimal"], Decimal("0"))
        & ~_decimal_is_missing(df["price_decimal"])
        & ~_decimal_le(df["price_decimal"], Decimal("1"))
        & df["stake_type_normalized"].isin(ALLOWED_STAKE_TYPE)
        & df["bet_result_normalized"].isin(ALLOWED_BET_RESULT)
        & ~_decimal_is_missing(df["payout_decimal"])
        & ~_decimal_is_missing(df["return_for_entain_decimal"])
    )
    df = _calculate_expected_money(df, can_check_money)
    payout_mismatch = can_check_money & ~df.apply(
        lambda row: _money_matches(row["payout_decimal"], row["expected_payout_decimal"]), axis=1
    )
    _append_error(errors, payout_mismatch, "payout_calculation_mismatch")

    can_check_return = can_check_money & ~payout_mismatch
    return_mismatch = can_check_return & ~df.apply(
        lambda row: _money_matches(row["return_for_entain_decimal"], row["expected_return_for_entain_decimal"]),
        axis=1,
    )
    _append_error(errors, return_mismatch, "return_for_entain_calculation_mismatch")

    # bet_num is treated as the customer sequence. If timestamps go backwards,
    # the row is still suspect even if the individual timestamp parses.
    _append_error(errors, _order_violation_mask(df, duplicate_customer_bet_num), "bet_datetime_decreases_with_bet_num")

    df["validation_errors"] = ["|".join(row_errors) for row_errors in errors]
    df["is_valid"] = df["validation_errors"].eq("")

    valid = df[df["is_valid"]].copy()
    if not valid.empty:
        valid["bet_id"] = valid["bet_id_num"].astype("int64")
        valid["customer_id"] = valid["customer_uuid"]
        valid["bet_datetime"] = valid["bet_datetime_ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        valid["bet_num"] = valid["bet_num_num"].astype("int64")
        valid["category"] = valid["category_normalized"]
        valid["stake_type"] = valid["stake_type_normalized"]
        valid["bet_result"] = valid["bet_result_normalized"]
        valid["betting_amount"] = valid["betting_amount_decimal"].map(_money_to_cents).astype(float)
        valid["price"] = valid["price_decimal"].map(lambda v: float(v) if v is not None else np.nan).round(4)
        valid["payout"] = valid["payout_decimal"].map(_money_to_cents).astype(float)
        valid["return_for_entain"] = valid["return_for_entain_decimal"].map(_money_to_cents).astype(float)
    valid = valid[CANONICAL_BET_COLUMNS].sort_values(["customer_id", "bet_num", "bet_id"]).reset_index(drop=True)

    invalid_cols = [
        "source_row_number",
        *CANONICAL_BET_COLUMNS,
        "canonical_customer_id",
        "category_normalized",
        "stake_type_normalized",
        "bet_result_normalized",
        "expected_payout",
        "expected_return_for_entain",
        "validation_errors",
    ]
    invalid = df[~df["is_valid"]][invalid_cols].copy().reset_index(drop=True)

    all_errors = [rule for row_errors in errors for rule in row_errors]
    failure_counts = dict(sorted(Counter(all_errors).items()))

    report = {
        "generated_at": generated_at,
        "run_id": run_id,
        "schema_contract_version": SCHEMA_CONTRACT_VERSION,
        "input_metadata": input_metadata or {},
        "input_rows": int(len(df)),
        "valid_rows": int(len(valid)),
        "invalid_rows": int(len(invalid)),
        "invalid_row_rate": round(float(len(invalid) / len(df)), 6) if len(df) else 0.0,
        "extra_columns": extra_columns,
        "failure_counts_by_rule": failure_counts,
        "valid_output_contract": CANONICAL_BET_COLUMNS,
        "money_precision": schema_contract()["money_precision"],
        "money_tolerance_abs": MONEY_TOLERANCE,
        "non_fatal_sequence_warnings": _sequence_warnings(df),
        "notes": [
            "Any row with at least one failure is written to invalid_bets.csv.",
            "Category, stake_type, and bet_result are stripped and lowercased before rule checks.",
            "Raw text values are preserved in invalid_bets.csv alongside normalized helper fields.",
            "Money checks use Decimal arithmetic with deterministic cent rounding and one-cent tolerance.",
        ],
    }
    return ValidationResult(valid_bets=valid, invalid_bets=invalid, report=report)


def validate_file(
    input_path: str | Path,
    output_dir: str | Path,
    generated_at: str | None = None,
    run_id: str | None = None,
) -> ValidationResult:
    """Run validation for a CSV file and materialise outputs."""
    raw = read_bets_csv(input_path)
    input_metadata = {"input_path": str(input_path), "input_sha256": file_sha256(input_path)}
    result = validate_bets(raw, generated_at=generated_at, run_id=run_id, input_metadata=input_metadata)
    out_dir = ensure_dir(output_dir)
    valid_path = write_csv(result.valid_bets, out_dir / "valid_bets.csv")
    invalid_path = write_csv(result.invalid_bets, out_dir / "invalid_bets.csv")
    report_path = out_dir / "validation_report.json"
    report = dict(result.report)
    report["output_paths"] = {
        "valid_bets": str(valid_path),
        "invalid_bets": str(invalid_path),
        "validation_report": str(report_path),
    }
    write_json(report, report_path)
    return ValidationResult(result.valid_bets, result.invalid_bets, report)
