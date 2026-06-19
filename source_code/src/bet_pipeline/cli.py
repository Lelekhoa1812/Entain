"""CLI entry point for the betting-data pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bet_pipeline.build_features import build_features_file
from bet_pipeline.validate import SchemaError, validate_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bet-pipeline",
        description="Validate raw betting data and build first-window customer features.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate raw bets and write the clean, quarantine, and report files.",
    )
    validate_parser.add_argument("--input", required=True, type=Path, help="Path to raw bets.csv")
    validate_parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Directory for validation outputs",
    )
    validate_parser.add_argument("--generated-at", help="UTC timestamp to write into the validation report")
    validate_parser.add_argument("--run-id", help="Optional run identifier for audit and rerun tracking")

    features_parser = subparsers.add_parser(
        "build-features",
        help="Build customer-level features from the first 20 bets.",
    )
    features_parser.add_argument("--input", required=True, type=Path, help="Path to raw bets.csv")
    features_parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Directory for feature outputs",
    )
    features_parser.add_argument(
        "--first-n-bets",
        type=int,
        default=20,
        help="Authoritative bet_num window size; default 20",
    )
    features_parser.add_argument("--generated-at", help="UTC timestamp to write into the feature report and rows")
    features_parser.add_argument("--run-id", help="Optional run identifier for audit and rerun tracking")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "validate":
            result = validate_file(args.input, args.output, generated_at=args.generated_at, run_id=args.run_id)
            print(
                f"Validation complete: {result.report['valid_rows']} valid rows, "
                f"{result.report['invalid_rows']} invalid rows. Outputs: {args.output}"
            )
            return 0

        if args.command == "build-features":
            result = build_features_file(
                args.input,
                args.output,
                first_n_bets=args.first_n_bets,
                generated_at=args.generated_at,
                run_id=args.run_id,
            )
            print(
                f"Feature build complete: {result.report['customer_count']} customer rows. "
                f"Outputs: {args.output}"
            )
            return 0

        parser.error(f"Unsupported command: {args.command}")
        return 2
    except FileNotFoundError as exc:
        print(f"Input file not found: {exc}", file=sys.stderr)
        return 1
    except SchemaError as exc:
        print(f"Schema error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Pipeline failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
