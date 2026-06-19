"""File helpers for the local batch jobs."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd


def ensure_dir(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def read_bets_csv(input_path: str | Path) -> pd.DataFrame:
    """Read raw bets as strings so validation owns all type coercion."""
    return pd.read_csv(input_path, dtype=str, keep_default_na=False)


def write_csv(df: pd.DataFrame, output_path: str | Path) -> Path:
    path = Path(output_path)
    ensure_dir(path.parent)
    df.to_csv(path, index=False, encoding="utf-8")
    return path


def write_json(payload: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, default=str)
        f.write("\n")
    return path


def file_sha256(input_path: str | Path) -> str:
    """Return a stable checksum for audit reports and rerun comparisons."""
    digest = sha256()
    with Path(input_path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_table_with_parquet_fallback(df: pd.DataFrame, output_dir: str | Path, stem: str) -> dict[str, str]:
    """Write CSV every time; add Parquet when the local environment supports it."""
    out_dir = ensure_dir(output_dir)
    csv_path = out_dir / f"{stem}.csv"
    write_csv(df, csv_path)

    result = {"csv": str(csv_path)}
    parquet_path = out_dir / f"{stem}.parquet"
    try:
        df.to_parquet(parquet_path, index=False)
        result["parquet"] = str(parquet_path)
    except Exception as exc:  # pragma: no cover - depends on optional engine availability
        result["parquet_unavailable_reason"] = f"{type(exc).__name__}: {exc}"
    return result
