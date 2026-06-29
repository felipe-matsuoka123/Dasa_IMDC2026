from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def load_case_data(config: dict[str, Any]) -> pd.DataFrame:
    data_cfg = config["data"]
    path = Path(data_cfg["cases_path"])
    df = pd.read_csv(path, parse_dates=[data_cfg.get("date_col", "date")])

    disease = data_cfg.get("disease")
    if disease and "disease" in df.columns:
        df = df.loc[df["disease"].eq(disease)].copy()

    exclude_uf = set(data_cfg.get("exclude_uf", []))
    if exclude_uf and "uf" in df.columns:
        df = df.loc[~df["uf"].isin(exclude_uf)].copy()

    if data_cfg.get("target_city_only", False):
        df = df.loc[df["target_city"].astype(bool)].copy()

    return df


def aggregate_cases(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    data_cfg = config["data"]
    target_col = data_cfg.get("target_col", "casos")
    date_col = data_cfg.get("date_col", "date")
    group_cols = data_cfg.get("group_cols", ["uf_code"])
    keep_cols = list(dict.fromkeys(group_cols + [date_col, "epiweek"]))
    mask_cols = data_cfg.get("mask_cols", []) + data_cfg.get("train_mask_cols", []) + data_cfg.get("valid_mask_cols", [])
    mask_cols = list(dict.fromkeys(c for c in mask_cols if c in df.columns))

    agg_spec: dict[str, Any] = {target_col: "sum"}
    for col in mask_cols:
        agg_spec[col] = "max"
    if "uf" in df.columns and "uf" not in group_cols:
        agg_spec["uf"] = "first"

    out = (
        df[keep_cols + [target_col] + mask_cols + (["uf"] if "uf" in agg_spec else [])]
        .groupby(keep_cols, as_index=False)
        .agg(agg_spec)
        .sort_values(group_cols + [date_col])
        .reset_index(drop=True)
    )
    for col in mask_cols:
        out[col] = out[col].astype(bool)
    return out


def add_exogenous_features(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    feature_cfg = config.get("features", {})
    exog_cfg = feature_cfg.get("exogenous", {})
    out = df.copy()
    if not exog_cfg.get("enabled", False):
        return out

    if exog_cfg.get("population", {}).get("enabled", False):
        out = _join_population(out, config)
    if exog_cfg.get("environment", {}).get("enabled", False):
        out = _join_environment(out, config)
    if exog_cfg.get("climate", {}).get("enabled", False):
        out = _join_climate(out, config)
    if exog_cfg.get("ocean", {}).get("enabled", False):
        out = _join_ocean(out, config)
    if exog_cfg.get("chikungunya", {}).get("enabled", False):
        out = _join_chikungunya(out, config)
    if exog_cfg.get("afya", {}).get("enabled", False):
        out = _join_afya(out, config)
    return out


def _mapping() -> pd.DataFrame:
    return pd.read_csv("data/map_regional_health.csv", usecols=["geocode", "uf", "uf_code"])


def _join_population(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    pop_cfg = config["features"]["exogenous"]["population"]
    data_cfg = config["data"]
    date_col = data_cfg.get("date_col", "date")
    pop = pd.read_csv(pop_cfg.get("path", "data/datasus_population_2001_2025.csv.gz"))
    pop = pop.merge(_mapping(), on="geocode", how="left")
    pop_state = pop.groupby(["uf_code", "year"], as_index=False)["population"].sum()

    out = df.copy()
    out["year"] = out[date_col].dt.year
    out = out.merge(pop_state, on=["uf_code", "year"], how="left")
    out["population"] = out.groupby("uf_code")["population"].ffill().bfill()
    out["log_population"] = np.log1p(out["population"])
    return out


def _join_environment(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    env_cfg = config["features"]["exogenous"]["environment"]
    env = pd.read_csv(env_cfg.get("path", "data/environ_vars.csv.gz"))
    env["biome"] = env["biome"].fillna("unknown")
    env["koppen"] = env["koppen"].fillna("unknown")

    biome = pd.crosstab(env["uf_code"], env["biome"], normalize="index").add_prefix("biome_share_")
    koppen = pd.crosstab(env["uf_code"], env["koppen"], normalize="index").add_prefix("koppen_share_")
    static = biome.join(koppen).reset_index()
    return df.merge(static, on="uf_code", how="left")


def _join_climate(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    clim_cfg = config["features"]["exogenous"]["climate"]
    data_cfg = config["data"]
    date_col = data_cfg.get("date_col", "date")
    variables = clim_cfg.get("variables", ["temp_med", "precip_tot", "rel_humid_med", "rainy_days"])
    cols = ["date", "geocode"] + variables
    available_cols = pd.read_csv(clim_cfg.get("path", "data/climate.csv.gz"), nrows=0).columns.tolist()
    missing_cols = sorted(set(cols) - set(available_cols))
    if missing_cols:
        raise ValueError(
            f"Climate config requested columns not present in {clim_cfg.get('path', 'data/climate.csv.gz')}: "
            f"{missing_cols}. Available columns: {available_cols}"
        )
    climate = pd.read_csv(clim_cfg.get("path", "data/climate.csv.gz"), usecols=cols, parse_dates=["date"])
    climate = climate.merge(_mapping(), on="geocode", how="left").dropna(subset=["uf_code"])
    climate_state = climate.groupby(["uf_code", "date"], as_index=False)[variables].mean()
    climate_state = _add_group_lags(climate_state, ["uf_code"], date_col, variables, clim_cfg.get("lags", [1, 4, 8]))
    keep_cols = ["uf_code", date_col] + [c for c in climate_state.columns if c.startswith("climate_")]
    return df.merge(climate_state[keep_cols], on=["uf_code", date_col], how="left")


def _join_ocean(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    ocean_cfg = config["features"]["exogenous"]["ocean"]
    data_cfg = config["data"]
    date_col = data_cfg.get("date_col", "date")
    variables = ocean_cfg.get("variables", ["enso", "iod", "pdo"])
    ocean = pd.read_csv(ocean_cfg.get("path", "data/ocean_climate_oscillations.csv.gz"), parse_dates=["date"])
    ocean = ocean[["date"] + variables].sort_values("date")
    for lag in ocean_cfg.get("lags", [1, 4, 12]):
        for col in variables:
            ocean[f"ocean_{col}_lag_{lag}"] = ocean[col].shift(lag)
    keep_cols = ["date"] + [c for c in ocean.columns if c.startswith("ocean_")]
    return df.merge(ocean[keep_cols], left_on=date_col, right_on="date", how="left").drop(columns=["date_y"], errors="ignore").rename(columns={"date_x": date_col})


def _join_chikungunya(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    chik_cfg = config["features"]["exogenous"]["chikungunya"]
    data_cfg = config["data"]
    date_col = data_cfg.get("date_col", "date")
    chik = pd.read_csv(chik_cfg.get("path", "data/chikungunya.csv.gz"), parse_dates=[date_col])
    exclude_uf = set(data_cfg.get("exclude_uf", []))
    if exclude_uf:
        chik = chik.loc[~chik["uf"].isin(exclude_uf)].copy()
    chik_state = chik.groupby(["uf_code", date_col], as_index=False)["casos"].sum().rename(columns={"casos": "chik_cases"})
    chik_state = _add_group_lags(chik_state, ["uf_code"], date_col, ["chik_cases"], chik_cfg.get("lags", [1, 4, 8, 12]))
    keep_cols = ["uf_code", date_col] + [c for c in chik_state.columns if c.startswith("chik_cases_")]
    return df.merge(chik_state[keep_cols], on=["uf_code", date_col], how="left")


def _join_afya(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    afya_cfg = config["features"]["exogenous"]["afya"]
    data_cfg = config["data"]
    date_col = data_cfg.get("date_col", "date")
    afya = pd.read_csv(afya_cfg.get("path", "data/access_afya_dengue_2021_2026.csv.gz"), parse_dates=["access_date"])
    disease = afya_cfg.get("accessed_disease", "Dengue").lower()
    afya = afya.loc[afya["accessed_disease"].str.lower().eq(disease)].copy()
    afya["date"] = afya["access_date"] - pd.to_timedelta(afya["access_date"].dt.weekday + 1, unit="D")
    afya_state = afya.groupby(["uf", "date"], as_index=False)["access_count"].sum()
    uf_lookup = _mapping()[["uf", "uf_code"]].drop_duplicates()
    afya_state = afya_state.merge(uf_lookup, on="uf", how="left").dropna(subset=["uf_code"])
    afya_state = afya_state.groupby(["uf_code", "date"], as_index=False)["access_count"].sum()
    afya_state = _add_group_lags(afya_state, ["uf_code"], "date", ["access_count"], afya_cfg.get("lags", [1, 2, 4]))
    keep_cols = ["uf_code", "date"] + [c for c in afya_state.columns if c.startswith("access_count_")]
    return df.merge(afya_state[keep_cols], left_on=["uf_code", date_col], right_on=["uf_code", "date"], how="left").drop(columns=["date_y"], errors="ignore").rename(columns={"date_x": date_col})


def _add_group_lags(
    df: pd.DataFrame,
    group_cols: list[str],
    date_col: str,
    variables: list[str],
    lags: list[int],
) -> pd.DataFrame:
    out = df.sort_values(group_cols + [date_col]).copy()
    grouped = out.groupby(group_cols, sort=False)
    prefix = "climate_" if set(variables) - {"chik_cases", "access_count"} else ""
    for lag in lags:
        for col in variables:
            name = f"{prefix}{col}_lag_{lag}"
            out[name] = grouped[col].shift(lag)
    return out


def add_time_features(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    data_cfg = config["data"]
    feat_cfg = config.get("features", {})
    date_col = data_cfg.get("date_col", "date")
    group_cols = data_cfg.get("group_cols", ["uf_code"])
    target_col = data_cfg.get("target_col", "casos")

    out = df.sort_values(group_cols + [date_col]).copy()
    iso = out[date_col].dt.isocalendar()
    out["year"] = iso.year.astype(int)
    out["weekofyear"] = iso.week.astype(int)
    out["month"] = out[date_col].dt.month.astype(int)
    out["week_sin"] = np.sin(2 * np.pi * out["weekofyear"] / 53.0)
    out["week_cos"] = np.cos(2 * np.pi * out["weekofyear"] / 53.0)

    grouped = out.groupby(group_cols, sort=False)[target_col]
    for lag in feat_cfg.get("lags", [1, 2, 4, 8, 12, 26, 52]):
        out[f"lag_{lag}"] = grouped.shift(lag)
    for window in feat_cfg.get("rolling_windows", [4, 8, 12]):
        shifted = grouped.shift(1)
        rolling = shifted.groupby([out[c] for c in group_cols]).rolling(window)
        out[f"roll_mean_{window}"] = rolling.mean().reset_index(level=group_cols, drop=True)
        out[f"roll_std_{window}"] = rolling.std().reset_index(level=group_cols, drop=True)

    out = _add_derivative_features(out, config)

    fill_value = feat_cfg.get("missing_value", 0)
    feature_cols = get_feature_columns(out, config)
    out[feature_cols] = out[feature_cols].fillna(fill_value)
    return out


def _add_derivative_features(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    data_cfg = config["data"]
    feat_cfg = config.get("features", {})
    date_col = data_cfg.get("date_col", "date")
    group_cols = data_cfg.get("group_cols", ["uf_code"])
    target_col = data_cfg.get("target_col", "casos")

    out = df.sort_values(group_cols + [date_col]).copy()
    grouped = out.groupby(group_cols, sort=False)[target_col]
    lag_cache: dict[int, pd.Series] = {}

    def lag(period: int) -> pd.Series:
        if period not in lag_cache:
            col = f"lag_{period}"
            lag_cache[period] = out[col] if col in out.columns else grouped.shift(period)
        return lag_cache[period]

    for period in feat_cfg.get("differences", []):
        out[f"diff_{period}"] = lag(1) - lag(1 + period)

    for period in feat_cfg.get("accelerations", []):
        out[f"accel_{period}"] = lag(1) - 2 * lag(1 + period) + lag(1 + 2 * period)

    for window in feat_cfg.get("growth_windows", []):
        mean_col = f"roll_mean_{window}"
        baseline = out[mean_col] if mean_col in out.columns else grouped.shift(1).groupby([out[c] for c in group_cols]).rolling(window).mean().reset_index(level=group_cols, drop=True)
        out[f"growth_ratio_{window}"] = lag(1) / (baseline + 1.0)

    shifted = grouped.shift(1)
    for window in feat_cfg.get("slope_windows", []):
        out[f"roll_slope_{window}"] = (
            shifted.groupby([out[c] for c in group_cols])
            .rolling(window)
            .apply(_linear_slope, raw=True)
            .reset_index(level=group_cols, drop=True)
        )

    return out


def _linear_slope(values: np.ndarray) -> float:
    if np.isnan(values).any():
        return np.nan
    x = np.arange(len(values), dtype=float)
    x_centered = x - x.mean()
    denominator = float(np.dot(x_centered, x_centered))
    if denominator == 0:
        return 0.0
    return float(np.dot(x_centered, values - values.mean()) / denominator)


def get_feature_columns(df: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    data_cfg = config["data"]
    group_cols = data_cfg.get("group_cols", ["uf_code"])
    base_cols = ["year", "weekofyear", "month", "week_sin", "week_cos"]
    case_feature_prefixes = ("lag_", "roll_", "diff_", "accel_", "growth_ratio_")
    lag_cols = [c for c in df.columns if c.startswith(case_feature_prefixes)]
    exog_prefixes = (
        "climate_",
        "ocean_",
        "chik_cases_",
        "access_count_",
        "biome_share_",
        "koppen_share_",
    )
    exog_cols = [c for c in df.columns if c.startswith(exog_prefixes)]
    scalar_cols = [c for c in ["population", "log_population"] if c in df.columns]
    feature_cols = group_cols + base_cols + lag_cols + scalar_cols + exog_cols
    return list(dict.fromkeys([c for c in feature_cols if c in df.columns]))


def split_data(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    data_cfg = config["data"]
    train_cols = data_cfg.get("train_mask_cols", [])
    valid_cols = data_cfg.get("valid_mask_cols", [])
    date_col = data_cfg.get("date_col", "date")

    if train_cols:
        train_mask = np.logical_or.reduce([df[c].astype(bool).to_numpy() for c in train_cols])
    else:
        train_end = pd.Timestamp(data_cfg["train_end_date"])
        train_mask = df[date_col].le(train_end).to_numpy()

    if valid_cols:
        valid_mask = np.logical_or.reduce([df[c].astype(bool).to_numpy() for c in valid_cols])
    else:
        valid_start = pd.Timestamp(data_cfg["valid_start_date"])
        valid_end = pd.Timestamp(data_cfg["valid_end_date"])
        valid_mask = df[date_col].between(valid_start, valid_end).to_numpy()

    train = df.loc[train_mask].copy()
    valid = df.loc[valid_mask].copy()
    if train.empty or valid.empty:
        raise ValueError(f"Empty split produced: train={len(train)}, valid={len(valid)}")
    if train[date_col].max() >= valid[date_col].min():
        raise ValueError("Validation is not strictly after training. Check time-aware split config.")
    return train, valid
