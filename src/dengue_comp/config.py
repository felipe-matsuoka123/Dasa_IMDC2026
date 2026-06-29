from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a YAML mapping: {config_path}")
    config["_config_path"] = str(config_path)
    return config


def save_config(config: dict[str, Any], path: str | Path) -> None:
    serializable = {k: v for k, v in config.items() if not k.startswith("_")}
    with Path(path).open("w", encoding="utf-8") as f:
        yaml.safe_dump(serializable, f, sort_keys=False)

