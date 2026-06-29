from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import pandas as pd

from dengue_comp.submission import validate_submission_frame
from dengue_comp.tracking import git_commit_hash


PREDICTION_COLUMNS = [
    "date",
    "pred",
    "lower_95",
    "lower_90",
    "lower_80",
    "lower_50",
    "upper_50",
    "upper_80",
    "upper_90",
    "upper_95",
]


def load_api_key(env_names: list[str]) -> str:
    for name in env_names:
        value = os.getenv(name)
        if value:
            return value
    joined = ", ".join(env_names)
    raise RuntimeError(f"Missing Mosqlimate API key. Set one of: {joined}")


def prediction_payload(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[PREDICTION_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def upload_predictions(args: argparse.Namespace) -> None:
    submission = pd.read_csv(args.submission_csv, parse_dates=["date"])
    validate_submission_frame(submission, group_cols=["uf_code"])

    commit = args.commit or git_commit_hash()
    if not commit or commit == "unknown-not-a-git-repo":
        raise RuntimeError("Could not infer git commit. Pass --commit explicitly.")

    groups = list(submission.groupby(["validation", "uf_code"], sort=True))
    print(f"Prepared {len(groups)} uploads from {args.submission_csv}")
    print(f"repository={args.repository}")
    print(f"commit={commit}")
    print(f"disease={args.disease}, case_definition={args.case_definition}, adm_level=1")

    if not args.execute:
        print("Dry run only. Add --execute to submit to Mosqlimate.")
        for (validation, uf_code), part in groups[:5]:
            print(f"would upload {validation} uf_code={int(uf_code)} rows={len(part)}")
        if len(groups) > 5:
            print(f"... and {len(groups) - 5} more uploads")
        return

    api_key = load_api_key(args.api_key_env)
    from mosqlient import upload_prediction

    for (validation, uf_code), part in groups:
        prediction = prediction_payload(part)
        description = f"{args.description_prefix}: {validation}, uf_code={int(uf_code)}"
        result: Any = upload_prediction(
            api_key=api_key,
            repository=args.repository,
            description=description,
            commit=commit,
            disease=args.disease,
            case_definition=args.case_definition,
            adm_level=1,
            adm_1=int(uf_code),
            published=args.published,
            prediction=prediction,
        )
        print(f"uploaded {validation} uf_code={int(uf_code)}: {result}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload July 1 validation predictions to Mosqlimate.")
    parser.add_argument(
        "submission_csv",
        nargs="?",
        default="outputs/submissions/july1/july1_validation_all.csv",
        help="Combined July 1 validation CSV produced by make_july1_validation_submission.py.",
    )
    parser.add_argument("--repository", default="felipe-matsuoka123/Dasa_IMDC2026")
    parser.add_argument("--commit", default=None, help="Git commit hash for the model code. Defaults to current checkout.")
    parser.add_argument("--disease", default="A90", help="ICD-10 disease code. A90 is dengue.")
    parser.add_argument("--case-definition", default="probable", choices=["probable", "reported"])
    parser.add_argument("--description-prefix", default="IMDC 2026 July 1 validation")
    parser.add_argument("--api-key-env", nargs="+", default=["MOSQLIMATE_API_KEY", "API_KEY"])
    parser.add_argument("--published", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--execute", action="store_true", help="Actually upload predictions. Omit for dry-run.")
    return parser.parse_args()


if __name__ == "__main__":
    upload_predictions(parse_args())
