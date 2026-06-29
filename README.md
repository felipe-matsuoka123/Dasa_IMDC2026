# Dasa IMDC 2026

Reproducible workflow for the 3rd Infodengue-Mosqlimate Dengue Challenge.
The registered model targets the mandatory dengue state-level challenge:
weekly dengue case forecasts for all Brazilian states except Espirito Santo.

## Team and Contributors

- Victor Goncalves Soares
- Felipe Akio Matsuoka
- Raphael Federicci Haddad
- Cristina Mendes de Oliveira
- Alberto Chebabo

Contact: victorsoares.ext@dasa.com.br or felipe.matsuoka.ext@dasa.com.br

## Repository Structure

- `configs/`: YAML experiment definitions.
- `scripts/`: runnable commands for training, validation, EDA, and submission generation.
- `src/dengue_comp/`: reusable data, feature, modeling, metric, submission, and tracking code.
- `docs/`: local copy of competition rules and data documentation.
- `data/processed/`: destination for derived data outputs.
- `outputs/`: generated outputs, ignored by git.

Raw competition data should be placed under `data/` locally and is not committed.

## Libraries and Dependencies

Create or update the conda environment:

```bash
conda env update -f environment.yml --prune
```

Run Python commands inside the environment:

```bash
conda run -n dengue-forecast python ...
```

The package metadata is defined in `pyproject.toml`; the full reproducible
runtime environment is defined in `environment.yml`.

## Data and Variables

The workflow uses the official 3rd IMDC data files from the Mosqlimate FTP/API,
including dengue cases and optional exogenous covariates such as population,
environmental variables, climate, ocean climate indicators, chikungunya cases,
and Afya access counts.

The main target is `casos`, aggregated weekly by `uf_code`. The time resolution
is weekly epidemiological weeks, with dates represented by Sundays.

The mandatory validation output excludes Espirito Santo (`ES`) and forecasts all
other Brazilian states.

See:

- `docs/Rules.md`
- `docs/Data.md`

## Model Training

Every experiment is controlled by a YAML config. A standard validation run can
be launched with:

```bash
conda run -n dengue-forecast python scripts/run_experiment.py configs/baseline_state_dengue.yaml
```

The compatibility wrapper is:

```bash
conda run -n dengue-forecast python scripts/train.py --config configs/baseline_state_dengue.yaml
```

A stronger LightGBM baseline is available at:

```bash
conda run -n dengue-forecast python scripts/run_experiment.py configs/solid_baseline_state_dengue_lightgbm.yaml
```

To benchmark one recursive model configuration across all four official
validation splits:

```bash
conda run -n dengue-forecast python scripts/run_recursive_validation_benchmark.py configs/minimal_recursive_per_split_state_dengue_hgb.yaml
```

A direct-horizon validation strategy is available with:

```bash
conda run -n dengue-forecast python scripts/run_direct_horizon_validation.py configs/direct_horizon_state_dengue_lightgbm.yaml
```

## July 1 Validation Submission

Generate the validation package required for the July 1, 2026 deadline:

```bash
conda run -n dengue-forecast python scripts/make_july1_validation_submission.py configs/baseline_state_dengue.yaml
```

This writes:

- `outputs/submissions/july1/july1_validation_all.csv`
- `outputs/submissions/july1/july1_validation_1.csv`
- `outputs/submissions/july1/july1_validation_2.csv`
- `outputs/submissions/july1/july1_validation_3.csv`
- `outputs/submissions/july1/july1_validation_4.csv`
- `outputs/submissions/july1/july1_validation_metrics.json`
- `outputs/submissions/july1/july1_submission_config.yaml`

Each validation file contains state-level dengue forecasts for all states except
ES, with median predictions and 50%, 80%, 90%, and 95% prediction intervals.

## Data Usage Restriction

Raw data files are not versioned in this repository. Download the official
competition data through the sources described in `docs/Data.md` and place the
files under `data/` using the filenames referenced by the configs.

External datasets not available through the official FTP server or Mosqlimate
API must be shared with the organizers according to the challenge rules.

## Predictive Uncertainty

Submission files include:

- `pred`
- `lower_50`, `upper_50`
- `lower_80`, `upper_80`
- `lower_90`, `upper_90`
- `lower_95`, `upper_95`

The baseline submission script estimates interval widths from absolute training
residual quantiles, clips predictions to non-negative values, and enforces
nested prediction intervals before writing CSV files.

## Experiment Tracking

Training and validation scripts log metrics, predictions, configs, and artifacts
to Weights & Biases according to the active config. Use `wandb.mode: online`
after authenticating locally, or `offline` for local smoke tests.

## References

- 3rd Infodengue-Mosqlimate Dengue Challenge rules: `docs/Rules.md`
- 3rd IMDC data documentation: `docs/Data.md`
- Mosqlimate platform and official challenge materials
