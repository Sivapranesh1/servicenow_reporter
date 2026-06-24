"""Locate and parse the latest ServiceNow incident export."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("servicenow_reporter")


class ExcelProcessingError(Exception):
    """Raised for any unrecoverable error while reading Excel."""


def find_latest_excel(folder: str | Path) -> Path:
    """Return the most recently modified .xlsx/.xls file in `folder`."""
    folder_path = Path(folder)
    if not folder_path.exists():
        raise ExcelProcessingError(f"Input folder does not exist: {folder_path}")

    candidates = [
        p for p in folder_path.iterdir()
        if p.is_file() and p.suffix.lower() in {".xlsx", ".xls"}
        and not p.name.startswith("~$")  # ignore Excel lock files
    ]
    if not candidates:
        raise ExcelProcessingError(f"No Excel files found in {folder_path}")

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    logger.info("Latest Excel selected: %s", latest.name)
    return latest


def _resolve_column_map(
    df_columns: list[str], required: dict[str, list[str]]
) -> dict[str, str | None]:
    """Map our logical names → actual columns in the dataframe (case-insensitive)."""
    lower_map = {c.lower().strip(): c for c in df_columns}
    resolved: dict[str, str | None] = {}
    for logical, variants in required.items():
        match = next(
            (lower_map[v.lower()] for v in variants if v.lower() in lower_map), None
        )
        resolved[logical] = match
    return resolved


def read_incident_file(
    file_path: str | Path, required_columns: dict[str, list[str]]
) -> tuple[pd.DataFrame, dict[str, str | None]]:
    """Read Excel into a normalized DataFrame and return the column map."""
    file_path = Path(file_path)
    try:
        engine = "openpyxl" if file_path.suffix.lower() == ".xlsx" else None
        df = pd.read_excel(file_path, engine=engine)
    except Exception as exc:  # noqa: BLE001
        raise ExcelProcessingError(f"Failed to read {file_path}: {exc}") from exc

    if df.empty:
        raise ExcelProcessingError("Excel file is empty.")

    col_map = _resolve_column_map(list(df.columns), required_columns)

    missing_critical = [k for k in ("incident_number", "state") if col_map.get(k) is None]
    if missing_critical:
        raise ExcelProcessingError(
            f"Missing critical columns: {missing_critical}. "
            f"Found columns: {list(df.columns)}"
        )

    logger.info("Resolved columns: %s", col_map)
    logger.info("Loaded %d incident rows.", len(df))
    return df, col_map


def normalize_dataframe(
    df: pd.DataFrame, col_map: dict[str, str | None]
) -> pd.DataFrame:
    """Return a dataframe with consistent canonical column names."""
    rename = {v: k for k, v in col_map.items() if v is not None}
    normalized = df.rename(columns=rename).copy()

    # Ensure every logical column exists
    for logical in col_map:
        if logical not in normalized.columns:
            normalized[logical] = pd.NA

    # Parse datetime columns
    for dt_col in ("last_updated", "opened_date"):
        if dt_col in normalized.columns:
            normalized[dt_col] = pd.to_datetime(
                normalized[dt_col], errors="coerce", dayfirst=False
            )

    # Strip strings
    str_cols = [
        "incident_number", "short_description", "assignment_group",
        "assigned_to", "state", "hold_reason", "dependency",
        "priority", "business_service",
    ]
    for c in str_cols:
        if c in normalized.columns:
            normalized[c] = normalized[c].astype(str).str.strip().replace(
                {"nan": pd.NA, "NaT": pd.NA, "None": pd.NA, "": pd.NA}
            )

    return normalized
