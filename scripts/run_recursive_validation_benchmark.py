from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

import joblib
import pandas as pd
import wandb

os.environ.setdefault("MPLCONFIGDIR", str(Path("outputs/plots/.matplotlib").resolve()))
import matplotlib.pyplot as plt

from dengue_comp.config import load_config, save_config
from dengue_comp.data import get_feature_columns
from dengue_comp.metrics import regression_metrics
from dengue_comp.modeling import build_model, clip_predictions
from dengue_comp.submission import SUBMISSION_COLUMNS, add_residual_intervals, validate_submission_frame, write_submission_files
from dengue_comp.tracking import git_commit_hash, init_wandb
try:
    from scripts.make_july1_validation_submission import (
        VALIDATION_SPLITS,
        build_case_table,
        build_training_features,
        recursive_forecast,
    )
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from make_july1_validation_submission import (
        VALIDATION_SPLITS,
        build_case_table,
        build_training_features,
        recursive_forecast,
    )


def default_output_dir(config: dict) -> Path:
    experiment_name = config.get("experiment", {}).get("name", "experiment")
    return Path(config.get("output", {}).get("recursive_validation_dir", "outputs/recursive_validation")) / experiment_name


def plot_prediction_grid(predictions: pd.DataFrame, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(15, 8), sharey=False)
    axes = axes.ravel()
    grouped_predictions = list(predictions.groupby("validation", sort=True))
    for ax, (validation, part) in zip(axes, grouped_predictions):
        weekly = part.groupby("date", as_index=False).agg(actual=("actual", "sum"), pred=("pred", "sum"))
        ax.plot(weekly["date"], weekly["actual"], label="Actual", color="#222222", linewidth=2)
        ax.plot(weekly["date"], weekly["pred"], label="Predicted", color="#d64b4b", linewidth=2)
        ax.set_title(validation)
        ax.set_xlabel("")
        ax.set_ylabel("Total weekly dengue cases")
        ax.tick_params(axis="x", labelrotation=35)
        ax.grid(True, alpha=0.25)
    for ax in axes[len(grouped_predictions) :]:
        ax.axis("off")
    axes[0].legend(loc="upper left", frameon=False)
    fig.suptitle("Recursive per-split validation: predicted vs actual total cases", y=1.02)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def run_recursive_validation_benchmark(config_path: str | Path, output_dir: str | Path | None = None) -> Path:
    config = load_config(config_path)
    config["git_commit"] = git_commit_hash()
    out_dir = Path(output_dir) if output_dir else default_output_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)

    case_table = build_case_table(config)
    feature_table = build_training_features(case_table, config)

    target_col = config["data"].get("target_col", "casos")
    date_col = config["data"].get("date_col", "date")
    group_cols = config["data"].get("group_cols", ["uf_code"])
    feature_cols = get_feature_columns(feature_table, config)

    submissions = []
    observed_predictions = []
    split_metrics = []

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
        forecast = recursive_forecast(model, case_table, split_config, train_col, target_mask_col, feature_cols)

        observed_eval = (
            observed_valid[group_cols + [date_col, target_col]]
            .merge(forecast, on=[*group_cols, date_col], how="inner")
            .rename(columns={target_col: "actual"})
        )
        metrics = regression_metrics(observed_eval["actual"], observed_eval["pred"])
        metrics.update(
            {
                "experiment": config["experiment"]["name"],
                "strategy": "recursive_per_split",
                "validation": validation_name,
                "n_train": int(len(train)),
                "n_observed_eval": int(len(observed_eval)),
                "n_submission_rows": int(len(forecast)),
                "train_end": str(train[date_col].max().date()),
                "target_start": str(observed_valid[date_col].min().date()),
            }
        )
        split_metrics.append(metrics)

        observed_eval["validation"] = validation_name
        observed_predictions.append(observed_eval)

        submission = forecast[group_cols + [date_col, "pred"]].copy()
        submission["validation"] = validation_name
        submission = add_residual_intervals(submission, train[target_col].to_numpy(), train_pred)
        submissions.append(submission)

        joblib.dump(model, out_dir / f"{validation_name}_model.joblib")

    observed_predictions_df = pd.concat(observed_predictions, ignore_index=True)
    submission_df = pd.concat(submissions, ignore_index=True)
    output_cols = [col for col in SUBMISSION_COLUMNS if col in submission_df.columns]
    submission_df = submission_df[output_cols].sort_values(["validation", *group_cols, date_col]).reset_index(drop=True)
    validate_submission_frame(submission_df, group_cols=group_cols)

    split_metrics_df = pd.DataFrame(split_metrics)
    global_metrics = regression_metrics(observed_predictions_df["actual"], observed_predictions_df["pred"])
    global_metrics.update(
        {
            "experiment": config["experiment"]["name"],
            "strategy": "recursive_per_split",
            "validation": "all_observed",
            "n_observed_eval": int(len(observed_predictions_df)),
            "mean_split_mae": float(split_metrics_df["mae"].mean()),
            "mean_split_rmse": float(split_metrics_df["rmse"].mean()),
            "mean_split_smape": float(split_metrics_df["smape"].mean()),
            "worst_split_mae": float(split_metrics_df["mae"].max()),
            "worst_split_smape": float(split_metrics_df["smape"].max()),
        }
    )
    metrics_df = pd.concat([split_metrics_df, pd.DataFrame([global_metrics])], ignore_index=True)

    paths = write_submission_files(submission_df, out_dir)
    observed_predictions_df.to_csv(out_dir / "observed_predictions.csv", index=False)
    metrics_df.to_csv(out_dir / "metrics.csv", index=False)
    global_metrics_path = out_dir / "global_metrics.json"
    with global_metrics_path.open("w", encoding="utf-8") as f:
        json.dump(global_metrics, f, indent=2, sort_keys=True)
        f.write("\n")
    save_config(config, out_dir / "config.yaml")
    plot_path = plot_prediction_grid(observed_predictions_df, out_dir / "prediction_grid.png")

    run = init_wandb(config, out_dir)
    try:
        essential_split_cols = [
            "validation",
            "mae",
            "rmse",
            "smape",
            "n_train",
            "n_observed_eval",
            "n_submission_rows",
            "train_end",
            "target_start",
        ]
        split_metrics_table = split_metrics_df[[col for col in essential_split_cols if col in split_metrics_df.columns]]

        wandb_payload = {
            f"global/{key}": value
            for key, value in global_metrics.items()
            if isinstance(value, (int, float))
        }
        for row in split_metrics_df.to_dict(orient="records"):
            validation = row["validation"]
            for key in ["mae", "rmse", "smape", "n_train", "n_observed_eval", "n_submission_rows"]:
                if key in row and isinstance(row[key], (int, float)):
                    wandb_payload[f"split/{validation}/{key}"] = row[key]

        best_mae = split_metrics_df.loc[split_metrics_df["mae"].idxmin()]
        worst_mae = split_metrics_df.loc[split_metrics_df["mae"].idxmax()]
        worst_smape = split_metrics_df.loc[split_metrics_df["smape"].idxmax()]
        run.summary["best_split_by_mae"] = str(best_mae["validation"])
        run.summary["worst_split_by_mae"] = str(worst_mae["validation"])
        run.summary["worst_split_by_smape"] = str(worst_smape["validation"])

        wandb.log(wandb_payload)
        wandb.log({"split_metrics": wandb.Table(dataframe=split_metrics_table)})
        wandb.log({"prediction_grid": wandb.Image(str(plot_path))})

        artifact = wandb.Artifact(f"{config['experiment']['name']}-recursive-validation", type="validation-benchmark")
        for path in [
            out_dir / "config.yaml",
            out_dir / "metrics.csv",
            global_metrics_path,
            plot_path,
        ]:
            artifact.add_file(str(path))
        run.log_artifact(artifact)
    finally:
        run.finish()

    print(f"Recursive validation benchmark written to: {out_dir}")
    print(f"Submission-style predictions: {paths['combined']}")
    print(f"Observed prediction grid: {plot_path}")
    print(metrics_df.to_string(index=False))
    return out_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark one recursive per-split model config across all validation splits.")
    parser.add_argument("config", help="Path to the YAML experiment config.")
    parser.add_argument("--output-dir", default=None, help="Override output directory.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_recursive_validation_benchmark(args.config, args.output_dir)
