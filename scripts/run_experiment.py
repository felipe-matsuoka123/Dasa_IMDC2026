from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import wandb

from dengue_comp.config import load_config
from dengue_comp.data import (
    add_time_features,
    add_exogenous_features,
    aggregate_cases,
    get_feature_columns,
    load_case_data,
    split_data,
)
from dengue_comp.metrics import regression_metrics
from dengue_comp.modeling import build_model, clip_predictions
from dengue_comp.tracking import git_commit_hash, init_wandb, prepare_run_dir, save_run_artifacts


def run(config_path: str | Path) -> Path:
    config = load_config(config_path)
    config["git_commit"] = git_commit_hash()
    run_dir = prepare_run_dir(config)

    raw = load_case_data(config)
    data = aggregate_cases(raw, config)
    data = add_exogenous_features(data, config)
    data = add_time_features(data, config)
    train, valid = split_data(data, config)

    target_col = config["data"].get("target_col", "casos")
    date_col = config["data"].get("date_col", "date")
    group_cols = config["data"].get("group_cols", ["uf_code"])
    feature_cols = get_feature_columns(data, config)

    model = build_model(config)
    model.fit(train[feature_cols], train[target_col])
    valid_pred = clip_predictions(model.predict(valid[feature_cols]))
    metrics = regression_metrics(valid[target_col], valid_pred)
    metrics["n_train"] = int(len(train))
    metrics["n_valid"] = int(len(valid))
    metrics["git_commit_known"] = config["git_commit"] != "unknown-not-a-git-repo"

    predictions = valid[group_cols + [date_col, "epiweek", target_col]].copy()
    predictions["pred"] = valid_pred
    predictions["error"] = predictions["pred"] - predictions[target_col]

    run = init_wandb(config, run_dir)
    try:
        wandb.log(metrics)
        wandb.log({"validation_predictions": wandb.Table(dataframe=predictions)})
        paths = save_run_artifacts(run_dir, config, metrics, predictions, model)
        artifact = wandb.Artifact(f"{config['experiment']['name']}-outputs", type="experiment-output")
        for path in paths.values():
            artifact.add_file(path)
        run.log_artifact(artifact)
    finally:
        run.finish()

    print(f"Run directory: {run_dir}")
    print(pd.Series(metrics).to_string())
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a config-driven dengue forecasting experiment.")
    parser.add_argument("config", help="Path to the YAML experiment config.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.config)
