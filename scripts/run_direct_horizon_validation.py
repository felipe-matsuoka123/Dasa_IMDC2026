from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from dengue_comp.config import load_config, save_config
from dengue_comp.data import add_exogenous_features, add_time_features, aggregate_cases, get_feature_columns, load_case_data
from dengue_comp.metrics import regression_metrics
from dengue_comp.modeling import build_model, clip_predictions
from dengue_comp.submission import add_residual_intervals, validate_submission_frame, write_submission_files
from dengue_comp.tracking import git_commit_hash


def build_case_table(config: dict[str, Any]) -> pd.DataFrame:
    direct_cfg = config["direct_horizon"]
    split_cols = []
    for split in direct_cfg["validation_splits"].values():
        split_cols.extend([split["train_col"], split["target_col"]])
    case_config = copy.deepcopy(config)
    case_config["data"]["mask_cols"] = split_cols
    raw = load_case_data(case_config)
    return aggregate_cases(raw, case_config)


def build_weekly_features(case_table: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    data = add_exogenous_features(case_table, config)
    return add_time_features(data, config)


def target_dates_for_year(case_table: pd.DataFrame, config: dict[str, Any], origin_year: int) -> pd.Series:
    direct_cfg = config["direct_horizon"]
    date_col = config["data"].get("date_col", "date")
    epiweek_start = origin_year * 100 + int(direct_cfg.get("target_start_week", 41))
    epiweek_end = (origin_year + 1) * 100 + int(direct_cfg.get("target_end_week", 40))
    dates = (
        case_table.loc[case_table["epiweek"].between(epiweek_start, epiweek_end), date_col]
        .drop_duplicates()
        .sort_values()
        .head(int(direct_cfg.get("target_length", 52)))
    )
    return dates


def validation_target_dates(case_table: pd.DataFrame, config: dict[str, Any], target_mask_col: str) -> pd.Series:
    date_col = config["data"].get("date_col", "date")
    direct_cfg = config["direct_horizon"]
    dates = (
        case_table.loc[case_table[target_mask_col].astype(bool), date_col]
        .drop_duplicates()
        .sort_values()
    )
    if dates.empty:
        raise ValueError(f"No target dates found for {target_mask_col}.")
    target_length = int(direct_cfg.get("target_length", 52))
    if len(dates) < target_length:
        start = dates.min()
        return pd.Series(pd.date_range(start=start, periods=target_length, freq="W-SUN"))
    return dates.head(target_length)


def add_horizon_metadata(frame: pd.DataFrame, origin_date: pd.Timestamp, target_dates: pd.Series, config: dict[str, Any]) -> pd.DataFrame:
    date_col = config["data"].get("date_col", "date")
    target_dates = pd.Series(pd.to_datetime(target_dates)).reset_index(drop=True)
    meta = pd.DataFrame({date_col: target_dates})
    iso = meta[date_col].dt.isocalendar()
    meta["target_year"] = iso.year.astype(int)
    meta["target_weekofyear"] = iso.week.astype(int)
    meta["target_month"] = meta[date_col].dt.month.astype(int)
    meta["target_week_sin"] = np.sin(2 * np.pi * meta["target_weekofyear"] / 53.0)
    meta["target_week_cos"] = np.cos(2 * np.pi * meta["target_weekofyear"] / 53.0)
    meta["season_week_index"] = np.arange(1, len(meta) + 1)
    meta["weeks_ahead"] = ((meta[date_col] - origin_date).dt.days // 7).astype(int)
    return frame.merge(meta, on=date_col, how="left")


def build_direct_rows_for_origin(
    feature_table: pd.DataFrame,
    case_table: pd.DataFrame,
    config: dict[str, Any],
    origin_year: int,
    cutoff_date: pd.Timestamp,
    require_complete_target: bool = False,
) -> pd.DataFrame:
    data_cfg = config["data"]
    direct_cfg = config["direct_horizon"]
    date_col = data_cfg.get("date_col", "date")
    target_col = data_cfg.get("target_col", "casos")
    group_cols = data_cfg.get("group_cols", ["uf_code"])
    origin_week = int(direct_cfg.get("origin_week", 25))
    origin_epiweek = origin_year * 100 + origin_week

    origin = feature_table.loc[feature_table["epiweek"].eq(origin_epiweek)].copy()
    if origin.empty:
        return pd.DataFrame()
    target_dates = target_dates_for_year(case_table, config, origin_year)
    if require_complete_target and len(target_dates) < int(direct_cfg.get("target_length", 52)):
        return pd.DataFrame()
    target_dates = target_dates[target_dates.le(cutoff_date)]
    if target_dates.empty:
        return pd.DataFrame()

    targets = case_table.loc[case_table[date_col].isin(target_dates), [*group_cols, date_col, target_col]].copy()
    origin_features = origin.drop(columns=[date_col, "epiweek", target_col], errors="ignore")
    rows = origin_features.merge(targets, on=group_cols, how="inner")
    rows["origin_year"] = origin_year
    rows["origin_date"] = origin[date_col].iloc[0]
    rows = add_horizon_metadata(rows, pd.Timestamp(rows["origin_date"].iloc[0]), target_dates, config)
    return rows


def build_direct_training_table(
    feature_table: pd.DataFrame,
    case_table: pd.DataFrame,
    config: dict[str, Any],
    cutoff_date: pd.Timestamp,
) -> pd.DataFrame:
    min_year = int(config["direct_horizon"].get("min_origin_year", 2010))
    max_year = int(cutoff_date.year)
    rows = [
        build_direct_rows_for_origin(feature_table, case_table, config, origin_year, cutoff_date, require_complete_target=False)
        for origin_year in range(min_year, max_year + 1)
    ]
    rows = [row for row in rows if not row.empty]
    if not rows:
        raise ValueError(f"No direct-horizon training rows available before cutoff {cutoff_date.date()}.")
    out = pd.concat(rows, ignore_index=True)
    return out.loc[out[config["data"].get("date_col", "date")].le(cutoff_date)].copy()


def build_prediction_table(
    feature_table: pd.DataFrame,
    case_table: pd.DataFrame,
    config: dict[str, Any],
    train_col: str,
    target_mask_col: str,
) -> pd.DataFrame:
    data_cfg = config["data"]
    date_col = data_cfg.get("date_col", "date")
    target_col = data_cfg.get("target_col", "casos")
    group_cols = data_cfg.get("group_cols", ["uf_code"])

    cutoff_date = case_table.loc[case_table[train_col].astype(bool), date_col].max()
    origin = feature_table.loc[feature_table[date_col].eq(cutoff_date)].copy()
    if origin.empty:
        raise ValueError(f"No feature rows found at cutoff date {cutoff_date.date()} for {train_col}.")

    target_dates = validation_target_dates(case_table, config, target_mask_col)
    target_grid = origin[group_cols].drop_duplicates().merge(pd.DataFrame({date_col: target_dates}), how="cross")
    origin_features = origin.drop(columns=[date_col, "epiweek", target_col], errors="ignore")
    rows = origin_features.merge(target_grid, on=group_cols, how="inner")
    rows["origin_year"] = int(cutoff_date.year)
    rows["origin_date"] = cutoff_date
    rows = add_horizon_metadata(rows, pd.Timestamp(cutoff_date), target_dates, config)
    return rows


def direct_feature_columns(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    date_col = config["data"].get("date_col", "date")
    target_col = config["data"].get("target_col", "casos")
    excluded = {
        date_col,
        target_col,
        "origin_date",
        "uf",
        "validation",
    }
    cols = []
    for col in frame.columns:
        if col in excluded:
            continue
        if re.fullmatch(r"(train|target)_\d+", col):
            continue
        if pd.api.types.is_numeric_dtype(frame[col]):
            cols.append(col)
    return cols


def run_direct_horizon(config_path: str | Path, output_dir: str | Path | None = None) -> Path:
    config = load_config(config_path)
    config["git_commit"] = git_commit_hash()
    if output_dir is None:
        output_dir = config.get("output", {}).get("direct_horizon_dir", "outputs/direct_horizon")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    case_table = build_case_table(config)
    feature_table = build_weekly_features(case_table, config)
    date_col = config["data"].get("date_col", "date")
    target_col = config["data"].get("target_col", "casos")
    group_cols = config["data"].get("group_cols", ["uf_code"])

    all_predictions = []
    metrics = {}
    for validation_name, split in config["direct_horizon"]["validation_splits"].items():
        train_col = split["train_col"]
        target_mask_col = split["target_col"]
        cutoff_date = case_table.loc[case_table[train_col].astype(bool), date_col].max()
        train = build_direct_training_table(feature_table, case_table, config, cutoff_date)
        pred_frame = build_prediction_table(feature_table, case_table, config, train_col, target_mask_col)
        feature_cols = direct_feature_columns(train, config)

        model = build_model(config)
        model.fit(train[feature_cols].fillna(0), train[target_col])
        train_pred = clip_predictions(model.predict(train[feature_cols].fillna(0)))
        pred = pred_frame[group_cols + [date_col]].copy()
        pred["pred"] = clip_predictions(model.predict(pred_frame[feature_cols].fillna(0)))
        pred["validation"] = validation_name
        pred = add_residual_intervals(pred, train[target_col].to_numpy(), train_pred)

        observed = case_table.loc[case_table[target_mask_col].astype(bool), [*group_cols, date_col, target_col]]
        eval_frame = observed.merge(pred[group_cols + [date_col, "pred"]], on=[*group_cols, date_col], how="inner")
        split_metrics = regression_metrics(eval_frame[target_col], eval_frame["pred"])
        split_metrics["n_direct_train_rows"] = int(len(train))
        split_metrics["n_observed_eval_rows"] = int(len(eval_frame))
        split_metrics["n_submission_rows"] = int(len(pred))
        split_metrics["cutoff_date"] = str(pd.Timestamp(cutoff_date).date())
        metrics[validation_name] = split_metrics

        model_path = out_dir / f"{validation_name}_direct_horizon_model.joblib"
        joblib.dump(model, model_path)
        all_predictions.append(pred)

    submission = pd.concat(all_predictions, ignore_index=True).sort_values(["validation", *group_cols, date_col])
    validate_submission_frame(submission, group_cols=group_cols)
    paths = write_submission_files(submission, out_dir)
    save_config(config, out_dir / "direct_horizon_config.yaml")
    with (out_dir / "direct_horizon_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Direct-horizon validation predictions written to: {paths['combined']}")
    print(pd.DataFrame(metrics).T.to_string())
    return paths["combined"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the direct-horizon validation strategy.")
    parser.add_argument("config", help="Path to a direct-horizon YAML config.")
    parser.add_argument("--output-dir", default=None, help="Override output directory.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_direct_horizon(args.config, args.output_dir)
