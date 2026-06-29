from __future__ import annotations

import argparse
import os
from pathlib import Path

import geopandas as gpd

os.environ.setdefault("MPLCONFIGDIR", str(Path("outputs/eda/.matplotlib").resolve()))
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


DATA_DIR = Path("data")
OUT_DIR = Path("outputs/eda")


def savefig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()


def read_cases(filename: str) -> pd.DataFrame:
    cols = ["date", "casos", "uf", "uf_code", "target_city", "train_4", "target_4"]
    df = pd.read_csv(DATA_DIR / filename, usecols=cols, parse_dates=["date"])
    return df.loc[df["uf"].ne("ES")].copy()


def plot_case_overview(dengue: pd.DataFrame, chik: pd.DataFrame, out_dir: Path) -> Path:
    dengue_week = dengue.groupby("date", as_index=False)["casos"].sum()
    dengue_week["disease"] = "Dengue"
    chik_week = chik.groupby("date", as_index=False)["casos"].sum()
    chik_week["disease"] = "Chikungunya"
    both = pd.concat([dengue_week, chik_week], ignore_index=True)

    plt.figure(figsize=(13, 5))
    sns.lineplot(data=both, x="date", y="casos", hue="disease", linewidth=1.8)
    plt.title("Weekly reported cases in Brazil, excluding ES")
    plt.xlabel("")
    plt.ylabel("Cases")
    plt.legend(title="")
    path = out_dir / "01_cases_over_time.png"
    savefig(path)
    return path


def plot_state_heatmap(dengue: pd.DataFrame, out_dir: Path) -> Path:
    recent = dengue.loc[dengue["date"].dt.year.ge(2021)].copy()
    recent["year"] = recent["date"].dt.year
    state_year = recent.groupby(["uf", "year"], as_index=False)["casos"].sum()
    pivot = state_year.pivot(index="uf", columns="year", values="casos").fillna(0)
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]

    plt.figure(figsize=(10, 8))
    sns.heatmap(pivot, cmap="rocket_r", linewidths=0.2, linecolor="white")
    plt.title("Dengue burden by state and year")
    plt.xlabel("")
    plt.ylabel("")
    path = out_dir / "02_state_year_heatmap.png"
    savefig(path)
    return path


def plot_target_season(dengue: pd.DataFrame, out_dir: Path) -> Path:
    season = dengue.loc[dengue["train_4"] | dengue["target_4"]].copy()
    season_week = season.groupby(["date", "target_4"], as_index=False)["casos"].sum()
    season_week["split"] = season_week["target_4"].map({False: "train_4", True: "target_4"})

    plt.figure(figsize=(12, 4))
    sns.lineplot(data=season_week, x="date", y="casos", hue="split", linewidth=2)
    plt.title("Current competition season split signal: train_4 vs target_4")
    plt.xlabel("")
    plt.ylabel("Dengue cases")
    plt.legend(title="")
    path = out_dir / "03_train_target_season.png"
    savefig(path)
    return path


def plot_population(population: pd.DataFrame, mapping: pd.DataFrame, out_dir: Path) -> Path:
    latest_year = int(population["year"].max())
    pop = population.loc[population["year"].eq(latest_year)].merge(
        mapping[["geocode", "uf"]].drop_duplicates(), on="geocode", how="left"
    )
    state_pop = pop.groupby("uf", as_index=False)["population"].sum().sort_values("population", ascending=False)

    plt.figure(figsize=(11, 5))
    sns.barplot(data=state_pop.head(15), x="population", y="uf", color="#4c78a8")
    plt.title(f"Largest state populations in {latest_year}")
    plt.xlabel("Population")
    plt.ylabel("")
    path = out_dir / "04_population_by_state.png"
    savefig(path)
    return path


