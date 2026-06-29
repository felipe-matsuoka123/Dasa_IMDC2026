from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import wandb

from dengue_comp.config import save_config


def git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown-not-a-git-repo"


def prepare_run_dir(config: dict[str, Any]) -> Path:
    output_dir = Path(config.get("output", {}).get("run_dir", "outputs/runs"))
    run_name = config.get("experiment", {}).get("name", "experiment")
    run_id = config.get("experiment", {}).get("run_id")
    if not run_id:
        from datetime import datetime

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{run_id}_{run_name}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_run_artifacts(
    run_dir: Path,
    config: dict[str, Any],
    metrics: dict[str, float],
    predictions: pd.DataFrame,
    model,
) -> dict[str, str]:
    paths = {
        "config": str(run_dir / "config.yaml"),
        "metrics": str(run_dir / "metrics.json"),
        "predictions": str(run_dir / "validation_predictions.csv"),
        "model": str(run_dir / "model.joblib"),
    }
    save_config(config, paths["config"])
    with Path(paths["metrics"]).open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, sort_keys=True)
        f.write("\n")
    predictions.to_csv(paths["predictions"], index=False)
    joblib.dump(model, paths["model"])
    return paths


def init_wandb(config: dict[str, Any], run_dir: Path):
    wandb_cfg = config.get("wandb", {})
    project = wandb_cfg.get("project", "dengue-forecast")
    if re.search(r"[/\\,#?%:]", project):
        raise ValueError(
            f"Invalid W&B project name {project!r}. Use a simple project name such as "
            "'dengue-comp'. Put your account/team in wandb.entity instead."
        )
    wandb_root = run_dir / "wandb"
    wandb_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("WANDB_DIR", str(wandb_root))
    os.environ.setdefault("WANDB_CACHE_DIR", str(wandb_root / "cache"))
    os.environ.setdefault("WANDB_CONFIG_DIR", str(wandb_root / "config"))
    return wandb.init(
        project=project,
        entity=wandb_cfg.get("entity"),
        name=config.get("experiment", {}).get("name"),
        config={k: v for k, v in config.items() if not k.startswith("_")},
        mode=wandb_cfg.get("mode", "offline"),
        dir=str(wandb_root),
        reinit="finish_previous",
    )
