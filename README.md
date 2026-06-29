# Dasa IMDC 2026

This repo contains our code for the 3rd Infodengue-Mosqlimate Dengue Challenge.
The model forecasts weekly dengue cases at the Brazilian state level, excluding
Espirito Santo as required by the challenge.

## Team

- Victor Goncalves Soares
- Felipe Akio Matsuoka
- Raphael Federicci Haddad
- Cristina Mendes de Oliveira
- Alberto Chebabo

Contact: victorsoares.ext@dasa.com.br or felipe.matsuoka.ext@dasa.com.br

## How to Run

Create the environment:

```bash
conda env update -f environment.yml --prune
```

Download the official competition data described in `docs/Data.md` and place the
raw files in `data/`. Raw data is not stored in this repository.

Generate the July 1 validation files:

```bash
conda run -n dengue-forecast python scripts/make_july1_validation_submission.py configs/baseline_state_dengue.yaml
```

The CSVs will be written to:

```text
outputs/submissions/july1/
```

## What Is Here

- `configs/`: model and feature settings
- `scripts/`: commands to train, validate, and create submissions
- `src/dengue_comp/`: reusable Python code
- `docs/`: challenge rules and data notes

The validation submission includes median forecasts and 50%, 80%, 90%, and 95%
prediction intervals for every required state.