def plot_climate_vs_cases(dengue: pd.DataFrame, mapping: pd.DataFrame, out_dir: Path) -> Path:
    climate_cols = ["date", "geocode", "temp_med", "precip_med", "rel_humid_med", "rainy_days"]
    climate = pd.read_csv(DATA_DIR / "climate.csv.gz", usecols=climate_cols, parse_dates=["date"])
    climate = climate.merge(mapping[["geocode", "uf"]].drop_duplicates(), on="geocode", how="left")
    climate = climate.dropna(subset=["uf"])
    climate_state = climate.groupby(["uf", "date"], as_index=False).agg(
        temp_med=("temp_med", "mean"),
        precip_med=("precip_med", "mean"),
        rel_humid_med=("rel_humid_med", "mean"),
        rainy_days=("rainy_days", "mean"),
    )
    cases_state = dengue.groupby(["uf", "date"], as_index=False)["casos"].sum()
    joined = cases_state.merge(climate_state, on=["uf", "date"], how="inner")
    joined = joined.loc[joined["date"].dt.year.ge(2020)].copy()
    sample = joined.sample(min(4000, len(joined)), random_state=42)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, col, title in zip(
        axes,
        ["temp_med", "precip_med", "rel_humid_med"],
        ["Temperature", "Precipitation", "Humidity"],
    ):
        sns.scatterplot(data=sample, x=col, y="casos", hue="rainy_days", size=None, alpha=0.35, ax=ax, legend=False)
        ax.set_title(title)
        ax.set_ylabel("Weekly dengue cases")
        ax.set_xlabel(col)
    fig.suptitle("Observed climate and dengue burden by state-week since 2020", y=1.03)
    path = out_dir / "05_climate_vs_cases.png"
    savefig(path)
    return path


def plot_ocean(out_dir: Path) -> Path:
    ocean = pd.read_csv(DATA_DIR / "ocean_climate_oscillations.csv.gz", parse_dates=["date"])
    ocean = ocean.loc[ocean["date"].dt.year.ge(2010)].copy()
    long = ocean.melt(id_vars="date", value_vars=["enso", "iod", "pdo"], var_name="indicator", value_name="value")

    plt.figure(figsize=(12, 4))
    sns.lineplot(data=long, x="date", y="value", hue="indicator", linewidth=1.2)
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Ocean climate oscillation indicators")
    plt.xlabel("")
    plt.ylabel("Index value")
    plt.legend(title="")
    path = out_dir / "06_ocean_oscillations.png"
    savefig(path)
    return path


def plot_forecast_climate(out_dir: Path) -> Path:
    fc = pd.read_csv(DATA_DIR / "forecasting_climate.csv.gz", parse_dates=["reference_month"])
    fc["reference_month"] = pd.to_datetime(fc["reference_month"], format="mixed")
    latest_ref = fc["reference_month"].max()
    latest = fc.loc[fc["reference_month"].eq(latest_ref)].copy()
    summary = latest.groupby("forecast_months_ahead", as_index=False).agg(
        temp_med=("temp_med", "mean"),
        precip_tot=("precip_tot", "mean"),
        umid_med=("umid_med", "mean"),
    )

    fig, ax1 = plt.subplots(figsize=(10, 4))
    sns.lineplot(data=summary, x="forecast_months_ahead", y="temp_med", marker="o", ax=ax1, color="#e45756")
    ax1.set_ylabel("Mean forecast temp")
    ax1.set_xlabel("Months ahead")
    ax2 = ax1.twinx()
    sns.lineplot(data=summary, x="forecast_months_ahead", y="precip_tot", marker="o", ax=ax2, color="#4c78a8")
    ax2.set_ylabel("Mean forecast precipitation")
    plt.title(f"National average climate forecast profile from {latest_ref.date()}")
    path = out_dir / "07_forecast_climate_profile.png"
    savefig(path)
    return path


def plot_afya(dengue: pd.DataFrame, out_dir: Path) -> Path:
    afya = pd.read_csv(DATA_DIR / "access_afya_dengue_2021_2026.csv.gz", parse_dates=["access_date"])
    afya = afya.loc[afya["accessed_disease"].str.lower().eq("dengue")].copy()
    afya["date"] = afya["access_date"] - pd.to_timedelta(afya["access_date"].dt.weekday + 1, unit="D")
    access_week = afya.groupby("date", as_index=False)["access_count"].sum()
    cases_week = dengue.groupby("date", as_index=False)["casos"].sum()
    joined = access_week.merge(cases_week, on="date", how="inner")
    joined = joined.loc[joined["date"].dt.year.ge(2021)].copy()

    fig, ax1 = plt.subplots(figsize=(12, 4))
    sns.lineplot(data=joined, x="date", y="access_count", ax=ax1, color="#54a24b", label="Afya access")
    ax1.set_ylabel("Access count")
    ax2 = ax1.twinx()
    sns.lineplot(data=joined, x="date", y="casos", ax=ax2, color="#e45756", label="Dengue cases")
    ax2.set_ylabel("Dengue cases")
    plt.title("Afya dengue-content access vs reported dengue cases")
    path = out_dir / "08_afya_access_vs_cases.png"
    savefig(path)
    return path


