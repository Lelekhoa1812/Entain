"""Build customer-level features from each customer's early betting history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from bet_pipeline.contracts import FEATURE_OUTPUT_COLUMNS, FEATURE_SET_NAME, FEATURE_SET_VERSION, SCHEMA_CONTRACT_VERSION
from bet_pipeline.constants import DEFAULT_FIRST_N_BETS
from bet_pipeline.io import ensure_dir, file_sha256, read_bets_csv, write_json, write_table_with_parquet_fallback
from bet_pipeline.validate import validate_bets

FEATURE_COLUMNS = FEATURE_OUTPUT_COLUMNS

FULL_QUALITY_FLAG = "FULL_20_VALID_BETS"
REVIEW_QUALITY_FLAG = "PARTIAL_OR_REVIEW_FIRST20_WINDOW"
WINDOW_POLICY_TEMPLATE = "valid rows where 1 <= bet_num <= {first_n_bets}; no replacement from later bets"
REPORT_WINDOW_POLICY = "valid records with bet_num <= first_n_bets; invalid early rows are not replaced by later bets"


@dataclass(frozen=True)
class FeatureBuildResult:
    customer_features: pd.DataFrame
    report: dict


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _empty_feature_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=FEATURE_COLUMNS)


def _empty_report(
    generated_at: str,
    first_n_bets: int,
    validation_report: dict,
    customers_without_features: int,
    run_id: str | None = None,
    input_metadata: dict | None = None,
) -> dict:
    return {
        "generated_at": generated_at,
        "run_id": run_id,
        "schema_contract_version": SCHEMA_CONTRACT_VERSION,
        "feature_set_name": FEATURE_SET_NAME,
        "feature_set_version": FEATURE_SET_VERSION,
        "input_metadata": input_metadata or {},
        "customer_count": 0,
        "first_n_bets": first_n_bets,
        "full_quality_customer_count": 0,
        "partial_or_review_customer_count": 0,
        "customers_without_valid_first_window_count": customers_without_features,
        "feature_window_policy": REPORT_WINDOW_POLICY,
        "output_columns": FEATURE_COLUMNS,
        "validation_summary": validation_report,
    }


def build_customer_features(
    raw: pd.DataFrame,
    first_n_bets: int = DEFAULT_FIRST_N_BETS,
    generated_at: str | None = None,
    run_id: str | None = None,
    input_metadata: dict | None = None,
) -> FeatureBuildResult:
    """Build customer-level features from the valid records in the first-N window."""
    if first_n_bets <= 0:
        raise ValueError("first_n_bets must be a positive integer")

    generated_at = generated_at or _utc_now_iso()
    validation = validate_bets(raw, generated_at=generated_at, run_id=run_id, input_metadata=input_metadata)
    valid = validation.valid_bets.copy()
    invalid = validation.invalid_bets.copy()

    total_customers_seen = int(raw["customer_id"].nunique()) if "customer_id" in raw.columns else 0
    if valid.empty:
        report = _empty_report(generated_at, first_n_bets, validation.report, total_customers_seen, run_id, input_metadata)
        return FeatureBuildResult(_empty_feature_frame(), report)

    valid["bet_datetime_ts"] = pd.to_datetime(valid["bet_datetime"], errors="coerce", utc=True)
    for col in ["bet_num", "betting_amount", "price", "payout", "return_for_entain"]:
        valid[col] = pd.to_numeric(valid[col], errors="coerce")

    first_window = valid[valid["bet_num"].between(1, first_n_bets, inclusive="both")].copy()
    first_window = first_window.sort_values(["customer_id", "bet_num", "bet_datetime_ts", "bet_id"])

    if first_window.empty:
        report = _empty_report(generated_at, first_n_bets, validation.report, total_customers_seen, run_id, input_metadata)
        return FeatureBuildResult(_empty_feature_frame(), report)

    # Invalid rows inside the first window still matter: they tell us the
    # customer's feature row is review-quality, not a clean full-20 sample.
    invalid_first_counts: dict[str, int] = {}
    if not invalid.empty:
        invalid_copy = invalid.copy()
        invalid_copy["bet_num_numeric"] = pd.to_numeric(invalid_copy["bet_num"], errors="coerce")
        early_invalid = invalid_copy[invalid_copy["bet_num_numeric"].between(1, first_n_bets, inclusive="both")]
        invalid_first_counts = early_invalid.groupby("canonical_customer_id").size().to_dict()

    rows: list[dict] = []
    for customer_id, group in first_window.groupby("customer_id", sort=True):
        group = group.sort_values(["bet_num", "bet_datetime_ts", "bet_id"])
        bets_used = int(len(group))
        bet20 = group[group["bet_num"] == first_n_bets]
        invalid_first20_count = int(invalid_first_counts.get(customer_id, 0))
        has_clean_full_window = bets_used == first_n_bets and invalid_first20_count == 0
        quality_flag = FULL_QUALITY_FLAG if has_clean_full_window else REVIEW_QUALITY_FLAG

        rows.append(
            {
                "customer_id": customer_id,
                "first_bet_datetime": group.iloc[0]["bet_datetime"],
                "twentieth_bet_datetime": bet20.iloc[0]["bet_datetime"] if not bet20.empty else pd.NA,
                "bets_used": bets_used,
                "total_betting_amount": round(float(group["betting_amount"].sum()), 2),
                "mean_betting_amount": round(float(group["betting_amount"].mean()), 4),
                "mean_price": round(float(group["price"].mean()), 4),
                "pct_racing": round(float((group["category"] == "racing").mean()), 6),
                "pct_cash": round(float((group["stake_type"] == "cash").mean()), 6),
                "pct_return": round(float((group["bet_result"] == "return").mean()), 6),
                "total_payout": round(float(group["payout"].sum()), 2),
                "total_return_for_entain": round(float(group["return_for_entain"].sum()), 2),
                "feature_generated_at": generated_at,
                "feature_window_policy": WINDOW_POLICY_TEMPLATE.format(first_n_bets=first_n_bets),
                "invalid_first20_count": invalid_first20_count,
                "feature_quality_flag": quality_flag,
            }
        )

    features = pd.DataFrame(rows, columns=FEATURE_COLUMNS).sort_values("customer_id").reset_index(drop=True)
    report = {
        "generated_at": generated_at,
        "run_id": run_id,
        "schema_contract_version": SCHEMA_CONTRACT_VERSION,
        "feature_set_name": FEATURE_SET_NAME,
        "feature_set_version": FEATURE_SET_VERSION,
        "input_metadata": input_metadata or {},
        "customer_count": int(len(features)),
        "first_n_bets": first_n_bets,
        "full_quality_customer_count": int((features["feature_quality_flag"] == FULL_QUALITY_FLAG).sum()),
        "partial_or_review_customer_count": int((features["feature_quality_flag"] != FULL_QUALITY_FLAG).sum()),
        "customers_without_valid_first_window_count": max(total_customers_seen - int(len(features)), 0),
        "feature_window_policy": REPORT_WINDOW_POLICY,
        "output_columns": FEATURE_COLUMNS,
        "validation_summary": validation.report,
        "notes": [
            "The feature job validates the raw file itself, so it does not depend on running the validation CLI first.",
            "A later bet_num is never pulled into the first-N window to patch over an invalid earlier row.",
            "Customers with incomplete or invalid first-N windows stay visible through bets_used and feature_quality_flag.",
        ],
    }
    return FeatureBuildResult(features, report)


def build_features_file(
    input_path: str | Path,
    output_dir: str | Path,
    first_n_bets: int = DEFAULT_FIRST_N_BETS,
    generated_at: str | None = None,
    run_id: str | None = None,
) -> FeatureBuildResult:
    """Run the customer feature build for a CSV file and materialise outputs."""
    raw = read_bets_csv(input_path)
    input_metadata = {"input_path": str(input_path), "input_sha256": file_sha256(input_path)}
    result = build_customer_features(
        raw,
        first_n_bets=first_n_bets,
        generated_at=generated_at,
        run_id=run_id,
        input_metadata=input_metadata,
    )
    out_dir = ensure_dir(output_dir)
    table_outputs = write_table_with_parquet_fallback(result.customer_features, out_dir, "customer_features")
    report = dict(result.report)
    report["table_outputs"] = table_outputs
    report_path = out_dir / "feature_build_report.json"
    report["output_paths"] = {"feature_build_report": str(report_path), **table_outputs}
    write_json(report, report_path)
    return FeatureBuildResult(result.customer_features, report)
