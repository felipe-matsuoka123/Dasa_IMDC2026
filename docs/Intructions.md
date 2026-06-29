The **Infodengue–Mosqlimate Dengue Challenge (IMDC)** is an international collaborative initiative focused on developing predictive models for dengue outbreaks in Brazil.

Researchers and teams from fields such as epidemiology, data science, statistics, and mathematical modeling are invited to participate by submitting forecasts based on open datasets provided by the organizers.

## Challenge Categories

### Mandatory Challenge

- **Dengue (State Level)**: Forecast dengue cases for all Brazilian states (_UFs_), except Espírito Santo.
    

### Optional Challenges

1. **Dengue (City Level)**: Forecast dengue cases for 15 selected cities.
    
2. **Chikungunya (State Level)**: Forecast chikungunya cases for all Brazilian states (_UFs_), except Espírito Santo.
    
3. **Chikungunya (City Level)**: Forecast chikungunya cases for 10 selected cities.
    

> Participation in the mandatory challenge is required. Optional challenges are voluntary.

---

# 1. Team Registration

Participants must form a research team and register through the challenge website.

Teams may include researchers from different institutions and countries.

---

# 2. Data Access

Training datasets are available through an FTP server provided by the Mosqlimate platform.

Available data include:

- Dengue epidemiological data
    
- Chikungunya epidemiological data
    
- Climate data
    
- Demographic data
    

Participants may also:

- Use the Mosqlimate API to retrieve specific subsets of data.
    
- Incorporate additional open-access datasets, provided they are:
    
    - Shared with all participants through the organizers.
        
    - Regularly updated.
        
    - Available nationwide.
        

---

# 3. Geographic Scope of the Challenges

Participants must submit forecasts for **all geographic units** within each challenge they choose to participate in.

## Mandatory Challenge – Dengue (State Level)

Forecast dengue cases for all Brazilian states except Espírito Santo.

---

## Optional Challenge 1 – Dengue (City Level)

Forecast dengue cases for the following cities:

|City|State|Geocode|
|---|---|---|
|Teixeira de Freitas|BA|2931350|
|Vitória da Conquista|BA|2933307|
|Brejo Santo|CE|2302503|
|Coronel Fabriciano|MG|3119401|
|São José do Rio Preto|SP|3549805|
|Presidente Prudente|SP|3541406|
|Rio Branco|AC|1200401|
|Cruzeiro do Sul|AC|1200203|
|Paraíso do Tocantins|TO|1716109|
|Londrina|PR|4113700|
|Cambé|PR|4103701|
|Cascavel|PR|4104808|
|Aparecida de Goiânia|GO|5201405|
|Campo Novo do Parecis|MT|5102637|
|Novo Gama|GO|5215231|

---

## Optional Challenge 2 – Chikungunya (State Level)

Forecast chikungunya cases for all Brazilian states except Espírito Santo.

---

## Optional Challenge 3 – Chikungunya (City Level)

Forecast chikungunya cases for the following cities:

|City|State|Geocode|
|---|---|---|
|Teresina|PI|2211001|
|Teixeira de Freitas|BA|2931350|
|Montes Claros|MG|3143302|
|Coronel Fabriciano|MG|3119401|
|Palmas|TO|1721000|
|Paraíso do Tocantins|TO|1716109|
|Cascavel|PR|4104808|
|Xanxerê|SC|4219507|
|Cuiabá|MT|5103403|
|Campo Novo do Parecis|MT|5102637|

---

## Cities Included in Both Diseases

The following cities require forecasts for both dengue and chikungunya:

|City|State|Geocode|
|---|---|---|
|Teixeira de Freitas|BA|2931350|
|Coronel Fabriciano|MG|3119401|
|Paraíso do Tocantins|TO|1716109|
|Cascavel|PR|4104808|
|Campo Novo do Parecis|MT|5102637|

---

# 4. Forecast Targets

The challenge includes:

- Four validation targets
    
- One final forecasting target
    

A dengue season is defined as:

> Epidemiological Week (EW) 41 of one year through EW 40 of the following year.

## Validation Targets

|Validation Test|Target Season|Training Data Available Until|
|---|---|---|
|Validation 1|EW41 2022 – EW40 2023|EW25 2022|
|Validation 2|EW41 2023 – EW40 2024|EW25 2023|
|Validation 3|EW41 2024 – EW40 2025|EW25 2024|
|Validation 4|EW41 2025 – EW40 2026|EW25 2025|

## Final Forecast Target

Forecast weekly dengue cases for:

**EW41 2026 – EW40 2027**

using all available data from:

**EW01 2010 – EW25 2026**

---

## Forecast Outputs

Models must generate:

### Validation Forecasts

- Median estimate
    
- 50% predictive interval
    
- 80% predictive interval
    
- 90% predictive interval
    
- 95% predictive interval
    

### Final Forecasts

- Median estimate
    
- 50% predictive interval
    
- 80% predictive interval
    
- 90% predictive interval
    
- 95% predictive interval
    

### Quantile Definitions

|Interval|Lower Quantile|Upper Quantile|
|---|---|---|
|50%|25th percentile|75th percentile|
|80%|10th percentile|90th percentile|
|90%|5th percentile|95th percentile|
|95%|2.5th percentile|97.5th percentile|

> The median estimate corresponds to the 50th percentile (0.5 quantile).

### Important Submission Rule

Participants must submit:

- All validation forecasts
    
- All forecast targets
    
- All geographic units within every selected challenge
    

Incomplete submissions will not be evaluated.

---

# 5. Model Development and Forecast Submission

Teams may use any forecasting methodology, including:

- Statistical models
    
- Mechanistic models
    
- Epidemiological models
    
- Machine learning methods
    
- Artificial intelligence approaches
    

Forecasts must follow the standardized format described in the official GitHub repository.

---

# 6. Model Evaluation

Forecasts will be evaluated through:

- Retrospective validation
    
- Comparison across methodologies
    

### Primary Metric

**Weighted Interval Score (WIS)**

Interval forecasts will be evaluated on a weekly basis.

---

# 7. Ensemble Model Construction

The IMDC organizers will construct an ensemble model by combining forecasts from multiple teams.

Ensemble forecasts often provide more robust and accurate outbreak predictions.

---

# 8. Dissemination of Results

Results may be presented through:

- Scientific webinars
    
- Project workshops
    
- Technical reports
    
- Scientific publications
    

---

# 9. Calendar

## Important Dates

|Date|Event|
|---|---|
|April 1, 2026|Challenge launch and registration opening|
|May 15, 2026|Registration deadline|
|July 1, 2026|Validation results submission deadline|
|July 31, 2026|Webinar: Validation results|
|September 10, 2026|Forecast submission deadline|
|September 22, 2026|Internal methodology webinar|
|October 15, 2026|International webinar: Technical results|
|October 30, 2026|International webinar: Public presentation of results|

---

# 10. Support and Contact

## Discord

Join the official Discord server.

## Email

**[mosqlimate@gmail.com](mailto:mosqlimate@gmail.com)**

---

## Previous Editions

- Instructions IMDC 2024
    
- Instructions IMDC 2025
    

---

**Contact:** [mosqlimate@gmail.com](mailto:mosqlimate@gmail.com)