# Rules – 3rd Infodengue–Mosqlimate Dengue Challenge (IMDC)

To participate in the challenge, please carefully review and comply with the following rules and requirements.

---

# 1. Challenge Structure

The competition includes one mandatory challenge and three optional challenges.

## Mandatory Challenge

### Dengue (State Level)

Forecast dengue cases at the state (*UF*) level for all Brazilian states, except Espírito Santo.

## Optional Challenges

### Optional Challenge 1 – Dengue (City Level)

Forecast dengue cases for 15 selected cities.

### Optional Challenge 2 – Chikungunya (State Level)

Forecast chikungunya cases at the state (*UF*) level for all Brazilian states, except Espírito Santo.

### Optional Challenge 3 – Chikungunya (City Level)

Forecast chikungunya cases for 10 selected cities.

---

# 2. Model Requirements

## Public Repository

Your model must be hosted in a public repository on either:

* GitHub
* GitLab

## Model Registration

The model must be registered on the Mosqlimate platform using the following naming convention:

```text
3rd_imdc_{institution}_{team_name}
```

### Naming Rules

* All characters must be lowercase.
* `institution` must correspond to the acronym of the team leader's institution.
* `team_name` may be freely chosen but must contain only lowercase letters.

Example:

```text
3rd_imdc_dasa_forecastlab
```

---

## Repository Documentation Requirements

The repository must contain a well-documented README to ensure reproducibility.

The README must include the following sections:

1. Team and Contributors
2. Repository Structure
3. Libraries and Dependencies
4. Data and Variables
5. Model Training
6. Data Usage Restriction
7. Predictive Uncertainty
8. References

---

## Multiple Models

Teams may submit more than one model.

However:

> Each submitted model must include predictions for all targets within the challenge(s) it is intended to participate in.

Additional details are available in the official repository template.

---

# 3. Data Usage Policy

Any dataset that is **not** available through:

* The FTP server
* The Mosqlimate API

must be submitted to the organizers.

These datasets will then be shared with all participants to ensure:

* Fairness
* Transparency
* Reproducibility

---

# 4. Prediction Format and Requirements

## 4.1 Prediction Data Structure

Prediction dataframes must contain the following columns:

| Column    | Description                         |
| --------- | ----------------------------------- |
| `date`    | Forecast target date (`YYYY-MM-DD`) |
| `pred`    | Median prediction (50th percentile) |
| `lower_x` | Lower bound of prediction interval  |
| `upper_x` | Upper bound of prediction interval  |

### Required Prediction Intervals

| Interval | Lower Quantile | Upper Quantile |
| -------- | -------------- | -------------- |
| 50%      | `lower_50`     | `upper_50`     |
| 80%      | `lower_80`     | `upper_80`     |
| 90%      | `lower_90`     | `upper_90`     |
| 95%      | `lower_95`     | `upper_95`     |

Example:

* `lower_95` = 2.5th percentile
* `upper_95` = 97.5th percentile

---

## 4.2 Validation Rules

To be accepted by the platform, predictions must satisfy all of the following conditions.

### Sunday Dates

All prediction dates must correspond to Sundays.

### Continuous Weekly Series

No gaps are allowed in the sequence of forecast dates.

### Full Seasonal Coverage

Predictions must cover every week between:

```text
EW41 (previous year)
through
EW40 (target year)
```

### Non-Negative Values

All predictions must satisfy:

```text
prediction >= 0
```

### Nested Prediction Intervals

Prediction intervals must be ordered as follows:

```text
lower_95 ≤ lower_90 ≤ lower_80 ≤ lower_50 ≤ pred
≤ upper_50 ≤ upper_80 ≤ upper_90 ≤ upper_95
```

Additional submission details are provided in the official template repository.

---

# 5. Submission Timeline and Forecast Targets

For every geographic unit included in a selected challenge, the following predictions must be submitted.

---

## 5.1 Validation Phase

### Deadline: July 1, 2026

### Validation Test 1

Forecast:

```text
EW41 2022 – EW40 2023
```

Training data available through:

```text
EW01 2010 – EW25 2022
```

---

### Validation Test 2

Forecast:

```text
EW41 2023 – EW40 2024
```

Training data available through:

```text
EW01 2010 – EW25 2023
```

---

### Validation Test 3

Forecast:

```text
EW41 2024 – EW40 2025
```

Training data available through:

```text
EW01 2010 – EW25 2024
```

---

### Validation Test 4

Forecast:

```text
EW41 2025 – EW40 2026
```

Training data available through:

```text
EW01 2010 – EW25 2025
```

---

## 5.2 Forecast Phase

### Data Update: July 31, 2026

### Submission Deadline: September 10, 2026

### Forecast Target

Predict weekly dengue cases for:

```text
EW41 2026 – EW40 2027
```

using all available data from:

```text
EW01 2010 – EW25 2026
```

---

# 6. Submission Completeness

The following are mandatory:

* Validation forecasts
* Final forecasts
* Predictions for all geographic units within selected challenges

### Invalid Submissions

Submissions will not be evaluated if they:

* Omit any required validation target
* Omit the final forecast target
* Omit any required state or city

---

# 7. Evaluation and Compliance

If issues are identified in:

* The forecasting methodology
* Submitted predictions
* Repository documentation

the organizers will contact the authors and allow corrections.

However:

> The organizers reserve the right to exclude a model from the final reports submitted to the Ministry of Health if issues are not adequately resolved.

Please ensure full compliance with all guidelines before submission.

For additional details, consult the **Instructions** section of the challenge website.

---

# Important Dates

| Date               | Event                                                 |
| ------------------ | ----------------------------------------------------- |
| April 1, 2026      | Challenge launch and registration opening             |
| May 15, 2026       | Team registration deadline                            |
| July 1, 2026       | Validation results submission deadline                |
| July 31, 2026      | Webinar: Validation round results                     |
| September 10, 2026 | Forecast submission deadline                          |
| September 22, 2026 | Internal webinar: Model methodologies                 |
| October 15, 2026   | International webinar: Technical results              |
| October 30, 2026   | International webinar: Public presentation of results |

---

# Contact

**Email:** [mosqlimate@gmail.com](mailto:mosqlimate@gmail.com)

---

## Previous Editions

* IMDC Rules 2024
* IMDC Rules 2025

