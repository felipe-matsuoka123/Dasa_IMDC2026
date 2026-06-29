from __future__ import annotations

from typing import Any

import numpy as np
from lightgbm import LGBMRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge


def build_model(config: dict[str, Any]):
    model_cfg = config.get("model", {})
    name = model_cfg.get("name", "hist_gradient_boosting")
    params = model_cfg.get("params", {})

    if name == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(**params)
    if name == "random_forest":
        return RandomForestRegressor(**params)
    if name == "ridge":
        return Ridge(**params)
    if name == "lightgbm":
        return LGBMRegressor(**params)
    raise ValueError(f"Unsupported model.name: {name}")


def clip_predictions(values: np.ndarray) -> np.ndarray:
    return np.maximum(values, 0)
