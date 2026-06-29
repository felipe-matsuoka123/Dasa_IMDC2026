from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dengue_comp.config import load_config, save_config
from dengue_comp.data import add_exogenous_features, add_time_features, aggregate_cases, get_feature_columns, load_case_data
from dengue_comp.metrics import regression_metrics
from dengue_comp.modeling import build_model, clip_predictions
from dengue_comp.submission import SUBMISSION_COLUMNS, add_residual_intervals, validate_submission_frame, write_submission_files
from dengue_comp.tracking import git_commit_hash


VALIDATION_SPLITS = {
    "validation_1": ("train_1", "target_1"),
    "validation_2": ("train_2", "target_2"),
    "validation_3": ("train_3", "target_3"),
    "validation_4": ("train_4", "target_4"),
}

VALIDATION_PERIODS = {
    "target_4": 53,
}


def build_case_table(config: dict) -> pd.DataFrame:
    feature_config = copy.deepcopy(config)
    feature_config["data"]["mask_cols"] = [col for pair in VALIDATION_SPLITS.values() for col in pair]

    raw = load_case_data(feature_config)
    return aggregate_cases(raw, feature_config)


def build_training_features(case_table: pd.DataFrame, config: dict) -> pd.DataFrame:
    data = add_exogenous_features(case_table, config)
    return add_time_features(data, config)


def validation_dates(case_table: pd.DataFrame, target_mask_col: str, date_col: str) -> pd.DatetimeIndex:
    observed_target = case_table.loc[case_table[target_mask_col].astype(bool), date_col]
    if observed_target.empty:
        raise ValueError(f"No rows found for {target_mask_col}.")
    start = observed_target.min()
    periods = VALIDATION_PERIODS.get(target_mask_col, 52)
    return pd.date_range(start=start, periods=periods, freq="W-SUN")


def make_forecast_skeleton(
    case_table: pd.DataFrame,
    config: dict,
    train_col: str,
    target_mask_col: str,
) -> pd.DataFrame:
    data_cfg = config["data"]
    date_col = data_cfg.get("date_col", "date")
    target_col = data_cfg.get("target_col", "casos")
    group_cols = data_cfg.get("group_cols", ["uf_code"])
    dates = validation_dates(case_table, target_mask_col, date_col)

    history = case_table.loc[case_table[train_col].astype(bool)].copy()
    groups = history[group_cols].drop_duplicates().sort_values(group_cols).reset_index(drop=True)
    skeleton = groups.merge(pd.DataFrame({date_col: dates}), how="cross")
    skeleton[target_col] = np.nan
    skeleton["epiweek"] = skeleton[date_col].dt.isocalendar().year.astype(int) * 100 + skeleton[date_col].dt.isocalendar().week.astype(int)
    skeleton[train_col] = False
    skeleton[target_mask_col] = True

    if "uf" in history.columns and "uf" not in skeleton.columns:
        uf_lookup = history[group_cols + ["uf"]].drop_duplicates(group_cols)
        skeleton = skeleton.merge(uf_lookup, on=group_cols, how="left")

    keep_cols = list(dict.fromkeys([*group_cols, date_col, "epiweek", target_col, "uf", train_col, target_mask_col]))
    keep_cols = [col for col in keep_cols if col in history.columns or col in skeleton.columns]
    return pd.concat([history[keep_cols], skeleton[keep_cols]], ignore_index=True).sort_values([*group_cols, date_col])


