from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


INTERVAL_LEVELS = [50, 80, 90, 95]
SUBMISSION_COLUMNS = [
    "validation",
    "uf_code",
    "date",
    "pred",
    "lower_50",
    "upper_50",
    "lower_80",
    "upper_80",
    "lower_90",
    "upper_90",
    "lower_95",
    "upper_95",
]


def add_residual_intervals(
    predictions: pd.DataFrame,
    train_actual: np.ndarray,
    train_pred: np.ndarray,
    pred_col: str = "pred",
) -> pd.DataFrame:
    out = predictions.copy()
    residual_scale = np.abs(np.asarray(train_actual) - np.asarray(train_pred))
    if residual_scale.size == 0:
        raise ValueError("Cannot build prediction intervals from an empty residual sample.")

    for level in INTERVAL_LEVELS:
        width = float(np.quantile(residual_scale, level / 100.0))
        out[f"lower_{level}"] = np.maximum(out[pred_col] - width, 0)
        out[f"upper_{level}"] = np.maximum(out[pred_col] + width, 0)

    return enforce_submission_constraints(out)


def enforce_submission_constraints(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["pred"] = np.maximum(out["pred"], 0)

    lower_cols = ["lower_95", "lower_90", "lower_80", "lower_50"]
    upper_cols = ["upper_50", "upper_80", "upper_90", "upper_95"]

    out[lower_cols] = np.maximum(out[lower_cols], 0)
    out[upper_cols] = np.maximum(out[upper_cols], 0)

    lower_values = np.minimum.accumulate(out[lower_cols[::-1]].to_numpy(), axis=1)[:, ::-1]
    upper_values = np.maximum.accumulate(out[upper_cols].to_numpy(), axis=1)
    out[lower_cols] = lower_values
    out[upper_cols] = upper_values

    for col in lower_cols:
        out[col] = np.minimum(out[col], out["pred"])
    for col in upper_cols:
        out[col] = np.maximum(out[col], out["pred"])

    return out


def validate_submission_frame(df: pd.DataFrame, group_cols: Iterable[str] = ("uf_code",)) -> None:
    missing = [col for col in SUBMISSION_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Submission is missing required columns: {missing}")

    if df["date"].isna().any():
        raise ValueError("Submission contains missing dates.")
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        raise ValueError("Submission date column must be datetime64 before writing.")
    if not df["date"].dt.weekday.eq(6).all():
        raise ValueError("All submission dates must be Sundays.")

    numeric_cols = [c for c in SUBMISSION_COLUMNS if c not in {"validation", "date", "uf_code"}]
    if (df[numeric_cols] < 0).any().any():
        raise ValueError("Submission contains negative predictions or intervals.")

    ordered = ["lower_95", "lower_90", "lower_80", "lower_50", "pred", "upper_50", "upper_80", "upper_90", "upper_95"]
    values = df[ordered].to_numpy()
    if not np.all(values[:, :-1] <= values[:, 1:] + 1e-9):
        raise ValueError("Submission intervals are not nested.")

    sort_cols = ["validation", *group_cols, "date"]
    for _, part in df.sort_values(sort_cols).groupby(["validation", *group_cols], dropna=False):
        dates = part["date"].sort_values()
        expected = pd.date_range(dates.iloc[0], dates.iloc[-1], freq="W-SUN")
        if len(dates) != len(expected) or not dates.reset_index(drop=True).equals(pd.Series(expected)):
            key = part[["validation", *group_cols]].iloc[0].to_dict()
            raise ValueError(f"Submission dates are not continuous weekly Sundays for {key}.")


def write_submission_files(df: pd.DataFrame, output_dir: str | Path) -> dict[str, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_df = df.copy()
    write_df["date"] = write_df["date"].dt.strftime("%Y-%m-%d")

    paths = {"combined": out_dir / "july1_validation_all.csv"}
    write_df.to_csv(paths["combined"], index=False)
    for validation, part in write_df.groupby("validation", sort=True):
        path = out_dir / f"july1_{validation}.csv"
        part.to_csv(path, index=False)
        paths[str(validation)] = path
    return paths
