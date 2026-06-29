from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "smape": float(np.mean(2 * np.abs(y_pred - y_true) / np.maximum(np.abs(y_true) + np.abs(y_pred), 1e-9))),
    }