def recursive_forecast(
    model,
    case_table: pd.DataFrame,
    config: dict,
    train_col: str,
    target_mask_col: str,
    feature_cols: list[str],
) -> pd.DataFrame:
    data_cfg = config["data"]
    date_col = data_cfg.get("date_col", "date")
    target_col = data_cfg.get("target_col", "casos")
    group_cols = data_cfg.get("group_cols", ["uf_code"])
    dates = validation_dates(case_table, target_mask_col, date_col)

    forecast_base = make_forecast_skeleton(case_table, config, train_col, target_mask_col)
    forecast_base = add_exogenous_features(forecast_base, config)

    predictions = []
    for date in dates:
        featured = add_time_features(forecast_base, config)
        step_mask = featured[date_col].eq(date)
        step_cols = list(dict.fromkeys([*group_cols, date_col, *feature_cols]))
        step = featured.loc[step_mask, step_cols].copy()
        step_pred = clip_predictions(model.predict(step[feature_cols]))
        step["pred"] = step_pred
        predictions.append(step[group_cols + [date_col, "pred"]])

        update_index = forecast_base[date_col].eq(date)
        forecast_base.loc[update_index, target_col] = step_pred

    return pd.concat(predictions, ignore_index=True)


def make_validation_submission(config_path: str | Path, output_dir: str | Path) -> Path:
    config = load_config(config_path)
    config["git_commit"] = git_commit_hash()
    config.setdefault("output", {})["submission_dir"] = str(output_dir)
    case_table = build_case_table(config)
    feature_table = build_training_features(case_table, config)

    target_col = config["data"].get("target_col", "casos")
    date_col = config["data"].get("date_col", "date")
    group_cols = config["data"].get("group_cols", ["uf_code"])
    feature_cols = get_feature_columns(feature_table, config)

    submissions = []
    metrics = {}
    for validation_name, (train_col, target_mask_col) in VALIDATION_SPLITS.items():
        split_config = copy.deepcopy(config)
        split_config["data"]["train_mask_cols"] = [train_col]
        split_config["data"]["valid_mask_cols"] = [target_mask_col]

        train = feature_table.loc[feature_table[train_col].astype(bool)].copy()
        observed_valid = feature_table.loc[feature_table[target_mask_col].astype(bool)].copy()
        if train.empty or observed_valid.empty:
            raise ValueError(f"Empty split for {validation_name}: train={len(train)}, observed_valid={len(observed_valid)}")
        if train[date_col].max() >= observed_valid[date_col].min():
            raise ValueError(f"{validation_name} is not time-aware: training overlaps target period.")

        model = build_model(split_config)
        model.fit(train[feature_cols], train[target_col])

        train_pred = clip_predictions(model.predict(train[feature_cols]))
        valid_pred = recursive_forecast(model, case_table, split_config, train_col, target_mask_col, feature_cols)

        observed_eval = observed_valid[group_cols + [date_col, target_col]].merge(valid_pred, on=[*group_cols, date_col], how="inner")
        split_metrics = regression_metrics(observed_eval[target_col], observed_eval["pred"])
        split_metrics["n_train"] = int(len(train))
        split_metrics["n_valid_observed"] = int(len(observed_eval))
        split_metrics["n_submission_rows"] = int(len(valid_pred))
        metrics[validation_name] = split_metrics

        pred = valid_pred[group_cols + [date_col, "pred"]].copy()
        pred["validation"] = validation_name
        pred = add_residual_intervals(pred, train[target_col].to_numpy(), train_pred)
        submissions.append(pred)

    submission = pd.concat(submissions, ignore_index=True)
    output_cols = [col for col in SUBMISSION_COLUMNS if col in submission.columns]
    submission = submission[output_cols].sort_values(["validation", *group_cols, date_col]).reset_index(drop=True)
    validate_submission_frame(submission, group_cols=group_cols)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = write_submission_files(submission, out_dir)
    save_config(config, out_dir / "july1_submission_config.yaml")
    with (out_dir / "july1_validation_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"July 1 validation submission written to: {paths['combined']}")
    for key, path in paths.items():
        if key != "combined":
            print(f"{key}: {path}")
    return paths["combined"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the July 1 validation submission package.")
    parser.add_argument("config", help="Path to the experiment config to use for modeling.")
    parser.add_argument("--output-dir", default="outputs/submissions/july1", help="Directory for submission CSVs and metadata.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    make_validation_submission(args.config, args.output_dir)
