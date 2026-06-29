from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", str(Path("outputs/eda/.matplotlib").resolve()))
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch


SPLITS = {
    "Validation 1": ("train_1", "target_1"),
    "Validation 2": ("train_2", "target_2"),
    "Validation 3": ("train_3", "target_3"),
    "Validation 4": ("train_4", "target_4"),
}

STATUS = {
    "unused": 0,
    "train": 1,
    "gap": 2,
    "target_observed": 3,
    "target_unreported": 4,
}


def split_status_table(cases_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    usecols = ["date", "epiweek", "uf", *[col for pair in SPLITS.values() for col in pair]]
    df = pd.read_csv(cases_path, usecols=usecols, parse_dates=["date"])
    df = df.loc[df["uf"].ne("ES")].copy()
    weekly = (
        df.drop(columns=["uf"])
        .groupby(["date", "epiweek"], as_index=False)
        .max()
        .sort_values("date")
    )

    full_target_ends = []
    split_ranges = []
    for label, (train_col, target_col) in SPLITS.items():
        train_dates = weekly.loc[weekly[train_col].astype(bool), "date"]
        target_dates = weekly.loc[weekly[target_col].astype(bool), "date"]
        if train_dates.empty or target_dates.empty:
            raise ValueError(f"Missing train/target dates for {label}")
        target_start = target_dates.min()
        target_observed_end = target_dates.max()
        target_full = pd.date_range(target_start, periods=52, freq="W-SUN")
        full_target_ends.append(target_full.max())
        split_ranges.append(
            {
                "validation": label,
                "train_start": train_dates.min(),
                "train_end": train_dates.max(),
                "gap_start": train_dates.max() + pd.Timedelta(days=7),
                "gap_end": target_start - pd.Timedelta(days=7),
                "target_start": target_start,
                "target_observed_end": target_observed_end,
                "target_end": target_full.max(),
                "n_observed_target_weeks": int(target_dates.nunique()),
                "n_full_target_weeks": int(len(target_full)),
                "n_unreported_target_weeks": int(len(target_full) - target_dates.nunique()),
            }
        )

    calendar = pd.DataFrame(
        {"date": pd.date_range(weekly["date"].min(), max(full_target_ends), freq="W-SUN")}
    )
    iso = calendar["date"].dt.isocalendar()
    calendar["epiweek"] = iso.year.astype(int) * 100 + iso.week.astype(int)

    rows = []
    for label, (train_col, target_col) in SPLITS.items():
        merged = calendar.merge(weekly[["date", train_col, target_col]], on="date", how="left")
        merged[[train_col, target_col]] = merged[[train_col, target_col]].fillna(False).astype(bool)

        train_dates = merged.loc[merged[train_col], "date"]
        observed_target_dates = merged.loc[merged[target_col], "date"]
        target_start = observed_target_dates.min()
        target_full = pd.date_range(target_start, periods=52, freq="W-SUN")
        train_end = train_dates.max()

        status = np.full(len(merged), STATUS["unused"], dtype=int)
        status[merged[train_col].to_numpy()] = STATUS["train"]
        gap_mask = merged["date"].between(train_end + pd.Timedelta(days=7), target_start - pd.Timedelta(days=7))
        status[gap_mask.to_numpy()] = STATUS["gap"]
        full_target_mask = merged["date"].isin(target_full)
        observed_target_mask = merged["date"].isin(observed_target_dates)
        status[full_target_mask.to_numpy()] = STATUS["target_unreported"]
        status[observed_target_mask.to_numpy()] = STATUS["target_observed"]

        row = pd.DataFrame(
            {
                "validation": label,
                "date": merged["date"],
                "epiweek": merged["epiweek"],
                "status_code": status,
            }
        )
        rows.append(row)

    return pd.concat(rows, ignore_index=True), pd.DataFrame(split_ranges)


def plot_heatmap(status: pd.DataFrame, ranges: pd.DataFrame, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pivot = status.pivot(index="validation", columns="date", values="status_code").loc[list(SPLITS)]
    dates = pd.to_datetime(pivot.columns)
    matrix = pivot.to_numpy()

    cmap = ListedColormap(["#e6e6e6", "#4c78a8", "#f2a541", "#d64b4b", "#f4b6b6"])
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap=cmap, vmin=0, vmax=4)

    year_starts = [i for i, date in enumerate(dates) if date.month == 1 and date.day <= 7]
    for x in year_starts[1:]:
        ax.vlines(
            x - 0.5,
            -0.5,
            len(pivot.index) - 0.5,
            color="black",
            linewidth=0.6,
            linestyles="--",
            alpha=0.35,
        )
    ax.set_xticks(year_starts)
    ax.set_xticklabels([str(dates[i].year) for i in year_starts], rotation=0)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.tick_params(axis="both", labelsize=12)
    ax.set_xlabel("Calendar year / epidemiological weeks")
    ax.xaxis.label.set_size(13)
    ax.set_title(
        "Validation Split Structure",
        fontsize=20,
        fontweight="bold",
        pad=18,
    )
    ax.text(
        0.5,
        1.01,
        "Train period, EW26-EW40 gap, and observed vs unreported target weeks",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=13,
        color="#444444",
    )

    for row_idx, label in enumerate(pivot.index):
        row = ranges.loc[ranges["validation"].eq(label)].iloc[0]
        for boundary in ["train_end", "target_start", "target_end"]:
            boundary_date = pd.Timestamp(row[boundary])
            if boundary_date in set(dates):
                x = int(np.where(dates == boundary_date)[0][0])
                ax.vlines(x + 0.5, row_idx - 0.45, row_idx + 0.45, color="black", linewidth=0.8, alpha=0.6)

    legend = [
        Patch(facecolor="#4c78a8", label="Allowed training data"),
        Patch(facecolor="#f2a541", label="EW26-EW40 gap: exists in raw data, not allowed"),
        Patch(facecolor="#d64b4b", label="Target weeks with actual dengue cases available"),
        Patch(facecolor="#f4b6b6", label="Target weeks required for submission, not yet reported"),
        Patch(facecolor="#e6e6e6", label="Not used for that validation split"),
    ]
    ax.legend(
        handles=legend,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        ncol=3,
        frameon=False,
        fontsize=12,
        handlelength=1.8,
        columnspacing=1.8,
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.84, bottom=0.24)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize train/gap/target periods for all validation splits.")
    parser.add_argument("--cases-path", default="data/dengue.csv.gz", help="Path to dengue case CSV.")
    parser.add_argument("--output", default="outputs/eda/validation_split_heatmap.png", help="Output PNG path.")
    parser.add_argument("--ranges-output", default="outputs/eda/validation_split_ranges.csv", help="Output CSV with split ranges.")
    args = parser.parse_args()

    status, ranges = split_status_table(args.cases_path)
    output_path = plot_heatmap(status, ranges, args.output)
    ranges.to_csv(args.ranges_output, index=False)
    print(f"Heatmap written to {output_path}")
    print(f"Split ranges written to {args.ranges_output}")


if __name__ == "__main__":
    main()
