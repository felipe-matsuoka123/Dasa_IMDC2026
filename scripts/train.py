from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_experiment import run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compatibility wrapper for experiment training.")
    parser.add_argument("--config", required=True, help="Path to the YAML experiment config.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.config)