def plot_environment(environ: pd.DataFrame, out_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    biome = environ["biome"].value_counts().head(10).reset_index()
    biome.columns = ["biome", "municipalities"]
    koppen = environ["koppen"].value_counts().head(10).reset_index()
    koppen.columns = ["koppen", "municipalities"]
    sns.barplot(data=biome, x="municipalities", y="biome", ax=axes[0], color="#72b7b2")
    sns.barplot(data=koppen, x="municipalities", y="koppen", ax=axes[1], color="#f58518")
    axes[0].set_title("Municipalities by biome")
    axes[1].set_title("Municipalities by Koppen class")
    axes[0].set_ylabel("")
    axes[1].set_ylabel("")
    path = out_dir / "09_environment_categories.png"
    savefig(path)
    return path


def plot_map(dengue: pd.DataFrame, mapping: pd.DataFrame, out_dir: Path) -> Path:
    muni = gpd.read_file(DATA_DIR / "shape_muni.gpkg")
    if "geocode" not in muni.columns:
        possible = [c for c in muni.columns if "code" in c.lower()]
        if not possible:
            raise ValueError("Could not find geocode column in shape_muni.gpkg")
        muni = muni.rename(columns={possible[0]: "geocode"})

    recent = dengue.loc[dengue["date"].dt.year.ge(2024)].copy()
    state_cases = recent.groupby("uf", as_index=False)["casos"].sum()
    if "uf" not in muni.columns:
        geocode_uf = mapping[["geocode", "uf"]].drop_duplicates()
        muni = muni.merge(geocode_uf, on="geocode", how="left")
    muni = muni.merge(state_cases, on="uf", how="left")

    ax = muni.plot(column="casos", cmap="Reds", linewidth=0.05, edgecolor="white", figsize=(8, 8), legend=True)
    ax.set_axis_off()
    ax.set_title("Recent dengue burden by state, shown across municipalities")
    path = out_dir / "10_recent_dengue_map.png"
    savefig(path)
    return path


def write_report(paths: list[Path], out_dir: Path) -> None:
    lines = [
        "# Dengue Competition EDA",
        "",
        "This report is generated by `scripts/make_eda.py` and summarizes the main available data sources.",
        "",
    ]
    captions = {
        "01_cases_over_time.png": "Dengue and chikungunya weekly burden over time.",
        "02_state_year_heatmap.png": "State-year dengue burden highlights spatial and temporal concentration.",
        "03_train_target_season.png": "Competition split view for the current training/target season.",
        "04_population_by_state.png": "Population scale by state for denominator-aware modeling.",
        "05_climate_vs_cases.png": "Observed climate variables compared with state-week dengue cases.",
        "06_ocean_oscillations.png": "Large-scale ocean indicators available as national temporal predictors.",
        "07_forecast_climate_profile.png": "Climate forecast profile available for forward-looking features.",
        "08_afya_access_vs_cases.png": "Afya dengue-content access signal compared with dengue cases.",
        "09_environment_categories.png": "Static environmental coverage by biome and Koppen class.",
        "10_recent_dengue_map.png": "Geographic distribution of recent dengue burden.",
    }
    for path in paths:
        rel = path.relative_to(out_dir)
        lines.extend([f"## {path.stem}", "", captions.get(path.name, ""), "", f"![{path.stem}]({rel})", ""])
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a compact EDA report for all dengue competition data sources.")
    parser.add_argument("--output-dir", default=str(OUT_DIR), help="Directory for plots and report.")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")

    dengue = read_cases("dengue.csv.gz")
    chik = read_cases("chikungunya.csv.gz")
    mapping = pd.read_csv(DATA_DIR / "map_regional_health.csv", usecols=["geocode", "uf", "uf_code"])
    population = pd.read_csv(DATA_DIR / "datasus_population_2001_2025.csv.gz")
    environ = pd.read_csv(DATA_DIR / "environ_vars.csv.gz")

    paths = [
        plot_case_overview(dengue, chik, out_dir),
        plot_state_heatmap(dengue, out_dir),
        plot_target_season(dengue, out_dir),
        plot_population(population, mapping, out_dir),
        plot_climate_vs_cases(dengue, mapping, out_dir),
        plot_ocean(out_dir),
        plot_forecast_climate(out_dir),
        plot_afya(dengue, out_dir),
        plot_environment(environ, out_dir),
    ]
    try:
        paths.append(plot_map(dengue, mapping, out_dir))
    except Exception as exc:
        print(f"Skipping map plot: {exc}")
    write_report(paths, out_dir)
    print(f"EDA report written to {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
